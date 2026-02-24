from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
import bcrypt
import jwt
import datetime
import os
import uuid
import socket
import re
import math  # === NEW
# (no external deps beyond stdlib)

# ====== CONFIG ======
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secure_secret")
DB_NAME = "auth_system"

# MQTT fixed config
MQTT_USERNAME = "taha"
MQTT_PASSWORD = "taha"
MQTT_PORT = 1883

# ====== INIT ======
app = Flask(__name__)
CORS(app)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db["users_auth"]
enrollments_collection = db["enrolled_devices"]

# === NEW/UPDATED COLLECTIONS ===
rooms_collection = db["rooms"]
mqtt_readings_collection = db["mqtt_readings"]  # expected schema: {device_uuid, distances: {"A0":in,"A1":in,"A2":in,"A3":in}, ts}

# ====== UTILS ======
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def generate_token(user_email, expires_days=30):
    payload = {
        "email": user_email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=expires_days)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_server_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "127.0.0.1"

# === NEW: simple validator for inches range ===
MIN_IN = 198
MAX_IN = 29800
def _valid_inch(v):
    try:
        v = float(v)
    except:
        return False
    return (v >= MIN_IN) and (v <= MAX_IN)

# === NEW: trilateration helpers ===
def _anchors_from_room(room):
    """
    Treat A0..A3 as rectangle corners:
      A0=(0,0), A1=(W,0), A2=(W,H), A3=(0,H)
    W = A0-A1, H = A1-A2 (we validate A2-A3≈W and A3-A0≈H with tolerance)
    """
    W = float(room["edges"]["A0_A1"])
    H = float(room["edges"]["A1_A2"])
    return {
        "A0": (0.0, 0.0),
        "A1": (W, 0.0),
        "A2": (W, H),
        "A3": (0.0, H),
    }

def _solve_xy_from_four(anchors, d):
    """
    Linearized 2D trilateration using differences to A0 to remove squares:
      For i in {A1,A2,A3}:
        2*(xi - x0)*x + 2*(yi - y0)*y = (xi^2+yi^2 - di^2) - (x0^2+y0^2 - d0^2)
    Use two best-conditioned rows (A1 & A2). If singular, fallback to A1 & A3.
    """
    (x0,y0) = anchors["A0"]
    r0 = float(d["A0"])
    eqs = []
    for key in ["A1","A2","A3"]:
        (xi, yi) = anchors[key]
        ri = float(d[key])
        A = 2*(xi - x0)
        B = 2*(yi - y0)
        C = (xi*xi + yi*yi - ri*ri) - (x0*x0 + y0*y0 - r0*r0)
        eqs.append((A,B,C,key))

    def solve_two(e1, e2):
        (A1,B1,C1,_) = e1
        (A2,B2,C2,_) = e2
        det = A1*B2 - A2*B1
        if abs(det) < 1e-9:
            return None
        x = (C1*B2 - C2*B1) / det
        y = (A1*C2 - A2*C1) / det
        return (x,y)

    # try A1 & A2
    sol = solve_two(eqs[0], eqs[1])
    if sol is None:
        # fallback: A1 & A3
        sol = solve_two(eqs[0], eqs[2])
    if sol is None:
        # last fallback: A2 & A3
        sol = solve_two(eqs[1], eqs[2])
    return sol

def _get_latest_ranges_from_mongo(device_uuid):
    """
    Expects documents like:
      {
        "device_uuid": "...",
        "distances": {"A0": 1234.0, "A1": 1500.5, "A2": 1800.0, "A3": 1400.0},  # inches
        "ts": ISODate(...)
      }
    """
    doc = mqtt_readings_collection.find_one({"device_uuid": device_uuid}, sort=[("ts", DESCENDING)])
    if not doc:
        return None
    distances = doc.get("distances") or {}
    if all(k in distances for k in ["A0","A1","A2","A3"]):
        # ensure float
        return {k: float(distances[k]) for k in ["A0","A1","A2","A3"]}
    return None

# ====== ROUTES ======

@app.route("/")
def index():
    return jsonify({"msg": "Standalone Auth API is running"}), 200

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"msg": "Name, email and password are required"}), 400

    if users_collection.find_one({"email": email}):
        return jsonify({"msg": "Email already exists"}), 409

    hashed_pw = hash_password(password)
    users_collection.insert_one({
        "name": name,
        "email": email,
        "password": hashed_pw
    })

    return jsonify({"msg": "User registered successfully"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400

    user = users_collection.find_one({"email": email})
    if not user or not verify_password(password, user["password"]):
        return jsonify({"msg": "Invalid credentials"}), 401

    token = generate_token(email)
    return jsonify({"msg": "Login successful", "token": token}), 200

@app.route("/api/verify", methods=["GET"])
def verify():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    return jsonify({"msg": "Token is valid", "email": decoded["email"]}), 200

@app.route("/api/refresh", methods=["POST"])
def refresh_token():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    user = users_collection.find_one({"email": decoded["email"]})
    if not user:
        return jsonify({"msg": "User not found"}), 404

    new_token = generate_token(decoded["email"])
    return jsonify({"msg": "Token refreshed", "token": new_token}), 200

@app.route("/api/config_mode", methods=["GET"])
def config_mode():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]
    user = users_collection.find_one({"email": email})
    if not user:
        return jsonify({"msg": "User not found"}), 404

    # Assign UUID if not already present
    if "uuid" not in user:
        user_uuid = str(uuid.uuid4())
        users_collection.update_one({"email": email}, {"$set": {"uuid": user_uuid}})
    else:
        user_uuid = user["uuid"]

    config = {
        "server_ip": get_server_ip(),
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password": MQTT_PASSWORD,
        "port": MQTT_PORT,
        "uuid": user_uuid
    }

    return jsonify(config), 200







@app.route("/api/enrollment", methods=["POST"])
def enrollment():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Accept JSON or form-data safely
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()

    if not data:
        return jsonify({"msg": "Body required (JSON or form-data)"}), 400

    # Allow either mqtt_topic (7 digits) or uuid
    mqtt_topic = data.get("mqtt_topic")
    uuid_val = data.get("uuid")

    if mqtt_topic and not re.fullmatch(r"\d{7}", str(mqtt_topic)):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    if not (mqtt_topic or uuid_val):
        return jsonify({"msg": "Provide either 'mqtt_topic' (7-digit) or 'uuid'"}), 400

    # Common required fields
    required_fields = ["server_ip", "mqtt_username", "mqtt_password", "port", "mobile_ssid", "mobile_passcode"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"msg": f"Missing required fields: {', '.join(missing)}"}), 400

    # Build the document
    enrollment_data = {
        "email": email,
        "server_ip": data["server_ip"],
        "mqtt_username": data["mqtt_username"],
        "mqtt_password": data["mqtt_password"],
        "port": data["port"],
        "mobile_ssid": data["mobile_ssid"],
        "mobile_passcode": data["mobile_passcode"],
        "device_name": data.get("device_name"),
        "enrolled_at": datetime.datetime.utcnow()
    }

    # Store both if provided; keep names explicit
    if mqtt_topic:
        enrollment_data["mqtt_topic"] = str(mqtt_topic)
    if uuid_val:
        enrollment_data["uuid"] = str(uuid_val)

    try:
        enrollments_collection.insert_one(enrollment_data)
    except Exception as e:
        # Ensure we always return a valid response
        return jsonify({"msg": "DB insert failed", "error": str(e)}), 500

    return jsonify({"msg": "Device enrolled successfully"}), 201









# === NEW/UPDATED CODE BELOW ===

@app.route("/api/rooms", methods=["POST"])
def create_room():
    """
    Create Room API
    Body:
    {
      "A0_A1": inches, "A1_A2": inches, "A2_A3": inches, "A3_A0": inches,
      "label": "Optional room name"
    }
    Constraints: each length MIN_IN..MAX_IN; opposite sides should match (±3%)
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401
    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401
    email = decoded["email"]

    data = request.json or {}
    keys = ["A0_A1","A1_A2","A2_A3","A3_A0"]
    if not all(k in data for k in keys):
        return jsonify({"msg": "Send all four edges: A0-A1, A1-A2, A2-A3, A3-A0"}), 400

    vals = {}
    for k in keys:
        if not _valid_inch(data[k]):
            return jsonify({"msg": f"{k} must be between {MIN_IN} and {MAX_IN} inches"}), 400
        vals[k] = float(data[k])

    # basic rectangular consistency (±3% tolerance)
    tol = 0.03
    def _close(a,b): 
        return abs(a-b) <= tol*max(a,b)
    if not (_close(vals["A0_A1"], vals["A2_A3"]) and _close(vals["A1_A2"], vals["A3_A0"])):
        return jsonify({"msg":"Opposite sides must be approximately equal (±3%) for rectangular room"}), 400

    room_doc = {
        "owner": email,
        "room_id": str(uuid.uuid4()),
        "edges": {
            "A0_A1": vals["A0_A1"],
            "A1_A2": vals["A1_A2"],
            "A2_A3": vals["A2_A3"],
            "A3_A0": vals["A3_A0"],
        },
        "label": data.get("label"),
        "created_at": datetime.datetime.utcnow()
    }
    rooms_collection.insert_one(room_doc)
    return jsonify({"msg":"Room created", "room_id": room_doc["room_id"]}), 201

@app.route("/api/enrollment/<uuid_str>", methods=["PATCH"])
def update_enrollment(uuid_str):
    """
    Update Enrollment API
    Path: /api/enrollment/<uuid>
    Body (any of):
      { "device_name": "...", "mobile_ssid": "...", "mobile_passcode": "..." }
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401
    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401
    email = decoded["email"]

    data = request.json or {}
    allowed = {k: v for k, v in data.items() if k in ["device_name","mobile_ssid","mobile_passcode"]}
    if not allowed:
        return jsonify({"msg":"Nothing to update"}), 400

    res = enrollments_collection.update_one({"email": email, "uuid": uuid_str}, {"$set": allowed})
    if res.matched_count == 0:
        return jsonify({"msg":"Enrollment not found"}), 404
    return jsonify({"msg":"Enrollment updated"}), 200

@app.route("/api/visualize", methods=["POST"])
def visualize():
    """
    Visualization API
    Body:
    {
      "room_id": "...",
      "device_uuid": "...",           # optional if 'ranges' provided
      "ranges": { "A0":in, "A1":in, "A2":in, "A3":in }  # optional; overrides MQTT if provided
    }
    Flow:
      - Load room -> anchor coords
      - Get ranges: use 'ranges' if provided else pull latest from mqtt_readings
      - Solve (x,y) and return
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401
    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401
    email = decoded["email"]

    data = request.json or {}
    room_id = data.get("room_id")
    if not room_id:
        return jsonify({"msg":"room_id is required"}), 400

    room = rooms_collection.find_one({"room_id": room_id, "owner": email})
    if not room:
        return jsonify({"msg":"Room not found"}), 404

    anchors = _anchors_from_room(room)

    ranges = None
    if "ranges" in data and isinstance(data["ranges"], dict):
        rng = data["ranges"]
        if all(k in rng for k in ["A0","A1","A2","A3"]):
            try:
                ranges = {k: float(rng[k]) for k in ["A0","A1","A2","A3"]}
            except:
                return jsonify({"msg":"ranges must be numeric inches"}), 400

    if ranges is None:
        device_uuid = data.get("device_uuid")
        if not device_uuid:
            return jsonify({"msg":"Provide either 'ranges' or 'device_uuid'"}), 400
        ranges = _get_latest_ranges_from_mongo(device_uuid)
        if ranges is None:
            return jsonify({"msg":"No MQTT distances found for device_uuid"}), 404

    # sanity: ranges must be within room diagonal a bit larger
    W = float(room["edges"]["A0_A1"])
    H = float(room["edges"]["A1_A2"])
    diag = math.hypot(W, H)
    max_allowed = diag * 1.5  # some buffer
    for k,v in ranges.items():
        if v <= 0 or v > max_allowed:
            return jsonify({"msg":f"Range {k} invalid (0..{max_allowed:.1f} inches)"}), 400

    xy = _solve_xy_from_four(anchors, ranges)
    if xy is None or any(math.isnan(t) or math.isinf(t) for t in xy):
        return jsonify({"msg":"Unable to compute position"}), 422

    x,y = xy
    # clamp to room rectangle bounds (optional)
    x = max(0.0, min(W, x))
    y = max(0.0, min(H, y))

    return jsonify({
        "room_id": room_id,
        "anchors": anchors,
        "ranges_in": ranges,
        "position": {"x": x, "y": y},   # inches from A0 origin
        "units": "inches"
    }), 200

# ====== RUN ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
