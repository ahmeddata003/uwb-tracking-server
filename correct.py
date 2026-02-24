from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import bcrypt
import jwt
import datetime
import os
import socket

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
uuid_counter_collection = db["uuid_counter"]
mqtt_data_collection = db["mqtt_data"]

# ====== UTILS ======
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

def generate_token(user_email):
    payload = {
        "email": user_email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=1)
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

def generate_7_digit_uuid():
    """Generate a unique 7-digit UUID for MQTT topic"""
    # Get or create counter document
    counter_doc = uuid_counter_collection.find_one_and_update(
        {"_id": "uuid_counter"},
        {"$inc": {"counter": 1}},
        upsert=True,
        return_document=True
    )
    
    # Generate 7-digit UUID starting from 1000000
    uuid_value = counter_doc.get("counter", 1000000)
    
    # Ensure it's 7 digits
    if uuid_value < 1000000:
        uuid_value = 1000000
        uuid_counter_collection.update_one(
            {"_id": "uuid_counter"},
            {"$set": {"counter": 1000000}},
            upsert=True
        )
    
    return str(uuid_value)

def validate_7_digit_uuid(uuid_str):
    """Validate if the UUID is a valid 7-digit number"""
    try:
        uuid_int = int(uuid_str)
        return len(uuid_str) == 7 and 1000000 <= uuid_int <= 9999999
    except ValueError:
        return False

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

    # Generate a new 7-digit UUID for MQTT topic
    mqtt_topic_uuid = generate_7_digit_uuid()

    config = {
        "server_ip": get_server_ip(),
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password": MQTT_PASSWORD,
        "port": MQTT_PORT,
        "mqtt_topic": mqtt_topic_uuid
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
    data = request.json

    required_fields = ["server_ip", "mqtt_username", "mqtt_password", "port", "mqtt_topic", "mobile_ssid", "mobile_passcode"]
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Missing required fields"}), 400

    # Validate 7-digit UUID
    mqtt_topic = data["mqtt_topic"]
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if this MQTT topic is already enrolled by another user
    existing_enrollment = enrollments_collection.find_one({"mqtt_topic": mqtt_topic})
    if existing_enrollment and existing_enrollment["email"] != email:
        return jsonify({"msg": "MQTT topic already in use by another user"}), 409

    enrollment_data = {
        "email": email,
        "server_ip": data["server_ip"],
        "mqtt_username": data["mqtt_username"],
        "mqtt_password": data["mqtt_password"],
        "port": data["port"],
        "mqtt_topic": mqtt_topic,
        "mobile_ssid": data["mobile_ssid"],
        "mobile_passcode": data["mobile_passcode"],
        "enrolled_at": datetime.datetime.utcnow()
    }

    enrollments_collection.insert_one(enrollment_data)
    return jsonify({"msg": "Device enrolled successfully"}), 201

@app.route("/api/enrollments", methods=["GET"])
def get_enrollments():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]
    devices = list(enrollments_collection.find({"email": email}, {"_id": 0}))

    return jsonify({"devices": devices}), 200

@app.route("/api/devices/<mqtt_topic>", methods=["GET"])
def get_devices_by_topic(mqtt_topic):
    """Get all devices enrolled under a specific MQTT topic"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    # Validate 7-digit UUID
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Get all devices for this MQTT topic
    devices = list(enrollments_collection.find({"mqtt_topic": mqtt_topic}, {"_id": 0}))
    
    if not devices:
        return jsonify({"msg": "No devices found for this MQTT topic"}), 404

    return jsonify({
        "mqtt_topic": mqtt_topic,
        "devices": devices,
        "device_count": len(devices)
    }), 200

@app.route("/api/mqtt/data", methods=["POST"])
def store_mqtt_data():
    """Store MQTT data received from devices"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]
    data = request.json

    required_fields = ["mqtt_topic", "device_id", "message", "timestamp"]
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Missing required fields: mqtt_topic, device_id, message, timestamp"}), 400

    # Validate 7-digit UUID
    mqtt_topic = data["mqtt_topic"]
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # Store MQTT data
    mqtt_data = {
        "email": email,
        "mqtt_topic": mqtt_topic,
        "device_id": data["device_id"],
        "message": data["message"],
        "timestamp": data["timestamp"],
        "received_at": datetime.datetime.utcnow(),
        "data_type": data.get("data_type", "sensor_data"),  # Optional field
        "metadata": data.get("metadata", {})  # Optional field for additional data
    }

    mqtt_data_collection.insert_one(mqtt_data)
    return jsonify({"msg": "MQTT data stored successfully"}), 201

@app.route("/api/mqtt/data/<mqtt_topic>", methods=["GET"])
def get_mqtt_data_by_topic(mqtt_topic):
    """Get MQTT data for a specific topic (for visualization)"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Validate 7-digit UUID
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # Get query parameters for filtering
    limit = request.args.get("limit", 100, type=int)  # Default 100 records
    device_id = request.args.get("device_id")  # Optional filter by device
    data_type = request.args.get("data_type")  # Optional filter by data type

    # Build query
    query = {"mqtt_topic": mqtt_topic}
    if device_id:
        query["device_id"] = device_id
    if data_type:
        query["data_type"] = data_type

    # Get MQTT data
    mqtt_data = list(mqtt_data_collection.find(query, {"_id": 0}).sort("received_at", -1).limit(limit))
    
    return jsonify({
        "mqtt_topic": mqtt_topic,
        "data": mqtt_data,
        "count": len(mqtt_data),
        "filters": {
            "device_id": device_id,
            "data_type": data_type,
            "limit": limit
        }
    }), 200

@app.route("/api/mqtt/data/<mqtt_topic>/latest", methods=["GET"])
def get_latest_mqtt_data(mqtt_topic):
    """Get latest MQTT data for a specific topic"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Validate 7-digit UUID
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # Get latest data for each device
    pipeline = [
        {"$match": {"mqtt_topic": mqtt_topic}},
        {"$sort": {"received_at": -1}},
        {"$group": {
            "_id": "$device_id",
            "latest_data": {"$first": "$$ROOT"}
        }},
        {"$replaceRoot": {"newRoot": "$latest_data"}},
        {"$project": {"_id": 0}}
    ]

    latest_data = list(mqtt_data_collection.aggregate(pipeline))
    
    return jsonify({
        "mqtt_topic": mqtt_topic,
        "latest_data": latest_data,
        "device_count": len(latest_data)
    }), 200

# ====== RUN ======
if __name__ == "__main__":
    app.run(host='0.0.0.0')

