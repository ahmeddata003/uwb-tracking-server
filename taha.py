# mqtt_to_mongo.py
import os, sys, json, signal, base64
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from pymongo import MongoClient
from bson.binary import Binary
from datetime import datetime, timedelta, timezone

PKT = timezone(timedelta(hours=5))




# -------------------- Config --------------------
MQTT_BROKER     = os.getenv("MQTT_BROKER", "15.204.231.252")
MQTT_PORT       = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER       = os.getenv("MQTT_USER", "taha")       # leave empty if broker allows anonymous
MQTT_PASS       = os.getenv("MQTT_PASS", "taha")
MQTT_CLIENT_ID  = os.getenv("MQTT_CLIENT_ID", "mqtt-to-mongo")
MQTT_QOS        = int(os.getenv("MQTT_QOS", "0"))
INCLUDE_SYS     = os.getenv("INCLUDE_SYS", "0").lower() in ("1","true","yes")

MONGO_URI       = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB        = os.getenv("MONGO_DB", "auth_system")
MONGO_COLLECTION= os.getenv("MONGO_COLLECTION", "mqtt_data")

# -------------------- Mongo --------------------
mongo_client = MongoClient(MONGO_URI)
col = mongo_client[MONGO_DB][MONGO_COLLECTION]
col.create_index("ts")
col.create_index("topic")

# -------------------- Helpers --------------------
def _rc_value(x):
    # Works for both int (MQTT v3) and ReasonCodes (v5)
    return getattr(x, "value", x)

def _rc_name(x):
    # Human-readable reason
    try:
        return x.getName()
    except Exception:
        names = {0: "Success", 4: "Bad username or password", 5: "Not authorized"}
        try:
            return names.get(int(x), str(x))
        except Exception:
            return str(x)

def _bytes_to_data(b: bytes) -> tuple[str, bytes]:
    """
    Returns (data_string, raw_bytes).
    JSON -> compact string; UTF-8 -> text; otherwise base64 (prefixed).
    """
    if not b:
        return "", b
    try:
        # Try JSON first
        parsed = json.loads(b.decode("utf-8"))
        return json.dumps(parsed, separators=(",", ":")), b
    except Exception:
        pass
    try:
        return b.decode("utf-8"), b
    except Exception:
        return "base64:" + base64.b64encode(b).decode("ascii"), b

# -------------------- MQTT Client (Paho v2 / MQTT v5) --------------------
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                     client_id=MQTT_CLIENT_ID,
                     protocol=mqtt.MQTTv5)

if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

def on_connect(client, userdata, flags, reason_code, properties):
    rc_val  = _rc_value(reason_code)
    rc_name = _rc_name(reason_code)
    if rc_val != 0:
        print(f"[CONNECT] Failed: {rc_name}")
        if rc_val in (4, 5) or "Not authorized" in rc_name or "Bad username" in rc_name:
            print("[HINT] Fix MQTT_USER/MQTT_PASS or broker ACLs.")
            client.disconnect()
        return

    subs = [("#", MQTT_QOS)]
    if INCLUDE_SYS:
        subs.append(("$SYS/#", MQTT_QOS))

    client.subscribe(subs)
    pretty = ", ".join(t for t,_ in subs)
    print(f"[CONNECTED] {rc_name}; subscribed to {pretty}")






def on_message(client, userdata, msg: mqtt.MQTTMessage):
    data_str, raw = _bytes_to_data(msg.payload or b"")

    # Get actual UTC time
    ts_utc = datetime.utcnow()

    # Add 5 hours for Pakistan Time
    ts_pk = ts_utc + timedelta(hours=5)

    doc = {
        "ts": ts_pk,      # save Pakistan time directly as UTC
        "topic": msg.topic,
        "data": data_str,
    }

    try:
        col.insert_one(doc)
        print(doc)
    except Exception as e:
        print(f"[MONGO ERROR] {e}", file=sys.stderr)


        

def on_disconnect(client, userdata, reason_code, properties):
    print(f"[DISCONNECTED] {_rc_name(reason_code)}")

client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

client.reconnect_delay_set(min_delay=1, max_delay=60)
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
client.loop_start()

# -------------------- Graceful shutdown --------------------
def _stop(*_):
    print("Stopping...")
    try:
        client.loop_stop()
        client.disconnect()
    finally:
        mongo_client.close()
    sys.exit(0)

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

print(f"Bridging MQTT {MQTT_BROKER}:{MQTT_PORT} -> MongoDB {MONGO_URI} ({MONGO_DB}.{MONGO_COLLECTION})")

# Keep main thread alive
try:
    signal.pause()
except AttributeError:
    import time
    while True:
        time.sleep(1)
