from flask import Flask
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# MQTT Configuration
MQTT_BROKER = "15.204.231.252"
MQTT_PORT = 1883
MQTT_USER = "taha"
MQTT_PASS = "taha"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to MQTT broker with code {rc}")
    client.subscribe("UWB123")

def on_message(client, userdata, msg):
    raw_message = msg.payload.decode('utf-8')
    print(f"MQTT Message: {raw_message}")
    socketio.emit('mqtt_data', raw_message)

# Initialize MQTT client
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

@socketio.on('connect')
def handle_connect():
    print("WebSocket client connected")
    mqtt_client.publish("UWB123", "begin")

if __name__ == '__main__':
    socketio.run(app, host='15.204.231.252', port=8000)
