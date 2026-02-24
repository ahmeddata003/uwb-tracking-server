
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, disconnect
from pymongo import MongoClient
import bcrypt
import jwt
import datetime
import os
import socket
import uuid
from werkzeug.utils import secure_filename
from pymongo import ReturnDocument
import math
from bson import ObjectId
import re
import json
import threading
import time




app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow CORS for WebSocket
# Configure SocketIO to work with nginx proxy
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)




# ==== Upload config ====
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
# e.g., 10 MB
MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Ensure folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)





# ====== CONFIG ======
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
JWT_SECRET = os.getenv("JWT_SECRET", "super_secure_secret")
DB_NAME = "auth_system"

# MQTT fixed config
MQTT_USERNAME = "taha"
MQTT_PASSWORD = "taha"
MQTT_PORT = 1883

# ====== INIT ======

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # Test the connection
    client.server_info()
    print(f"✓ Connected to MongoDB at {MONGO_URI}")
    print(f"✓ Using database: {DB_NAME}")
except Exception as e:
    print(f"✗ ERROR: Failed to connect to MongoDB: {e}")
    print(f"✗ MONGO_URI: {MONGO_URI}")
    print(f"✗ DB_NAME: {DB_NAME}")
    raise

db = client[DB_NAME]
users_collection = db["users_auth"]
enrollments_collection = db["enrolled_devices"]
uuid_counter_collection = db["uuid_counter"]
mqtt_data_collection = db["mqtt_data"]
room_uploads_collection = db["room_uploads"]
rooms_collection = db["rooms"]
used_topics_collection = db["used_mqtt_topics"]  # Track all used topics permanently
used_emails_collection = db["used_emails"]  # Track all used emails permanently

# Verify collections exist and show counts
try:
    user_count = users_collection.count_documents({})
    enrollment_count = enrollments_collection.count_documents({})
    print(f"✓ Database initialized - Users: {user_count}, Enrollments: {enrollment_count}")
except Exception as e:
    print(f"⚠ Warning: Could not verify collection counts: {e}")






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
    return "15.204.231.252"



#################################

def generate_7_digit_uuid():
    """
    Generate a globally unique 7-digit MQTT topic.
    Once a value is used, it will never be reused - even if enrollment is deleted.
    """
    max_attempts = 1000  # Prevent infinite loop
    attempts = 0
    
    while attempts < max_attempts:
        # Atomically increment a counter in Mongo
        counter_doc = uuid_counter_collection.find_one_and_update(
            {"_id": "mqtt_topic_counter"},
            {"$inc": {"counter": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        # If it's a fresh doc (no counter yet), initialize to 1,000,000
        if "counter" not in counter_doc:
            counter_doc = uuid_counter_collection.find_one_and_update(
                {"_id": "mqtt_topic_counter"},
                {"$set": {"counter": 1000000}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )

        value = counter_doc["counter"]

        # Ensure we start from 1,000,000 (7 digits)
        if value < 1000000:
            value = 1000000
            uuid_counter_collection.update_one(
                {"_id": "mqtt_topic_counter"},
                {"$set": {"counter": value}},
                upsert=True,
            )

        # Format as 7-digit string
        topic = f"{value:07d}"
        
        # Check if topic is currently enrolled (actually in use)
        enrolled = enrollments_collection.find_one({"mqtt_topic": topic})
        if enrolled:
            attempts += 1
            continue  # Topic is enrolled and in use, try next one
        
        # Check if topic was enrolled before (even if enrollment was deleted)
        existing_enrolled = used_topics_collection.find_one({"mqtt_topic": topic, "enrolled": True})
        if existing_enrolled:
            attempts += 1
            continue  # Topic was enrolled before, never reuse it
        
        # Topic is available - return it without marking as used
        # Topic will only be marked as enrolled when actually enrolled via enrollment endpoint
        return topic
    
    # If we've tried too many times, something is wrong
    raise Exception("Unable to generate unique MQTT topic after maximum attempts")





def validate_7_digit_uuid(uuid_str):
    """Validate if the UUID is a valid 7-digit number"""
    try:
        uuid_int = int(uuid_str)
        return len(uuid_str) == 7 and 1000000 <= uuid_int <= 9999999
    except ValueError:
        return False

def three_point_calculation(x1, y1, x2, y2, r1, r2):
    """Same as main.py three_point method"""
    temp_x = 0.0
    temp_y = 0.0
    # 圆心距离 (distance between circle centers)
    p2p = math.sqrt((x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2))

    # 判断是否相交 (check if circles intersect)
    if r1 + r2 <= p2p:
        temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
        temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
    else:
        dr = p2p / 2 + (r1 * r1 - r2 * r2) / (2 * p2p)
        temp_x = x1 + (x2 - x1) * dr / p2p
        temp_y = y1 + (y2 - y1) * dr / p2p

    return temp_x, temp_y

def calculate_tag_positions(mqtt_topic, room, email):
    """
    Calculate tag positions from MQTT data.
    Returns tag_positions dict or None if error.
    """
    # Validate access
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return None, "You don't have access to this MQTT topic"
    
    # Get room dimensions
    width = float(room.get("width_in", 0))
    height = float(room.get("height_in", 0))
    if width <= 0 or height <= 0:
        return None, "Room has invalid dimensions"
    
    # Anchor positions (in inches)
    anchor_positions = [
        (0, 0),           # A0
        (width, 0),       # A1
        (width, height),  # A2
        (0, height)       # A3
    ]
    
    # Fetch latest MQTT data
    mqtt_records = list(mqtt_data_collection.find(
        {"$or": [{"mqtt_topic": mqtt_topic}, {"topic": mqtt_topic}]}
    ).sort([("ts", -1), ("received_at", -1), ("timestamp", -1)]).limit(100))
    
    if not mqtt_records:
        return None, "No MQTT data found for this topic"
    
    # Parse MQTT data and group by tag ID
    tag_data = {}
    for record in mqtt_records:
        data_str = record.get("data") or record.get("message", "")
        if not data_str:
            continue
        try:
            tag_info = json.loads(data_str)
            tag_id = tag_info.get("id")
            ranges = tag_info.get("range", [])
            if tag_id is not None and isinstance(ranges, list) and len(ranges) >= 4:
                if tag_id not in tag_data:
                    timestamp = record.get("ts") or record.get("received_at") or record.get("timestamp")
                    tag_data[tag_id] = {"range": ranges, "timestamp": timestamp}
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
    
    if not tag_data:
        return None, "No valid tag data found in MQTT records"
    
    # Calculate positions
    tag_positions = {}
    for tag_id, tag_info in tag_data.items():
        ranges = tag_info["range"]
        distances = [(i, r) for i, r in enumerate(ranges) if r > 0 and i < 4]
        
        if len(distances) < 3:
            tag_positions[tag_id] = {
                "x": None, "y": None, "status": False,
                "error": "Insufficient valid ranges (need at least 3)"
            }
            continue
        
        distances.sort(key=lambda x: x[1])
        selected_ids = [distances[i][0] for i in range(3)]
        
        x_sum, y_sum, count = 0.0, 0.0, 0
        for i in range(3):
            for j in range(i + 1, 3):
                a_id, b_id = selected_ids[i], selected_ids[j]
                a_x, a_y = anchor_positions[a_id]
                b_x, b_y = anchor_positions[b_id]
                temp_x, temp_y = three_point_calculation(a_x, a_y, b_x, b_y, ranges[a_id], ranges[b_id])
                x_sum += temp_x
                y_sum += temp_y
                count += 1
        
        if count > 0:
            x = int(x_sum / count)
            y = int(y_sum / count)
            x_clamped = max(0.0, min(width, x))
            y_clamped = max(0.0, min(height, y))
            
            tag_positions[tag_id] = {
                "x": x_clamped, "y": y_clamped,
                "x_normalized": x_clamped / width if width > 0 else None,
                "y_normalized": y_clamped / height if height > 0 else None,
                "status": True,
                "ranges": {
                    "A0": ranges[0] if len(ranges) > 0 else 0,
                    "A1": ranges[1] if len(ranges) > 1 else 0,
                    "A2": ranges[2] if len(ranges) > 2 else 0,
                    "A3": ranges[3] if len(ranges) > 3 else 0
                },
                "selected_anchors": [f"A{id}" for id in selected_ids],
                "timestamp": tag_info["timestamp"].isoformat() if hasattr(tag_info["timestamp"], 'isoformat') else str(tag_info["timestamp"])
            }
        else:
            tag_positions[tag_id] = {"x": None, "y": None, "status": False, "error": "Calculation failed"}
    
    return tag_positions, None

# ====== ROUTES ======

@app.route("/")
def index():
    return jsonify({"msg": "Standalone Auth API is running"}), 200

@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"msg": "Request body must be valid JSON"}), 400
    
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({"msg": "Name, email and password are required"}), 400

    # Normalize email to lowercase for case-insensitive checking
    email_lower = email.lower().strip()
    
    # CRITICAL: Check if email was ever used before (permanent record)
    existing_used_email = used_emails_collection.find_one({"email": email_lower})
    if existing_used_email:
        return jsonify({"msg": "Email already exists"}), 409
    
    # Check if email exists in users collection (current active users)
    existing_user = users_collection.find_one({"email": email_lower})
    if existing_user:
        # Email exists in users - mark it in used_emails if not already there
        used_emails_collection.update_one(
            {"email": email_lower},
            {"$setOnInsert": {"email": email_lower, "marked_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        return jsonify({"msg": "Email already exists"}), 409
    
    # Additional check: Case-insensitive search for any case variations (backwards compatibility)
    escaped_email = re.escape(email_lower)
    existing_user_case = users_collection.find_one({"email": {"$regex": f"^{escaped_email}$", "$options": "i"}})
    if existing_user_case:
        # Found a case variation - normalize and mark as used
        found_email = existing_user_case.get("email", "").lower()
        used_emails_collection.update_one(
            {"email": found_email},
            {"$setOnInsert": {"email": found_email, "marked_at": datetime.datetime.utcnow()}},
            upsert=True
        )
        return jsonify({"msg": "Email already exists"}), 409
    
    # Final safety check: Count documents with this email (case-insensitive)
    email_count = users_collection.count_documents({"email": {"$regex": f"^{escaped_email}$", "$options": "i"}})
    if email_count > 0:
        return jsonify({"msg": "Email already exists"}), 409

    # Mark email as used permanently BEFORE creating user (prevents race conditions)
    used_emails_collection.update_one(
        {"email": email_lower},
        {"$setOnInsert": {"email": email_lower, "marked_at": datetime.datetime.utcnow()}},
        upsert=True
    )
    
    # Double-check one more time after marking (race condition protection)
    existing_user_final = users_collection.find_one({"email": email_lower})
    if existing_user_final:
        return jsonify({"msg": "Email already exists"}), 409

    hashed_pw = hash_password(password)
    users_collection.insert_one({
        "name": name,
        "email": email_lower,  # Store email in lowercase
        "password": hashed_pw
    })

    return jsonify({"msg": "User registered successfully"}), 201



@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"msg": "Request body must be valid JSON"}), 400
    
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Email and password are required"}), 400

    # Normalize email to lowercase for consistency
    email_lower = email.lower().strip()
    
    user = users_collection.find_one({"email": email_lower})
    if not user or not verify_password(password, user["password"]):
        return jsonify({"msg": "Invalid credentials"}), 401

    token = generate_token(email_lower)
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

    # Generate a new 7-digit UUID for MQTT topic
    mqtt_topic_uuid = generate_7_digit_uuid()

    # Reserve topic for this user as "pending" so it survives re-login until they complete enrollment
    enrollments_collection.update_one(
        {"email": email, "mqtt_topic": mqtt_topic_uuid},
        {
            "$set": {
                "email": email,
                "mqtt_topic": mqtt_topic_uuid,
                "status": "pending",
                "created_at": datetime.datetime.utcnow()
            }
        },
        upsert=True
    )

    config = {
        "server_ip": get_server_ip(),
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password": MQTT_PASSWORD,
        "port": MQTT_PORT,
        "mqtt_topic": mqtt_topic_uuid
    }

    return jsonify(config), 200

#@app.route("/api/enrollment", methods=["POST"])
#def enrollment():
#    token = request.headers.get("Authorization")
#    if not token:
#        return jsonify({"msg": "Missing token"}), 401

#    decoded = decode_token(token)
#    if not decoded:
#        return jsonify({"msg": "Invalid or expired token"}), 401

#    email = decoded["email"]
#    data = request.json

#    required_fields = ["server_ip", "mqtt_username", "mqtt_password", "port", "mqtt_topic", "mobile_ssid", "mobile_passcode"







@app.route("/api/enrollment", methods=["POST"])
def enrollment():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # ✅ Safe JSON parsing
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"msg": "Request body must be valid JSON"}), 400

    required_fields = [
        "server_ip",
        "mqtt_username",
        "mqtt_password",
        "port",
        "mqtt_topic",
        "mobile_ssid",
        "mobile_passcode"
    ]

    # ✅ Better missing-field check
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({
            "msg": "Missing required fields",
            "missing": missing
        }), 400

    # Validate 7-digit UUID
    mqtt_topic = data["mqtt_topic"]
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if topic is already in use by another user (in enrollments)
    existing_enrollment = enrollments_collection.find_one({"mqtt_topic": mqtt_topic})
    if existing_enrollment and existing_enrollment["email"] != email:
        return jsonify({"msg": "MQTT topic already in use by another user"}), 409
    
    # Same user, same topic: upgrade pending to full enrollment, or reject if already enrolled
    if existing_enrollment and existing_enrollment["email"] == email:
        if existing_enrollment.get("status") == "pending":
            used_topics_collection.update_one(
                {"mqtt_topic": mqtt_topic},
                {"$set": {"mqtt_topic": mqtt_topic, "enrolled": True, "enrolled_at": datetime.datetime.utcnow(), "enrolled_by": email}, "$setOnInsert": {"marked_at": datetime.datetime.utcnow()}},
                upsert=True
            )
            full_data = {"email": email, "server_ip": data["server_ip"], "mqtt_username": data["mqtt_username"], "mqtt_password": data["mqtt_password"], "port": data["port"], "mqtt_topic": mqtt_topic, "mobile_ssid": data["mobile_ssid"], "mobile_passcode": data["mobile_passcode"], "enrolled_at": datetime.datetime.utcnow()}
            enrollments_collection.update_one(
                {"email": email, "mqtt_topic": mqtt_topic},
                {"$set": full_data, "$unset": {"status": 1, "created_at": 1}}
            )
            return jsonify({"msg": "Device enrolled successfully"}), 201
        return jsonify({"msg": "Device already enrolled with this MQTT topic"}), 409

    # CRITICAL: Check if topic was ever ENROLLED before (not just generated)
    # First check if currently enrolled
    current_enrollment = enrollments_collection.find_one({"mqtt_topic": mqtt_topic})
    if current_enrollment:
        # Topic is currently enrolled by someone
        if current_enrollment["email"] != email:
            return jsonify({"msg": "MQTT topic already in use by another user"}), 409
        else:
            return jsonify({"msg": "Device already enrolled with this MQTT topic"}), 409
    
    # Check if topic was enrolled before (even if enrollment was deleted)
    # Only reject if it was actually enrolled, not just generated
    existing_used = used_topics_collection.find_one({"mqtt_topic": mqtt_topic, "enrolled": True})
    if existing_used:
        # Topic was enrolled before but enrollment was deleted - NEVER REUSE IT
        return jsonify({"msg": "MQTT topic was previously used and cannot be reused"}), 409

    # Mark topic as enrolled permanently (only when actually enrolled)
    used_topics_collection.update_one(
        {"mqtt_topic": mqtt_topic},
        {
            "$set": {
                "mqtt_topic": mqtt_topic,
                "enrolled": True,
                "enrolled_at": datetime.datetime.utcnow(),
                "enrolled_by": email
            },
            "$setOnInsert": {"marked_at": datetime.datetime.utcnow()}
        },
        upsert=True
    )

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
    enrollments = list(enrollments_collection.find({"email": email}, {"_id": 0}))

    # Check if each MQTT topic has a room bound to it
    devices = []
    for enrollment in enrollments:
        mqtt_topic = enrollment.get("mqtt_topic")
        
        # Check if there's a room bound to this MQTT topic
        room = rooms_collection.find_one({"mqtt_topic": mqtt_topic})
        
        enrollment_data = dict(enrollment)
        if room:
            enrollment_data["room"] = {
                "room_id": str(room["_id"]),
                "label": room.get("label"),
                "width_in": room.get("width_in"),
                "height_in": room.get("height_in"),
                "area_sqft": room.get("area_sqft"),
                "bound": True
            }
        else:
            enrollment_data["room"] = {
                "bound": False,
                "room_id": None,
                "label": None
            }
        
        devices.append(enrollment_data)

    return jsonify({"devices": devices}), 200


@app.route("/api/enrollment/<mqtt_topic>", methods=["PUT"])
def update_enrollment(mqtt_topic):
    """Update enrollment data for a specific MQTT topic"""
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

    # Check if enrollment exists and user owns it
    existing_enrollment = enrollments_collection.find_one({"mqtt_topic": mqtt_topic, "email": email})
    if not existing_enrollment:
        return jsonify({"msg": "Enrollment not found or you don't have access to this MQTT topic"}), 404

    # Get update data
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"msg": "Request body must be valid JSON"}), 400

    # Fields that can be updated
    updatable_fields = [
        "server_ip",
        "mqtt_username",
        "mqtt_password",
        "port",
        "mobile_ssid",
        "mobile_passcode"
    ]

    # Build update document (only include fields that are provided)
    update_data = {}
    for field in updatable_fields:
        if field in data:
            update_data[field] = data[field]

    if not update_data:
        return jsonify({"msg": "No valid fields to update"}), 400

    # Validate port if provided
    if "port" in update_data:
        try:
            port = int(update_data["port"])
            if port <= 0 or port > 65535:
                return jsonify({"msg": "Port must be between 1 and 65535"}), 400
            update_data["port"] = port
        except (TypeError, ValueError):
            return jsonify({"msg": "Port must be a valid integer"}), 400

    # Add updated timestamp
    update_data["updated_at"] = datetime.datetime.utcnow()

    # Update the enrollment
    result = enrollments_collection.update_one(
        {"mqtt_topic": mqtt_topic, "email": email},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        return jsonify({"msg": "No changes were made"}), 200

    # Return updated enrollment
    updated_enrollment = enrollments_collection.find_one(
        {"mqtt_topic": mqtt_topic, "email": email},
        {"_id": 0}
    )

    return jsonify({
        "msg": "Enrollment updated successfully",
        "enrollment": updated_enrollment
    }), 200


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

#@app.route("/api/mqtt/data", methods=["POST"])
#def store_mqtt_data():
#   
#    token = request.headers.get("Authorization")
#    if not token:
#        return jsonify({"msg": "Missing token"}), 401

#    decoded = decode_token(token)
#    if not decoded:
#        return jsonify({"msg": "Invalid or expired token"}), 401

#    email = decoded["email"]
#    data = request.json

#    required_fields = ["mqtt_topic", "device_id", "message", "timestamp"]
#    if not all(field in data for field in required_fields):
#        return jsonify({"msg": "Missing required fields: mqtt_topic, device_id, message, timestamp"}), 400

    
#    mqtt_topic = data["mqtt_topic"]
#    if not validate_7_digit_uuid(mqtt_topic):
#        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
#    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
#    if not user_enrollment:
#        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # Store MQTT data
#    mqtt_data = {
#        "email": email,
#        "mqtt_topic": mqtt_topic,
#        "device_id": data["device_id"],
#        "message": data["message"],
#        "timestamp": data["timestamp"],
#        "received_at": datetime.datetime.utcnow(),
#        "data_type": data.get("data_type", "sensor_data"),  # Optional field
#        "metadata": data.get("metadata", {})  # Optional field for additional data
#    }

#    mqtt_data_collection.insert_one(mqtt_data)
#    return jsonify({"msg": "MQTT data stored successfully"}), 201




@app.route("/api/mqtt/data", methods=["POST"])
def store_mqtt_data():
    """Store MQTT data received from devices (no token required)"""
    data = request.json or {}

    required_fields = ["mqtt_topic", "device_id", "message", "timestamp"]
    if not all(field in data for field in required_fields):
        return jsonify({"msg": "Missing required fields: mqtt_topic, device_id, message, timestamp"}), 400

    mqtt_topic = data["mqtt_topic"]

    # Validate 7-digit UUID
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Optional: If you still want to check ownership (optional step)
    # user_enrollment = enrollments_collection.find_one({"mqtt_topic": mqtt_topic})
    # if not user_enrollment:
    #     return jsonify({"msg": "Unknown or unregistered MQTT topic"}), 403

    # Store MQTT data directly
    mqtt_data = {
        "mqtt_topic": mqtt_topic,
        "device_id": data["device_id"],
        "message": data["message"],
        "timestamp": data["timestamp"],
        "received_at": datetime.datetime.utcnow(),
        "data_type": data.get("data_type", "sensor_data"),
        "metadata": data.get("metadata", {})
    }

    mqtt_data_collection.insert_one(mqtt_data)
    return jsonify({"msg": "MQTT data stored successfully"}), 201






from flask import send_from_directory

@app.route("/uploads/<path:filename>", methods=["GET"])
def get_uploaded_file(filename):
    # Consider auth if images are private
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=False)

























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

@app.route("/api/rooms", methods=["POST"])
def create_room():
    """
    Create a rectangular room using four sides (inches):
    A0_A1, A1_A2, A2_A3, A3_A0, label, mqtt_topic, and optional image.
    
    Expects multipart/form-data:
      - A0_A1 (string/number)
      - A1_A2 (string/number)
      - A2_A3 (string/number)
      - A3_A0 (string/number)
      - label (string)
      - mqtt_topic (string, required) - 7-digit MQTT topic to bind to this room
      - image (file, optional: jpg/jpeg/png)
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Get form data
    a0_a1_val = request.form.get("A0_A1")
    a1_a2_val = request.form.get("A1_A2")
    a2_a3_val = request.form.get("A2_A3")
    a3_a0_val = request.form.get("A3_A0")
    label = request.form.get("label")
    mqtt_topic = request.form.get("mqtt_topic")
    image_file = request.files.get("image")

    # Validate required fields
    required_fields = {"A0_A1": a0_a1_val, "A1_A2": a1_a2_val, "A2_A3": a2_a3_val, "A3_A0": a3_a0_val, "label": label, "mqtt_topic": mqtt_topic}
    missing = [k for k, v in required_fields.items() if v is None]
    if missing:
        return jsonify({"msg": "Missing required fields", "missing": missing}), 400

    # Validate MQTT topic
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # CRITICAL: Check if MQTT topic is already bound to another room
    existing_room = rooms_collection.find_one({"mqtt_topic": mqtt_topic})
    if existing_room:
        existing_room_id = str(existing_room["_id"])
        existing_room_label = existing_room.get("label", "Unknown")
        return jsonify({
            "msg": "MQTT topic is already bound to another room",
            "bound_to_room_id": existing_room_id,
            "bound_to_room_label": existing_room_label
        }), 409

    # Parse numeric values
    try:
        a0_a1 = float(a0_a1_val)
        a1_a2 = float(a1_a2_val)
        a2_a3 = float(a2_a3_val)
        a3_a0 = float(a3_a0_val)
    except (TypeError, ValueError):
        return jsonify({"msg": "All A*_A* fields must be numeric"}), 400

    # Basic positive check
    sides = [a0_a1, a1_a2, a2_a3, a3_a0]
    if any(s <= 0 for s in sides):
        return jsonify({"msg": "All sides must be positive"}), 400

    # Optional: range check (198–29800 inches)
    for s in sides:
        if s < 198 or s > 29800:
            return jsonify({"msg": "Each side must be between 198 and 29800 inches"}), 400

    # Assume rectangle: opposite sides equal
    tol = 1e-6
    if abs(a0_a1 - a2_a3) > tol or abs(a1_a2 - a3_a0) > tol:
        return jsonify({
            "msg": "Room must be rectangular (A0_A1 == A2_A3 and A1_A2 == A3_A0)"
        }), 400

    width_in = a0_a1      # along X (A0 → A1)
    height_in = a1_a2     # along Y (A0 → A3)
    area_sqft = (width_in * height_in) / 144.0

    # Handle image upload (optional)
    image_filename = None
    if image_file:
        def _allowed_image(filename: str) -> bool:
            if not filename or "." not in filename:
                return False
            return filename.rsplit(".", 1)[1].lower() in {"jpg", "jpeg", "png"}

        filename = secure_filename(image_file.filename or "")
        if not _allowed_image(filename):
            return jsonify({"msg": "Image must be JPG or PNG"}), 400

        # Save file
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        ext = filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(uploads_dir, unique_name)

        try:
            image_file.save(save_path)
            image_filename = unique_name
        except Exception as e:
            return jsonify({"msg": f"Failed to save image: {str(e)}"}), 500

    room_doc = {
        "email": email,
        "label": label,
        "A0_A1": a0_a1,
        "A1_A2": a1_a2,
        "A2_A3": a2_a3,
        "A3_A0": a3_a0,
        "width_in": width_in,
        "height_in": height_in,
        "area_sqft": area_sqft,
        "mqtt_topic": mqtt_topic,  # Bind MQTT topic to this room
        "created_at": datetime.datetime.utcnow()
    }

    # Add image filename if provided
    if image_filename:
        room_doc["image_file"] = image_filename

    result = rooms_collection.insert_one(room_doc)

    response_data = {
        "msg": "Room created successfully",
        "room_id": str(result.inserted_id),
        "width_in": width_in,
        "height_in": height_in,
        "area_sqft": round(area_sqft, 4),
        "label": label,
        "mqtt_topic": mqtt_topic,
        "image_file": image_filename,
        "image_url": f"http://{get_server_ip()}/uploads/{image_filename}" if image_filename else None
    }

    return jsonify(response_data), 201




@app.route("/api/rooms", methods=["GET"])
def list_rooms():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    rooms = []
    for r in rooms_collection.find({"email": email}):
        image_file = r.get("image_file")
        rooms.append({
            "room_id": str(r["_id"]),
            "label": r.get("label"),
            "width_in": r.get("width_in"),
            "height_in": r.get("height_in"),
            "area_sqft": r.get("area_sqft"),
            "mqtt_topic": r.get("mqtt_topic"),
            "image_file": image_file,
            "image_url": f"http://{get_server_ip()}/uploads/{image_file}" if image_file else None,
            "created_at": r.get("created_at").isoformat() if r.get("created_at") else None
        })

    return jsonify({"rooms": rooms}), 200


@app.route("/api/rooms/<room_id>", methods=["GET"])
def get_room_details(room_id):
    """Get detailed information about a specific room by room_id"""
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Validate ObjectId
    try:
        room_oid = ObjectId(room_id)
    except Exception:
        return jsonify({"msg": "Invalid room_id"}), 400

    # Get room
    room = rooms_collection.find_one({"_id": room_oid})
    if not room:
        return jsonify({"msg": "Room not found"}), 404

    # Check if user owns this room
    if room.get("email") != email:
        return jsonify({"msg": "You don't have access to this room"}), 403

    # Build response with all room details
    image_file = room.get("image_file")
    room_data = {
        "room_id": str(room["_id"]),
        "label": room.get("label"),
        "A0_A1": room.get("A0_A1"),
        "A1_A2": room.get("A1_A2"),
        "A2_A3": room.get("A2_A3"),
        "A3_A0": room.get("A3_A0"),
        "width_in": room.get("width_in"),
        "height_in": room.get("height_in"),
        "area_sqft": room.get("area_sqft"),
        "mqtt_topic": room.get("mqtt_topic"),
        "image_file": image_file,
        "image_url": f"http://{get_server_ip()}/uploads/{image_file}" if image_file else None,
        "created_at": room.get("created_at").isoformat() if room.get("created_at") else None,
        "updated_at": room.get("updated_at").isoformat() if room.get("updated_at") else None
    }

    return jsonify(room_data), 200


@app.route("/api/rooms/<room_id>", methods=["PUT"])
def update_room_details(room_id):
    """
    Update room details by room_id.
    
    Body (multipart/form-data or JSON):
    {
        "label": "New Room Name",  // Optional
        "A0_A1": 1200,             // Optional - if provided, all A*_A* must be provided
        "A1_A2": 800,              // Optional
        "A2_A3": 1200,             // Optional
        "A3_A0": 800,              // Optional
        "image": <file>            // Optional - new image file
    }
    
    Note: If updating dimensions, all four sides (A0_A1, A1_A2, A2_A3, A3_A0) must be provided.
    MQTT topic cannot be changed after room creation.
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    # Validate ObjectId
    try:
        room_oid = ObjectId(room_id)
    except Exception:
        return jsonify({"msg": "Invalid room_id"}), 400

    # Get existing room
    room = rooms_collection.find_one({"_id": room_oid})
    if not room:
        return jsonify({"msg": "Room not found"}), 404

    # Check if user owns this room
    if room.get("email") != email:
        return jsonify({"msg": "You don't have access to this room"}), 403

    # Get update data (support both form-data and JSON)
    update_data = {}
    
    # Try form data first (for image uploads)
    if request.form:
        label = request.form.get("label")
        a0_a1_val = request.form.get("A0_A1")
        a1_a2_val = request.form.get("A1_A2")
        a2_a3_val = request.form.get("A2_A3")
        a3_a0_val = request.form.get("A3_A0")
        image_file = request.files.get("image")
    else:
        # Try JSON
        data = request.get_json(silent=True) or {}
        label = data.get("label")
        a0_a1_val = data.get("A0_A1")
        a1_a2_val = data.get("A1_A2")
        a2_a3_val = data.get("A2_A3")
        a3_a0_val = data.get("A3_A0")
        image_file = None

    # Update label if provided
    if label is not None:
        update_data["label"] = label

    # Update dimensions if provided (all four sides must be provided together)
    if any([a0_a1_val, a1_a2_val, a2_a3_val, a3_a0_val]):
        if not all([a0_a1_val, a1_a2_val, a2_a3_val, a3_a0_val]):
            return jsonify({
                "msg": "If updating dimensions, all four sides (A0_A1, A1_A2, A2_A3, A3_A0) must be provided"
            }), 400

        try:
            a0_a1 = float(a0_a1_val)
            a1_a2 = float(a1_a2_val)
            a2_a3 = float(a2_a3_val)
            a3_a0 = float(a3_a0_val)
        except (TypeError, ValueError):
            return jsonify({"msg": "All A*_A* fields must be numeric"}), 400

        # Basic positive check
        sides = [a0_a1, a1_a2, a2_a3, a3_a0]
        if any(s <= 0 for s in sides):
            return jsonify({"msg": "All sides must be positive"}), 400

        # Range check (198–29800 inches)
        for s in sides:
            if s < 198 or s > 29800:
                return jsonify({"msg": "Each side must be between 198 and 29800 inches"}), 400

        # Assume rectangle: opposite sides equal
        tol = 1e-6
        if abs(a0_a1 - a2_a3) > tol or abs(a1_a2 - a3_a0) > tol:
            return jsonify({
                "msg": "Room must be rectangular (A0_A1 == A2_A3 and A1_A2 == A3_A0)"
            }), 400

        width_in = a0_a1
        height_in = a1_a2
        area_sqft = (width_in * height_in) / 144.0

        update_data["A0_A1"] = a0_a1
        update_data["A1_A2"] = a1_a2
        update_data["A2_A3"] = a2_a3
        update_data["A3_A0"] = a3_a0
        update_data["width_in"] = width_in
        update_data["height_in"] = height_in
        update_data["area_sqft"] = area_sqft

    # Handle image upload (optional)
    if image_file:
        def _allowed_image(filename: str) -> bool:
            if not filename or "." not in filename:
                return False
            return filename.rsplit(".", 1)[1].lower() in {"jpg", "jpeg", "png"}

        filename = secure_filename(image_file.filename or "")
        if not _allowed_image(filename):
            return jsonify({"msg": "Image must be JPG or PNG"}), 400

        # Save file
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)

        # Delete old image if exists
        old_image = room.get("image_file")
        if old_image:
            old_image_path = os.path.join(uploads_dir, old_image)
            try:
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
            except Exception:
                pass  # Ignore errors deleting old image

        ext = filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        save_path = os.path.join(uploads_dir, unique_name)

        try:
            image_file.save(save_path)
            update_data["image_file"] = unique_name
        except Exception as e:
            return jsonify({"msg": f"Failed to save image: {str(e)}"}), 500

    # If no updates provided
    if not update_data:
        return jsonify({"msg": "No fields to update"}), 400

    # Add updated timestamp
    update_data["updated_at"] = datetime.datetime.utcnow()

    # Update the room
    result = rooms_collection.update_one(
        {"_id": room_oid},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        return jsonify({"msg": "No changes were made"}), 200

    # Get updated room
    updated_room = rooms_collection.find_one({"_id": room_oid})

    # Build response
    image_file = updated_room.get("image_file")
    response_data = {
        "msg": "Room updated successfully",
        "room_id": str(updated_room["_id"]),
        "label": updated_room.get("label"),
        "width_in": updated_room.get("width_in"),
        "height_in": updated_room.get("height_in"),
        "area_sqft": updated_room.get("area_sqft"),
        "mqtt_topic": updated_room.get("mqtt_topic"),
        "image_file": image_file,
        "image_url": f"http://{get_server_ip()}/uploads/{image_file}" if image_file else None,
        "updated_at": updated_room.get("updated_at").isoformat() if updated_room.get("updated_at") else None
    }

    return jsonify(response_data), 200


@app.route("/api/visualize", methods=["POST"])
def visualize_position():
    """
    Compute tag positions using real-time MQTT data and calculations from main.py.

    Body:
    {
        "room_id": "PUT_ROOM_ID_HERE",
        "mqtt_topic": "1000087"
    }
    
    Fetches latest MQTT data for the topic and calculates positions for all tags.
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id")
    mqtt_topic = data.get("mqtt_topic")

    if not room_id:
        return jsonify({"msg": "room_id is required"}), 400
    
    if not mqtt_topic:
        return jsonify({"msg": "mqtt_topic is required"}), 400

    # Validate ObjectId
    try:
        room_oid = ObjectId(room_id)
    except Exception:
        return jsonify({"msg": "Invalid room_id"}), 400

    # Validate MQTT topic
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Get room
    room = rooms_collection.find_one({"_id": room_oid})
    if not room:
        return jsonify({"msg": "Room not found"}), 404

    if room.get("email") != email:
        return jsonify({"msg": "You don't have access to this room"}), 403

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # Get room dimensions
    width = float(room.get("width_in", 0))
    height = float(room.get("height_in", 0))
    if width <= 0 or height <= 0:
        return jsonify({"msg": "Room has invalid dimensions"}), 500

    # Anchor positions (in inches) - same as main.py
    # A0 = (0, 0)
    # A1 = (width, 0)
    # A2 = (width, height)
    # A3 = (0, height)
    anchor_positions = [
        (0, 0),           # A0
        (width, 0),       # A1
        (width, height),  # A2
        (0, height)       # A3
    ]

    # Fetch latest MQTT data for this topic
    # Try both field names: "topic" and "mqtt_topic", and "data" and "message"
    # Sort by timestamp (ts, received_at, or timestamp field)
    mqtt_records = list(mqtt_data_collection.find(
        {"$or": [{"mqtt_topic": mqtt_topic}, {"topic": mqtt_topic}]}
    ).sort([("ts", -1), ("received_at", -1), ("timestamp", -1)]).limit(100))  # Get latest 100 records

    if not mqtt_records:
        return jsonify({"msg": "No MQTT data found for this topic"}), 404

    # Parse MQTT data and group by tag ID
    tag_data = {}  # {tag_id: {"range": [r0, r1, r2, r3, ...], "timestamp": ...}}
    
    for record in mqtt_records:
        # Handle both field name formats
        data_str = record.get("data") or record.get("message", "")
        if not data_str:
            continue
        
        try:
            tag_info = json.loads(data_str)
            tag_id = tag_info.get("id")
            ranges = tag_info.get("range", [])
            
            if tag_id is not None and isinstance(ranges, list) and len(ranges) >= 4:
                # Keep only the latest data for each tag
                if tag_id not in tag_data:
                    timestamp = record.get("ts") or record.get("received_at") or record.get("timestamp")
                    tag_data[tag_id] = {
                        "range": ranges,
                        "timestamp": timestamp
                    }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            continue  # Skip invalid records

    if not tag_data:
        return jsonify({"msg": "No valid tag data found in MQTT records"}), 404

    # Calculate positions using helper function
    tag_positions, error = calculate_tag_positions(mqtt_topic, room, email)
    if error:
        return jsonify({"msg": error}), 404 if "not found" in error.lower() else 400

    width = float(room.get("width_in", 0))
    height = float(room.get("height_in", 0))

    return jsonify({
        "msg": "Positions computed",
        "room_id": room_id,
        "label": room.get("label"),
        "mqtt_topic": mqtt_topic,
        "room_dimensions_in": {
            "width_in": width,
            "height_in": height
        },
        "anchor_positions": {
            "A0": {"x": 0, "y": 0},
            "A1": {"x": width, "y": 0},
            "A2": {"x": width, "y": height},
            "A3": {"x": 0, "y": height}
        },
        "tag_positions": tag_positions,
        "tag_count": len(tag_positions)
    }), 200






@app.route("/api/test/dummy-mqtt-data", methods=["POST"])
def create_dummy_mqtt_data():
    """
    Create dummy MQTT data for testing the visualize endpoint.
    For testing purposes, this endpoint will auto-create enrollment if it doesn't exist.
    
    Body:
    {
        "mqtt_topic": "1000087",
        "tag_count": 2,  // Optional, default 2
        "ranges": {      // Optional, if not provided uses random values
            "0": [25, 28, 29, 30, 0, 0, 0, 0],
            "1": [69, 50, 53, 74, 0, 0, 0, 0]
        },
        "auto_enroll": true  // Optional, default true - auto-create enrollment for testing
    }
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    data = request.get_json(silent=True) or {}
    mqtt_topic = data.get("mqtt_topic")
    tag_count = int(data.get("tag_count", 2))
    custom_ranges = data.get("ranges", {})
    auto_enroll = data.get("auto_enroll", True)  # Default to True for testing

    if not mqtt_topic:
        return jsonify({"msg": "mqtt_topic is required"}), 400

    # Validate MQTT topic
    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    # Check if user has access to this MQTT topic
    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    
    # Auto-create enrollment for testing if it doesn't exist
    if not user_enrollment and auto_enroll:
        # Check if topic was ever enrolled before
        existing_used = used_topics_collection.find_one({"mqtt_topic": mqtt_topic, "enrolled": True})
        if existing_used:
            return jsonify({
                "msg": "MQTT topic was previously used and cannot be reused. Use a different topic for testing."
            }), 409
        
        # Create a test enrollment
        test_enrollment = {
            "email": email,
            "server_ip": get_server_ip(),
            "mqtt_username": MQTT_USERNAME,
            "mqtt_password": MQTT_PASSWORD,
            "port": MQTT_PORT,
            "mqtt_topic": mqtt_topic,
            "mobile_ssid": "test_ssid",
            "mobile_passcode": "test_passcode",
            "enrolled_at": datetime.datetime.utcnow(),
            "test_enrollment": True  # Mark as test enrollment
        }
        enrollments_collection.insert_one(test_enrollment)
        
        # Mark topic as enrolled
        used_topics_collection.update_one(
            {"mqtt_topic": mqtt_topic},
            {
                "$set": {
                    "mqtt_topic": mqtt_topic,
                    "enrolled": True,
                    "enrolled_at": datetime.datetime.utcnow(),
                    "enrolled_by": email
                },
                "$setOnInsert": {"marked_at": datetime.datetime.utcnow()}
            },
            upsert=True
        )
        
        user_enrollment = test_enrollment
    
    if not user_enrollment:
        return jsonify({
            "msg": "You don't have access to this MQTT topic. Set 'auto_enroll': true to auto-create enrollment for testing."
        }), 403

    # Generate dummy data
    inserted_records = []
    current_time = datetime.datetime.utcnow()

    # Default ranges for testing (in inches, simulating realistic distances)
    default_ranges = {
        "0": [25, 28, 29, 30, 0, 0, 0, 0],  # Tag 0 - close to A0
        "1": [69, 50, 53, 74, 0, 0, 0, 0],  # Tag 1 - middle of room
        "2": [100, 120, 110, 95, 0, 0, 0, 0],  # Tag 2 - far from A0
    }

    for tag_id in range(tag_count):
        tag_id_str = str(tag_id)
        
        # Use custom ranges if provided, otherwise use defaults or generate random
        if tag_id_str in custom_ranges:
            ranges = custom_ranges[tag_id_str]
        elif tag_id_str in default_ranges:
            ranges = default_ranges[tag_id_str]
        else:
            # Generate random realistic ranges (50-200 inches)
            import random
            ranges = [
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200),
                random.randint(50, 200),
                0, 0, 0, 0
            ]

        # Create MQTT data record (matching the format you showed)
        tag_data = {
            "id": tag_id,
            "range": ranges
        }

        # Insert into mqtt_data collection with both field name formats for compatibility
        mqtt_record = {
            "topic": mqtt_topic,  # Your format
            "mqtt_topic": mqtt_topic,  # Standard format
            "data": json.dumps(tag_data),  # Your format
            "message": json.dumps(tag_data),  # Standard format
            "device_id": f"tag_{tag_id}",
            "ts": current_time,  # Your format
            "timestamp": current_time.isoformat(),  # Standard format
            "received_at": current_time,  # Standard format
            "data_type": "uwb_tag_data",
            "metadata": {
                "tag_id": tag_id,
                "test_data": True
            }
        }

        result = mqtt_data_collection.insert_one(mqtt_record)
        inserted_records.append({
            "tag_id": tag_id,
            "ranges": ranges,
            "record_id": str(result.inserted_id)
        })

    return jsonify({
        "msg": f"Created {len(inserted_records)} dummy MQTT records",
        "mqtt_topic": mqtt_topic,
        "records": inserted_records,
        "timestamp": current_time.isoformat()
    }), 201


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


@app.route("/api/mqtt/data/<mqtt_topic>/history", methods=["GET"])
def get_mqtt_history(mqtt_topic):
    """
    Get historical MQTT data for a specific topic with optional date/time filtering.

    Query Parameters:
    - start_date (optional): Start datetime in ISO format (e.g., "2024-01-15T00:00:00")
    - end_date (optional): End datetime in ISO format (e.g., "2024-01-15T23:59:59")
    - tag_id (optional): Filter by specific tag ID (e.g., 0, 1, 2)
    - page (optional): Page number for pagination (default: 1)
    - per_page (optional): Records per page (default: 100, max: 1000)
    - include_positions (optional): Include calculated x,y positions (default: true)

    If no date filters provided, returns all available data (paginated).
    """
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

    # Get query parameters
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    tag_id = request.args.get("tag_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 100, type=int)
    include_positions = request.args.get("include_positions", "true").lower() == "true"

    # Validate pagination
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 1
    if per_page > 1000:
        per_page = 1000

    # Build query
    query = {"$or": [{"mqtt_topic": mqtt_topic}, {"topic": mqtt_topic}]}

    # Parse and add date filters
    date_filter = {}
    if start_date_str:
        try:
            start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            date_filter["$gte"] = start_date
        except ValueError:
            return jsonify({"msg": "Invalid start_date format. Use ISO format: YYYY-MM-DDTHH:MM:SS"}), 400

    if end_date_str:
        try:
            end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            date_filter["$lte"] = end_date
        except ValueError:
            return jsonify({"msg": "Invalid end_date format. Use ISO format: YYYY-MM-DDTHH:MM:SS"}), 400

    if date_filter:
        query["$or"] = [
            {"received_at": date_filter},
            {"ts": date_filter},
            {"timestamp": date_filter}
        ]
        # Rebuild query to include both topic and date filters
        query = {
            "$and": [
                {"$or": [{"mqtt_topic": mqtt_topic}, {"topic": mqtt_topic}]},
                {"$or": [
                    {"received_at": date_filter},
                    {"ts": date_filter}
                ]}
            ]
        }

    # Get total count for pagination
    total_count = mqtt_data_collection.count_documents(query)
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1

    # Get paginated data
    skip = (page - 1) * per_page
    mqtt_records = list(mqtt_data_collection.find(query).sort([
        ("ts", -1),
        ("received_at", -1),
        ("timestamp", -1)
    ]).skip(skip).limit(per_page))

    # Get room for position calculation if needed
    room = rooms_collection.find_one({"mqtt_topic": mqtt_topic, "email": email})

    # Process records
    results = []
    for record in mqtt_records:
        # Parse tag data from the record
        data_str = record.get("data") or record.get("message", "")
        tag_info = None
        parsed_tag_id = None
        ranges = []

        if data_str:
            try:
                tag_info = json.loads(data_str)
                parsed_tag_id = tag_info.get("id")
                ranges = tag_info.get("range", [])
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Filter by tag_id if specified
        if tag_id is not None and parsed_tag_id != tag_id:
            continue

        # Get timestamp
        timestamp = record.get("ts") or record.get("received_at") or record.get("timestamp")
        if hasattr(timestamp, 'isoformat'):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp) if timestamp else None

        result_item = {
            "record_id": str(record.get("_id")),
            "tag_id": parsed_tag_id,
            "ranges": {
                "A0": ranges[0] if len(ranges) > 0 else None,
                "A1": ranges[1] if len(ranges) > 1 else None,
                "A2": ranges[2] if len(ranges) > 2 else None,
                "A3": ranges[3] if len(ranges) > 3 else None
            },
            "raw_ranges": ranges,
            "timestamp": timestamp_str,
            "device_id": record.get("device_id"),
            "data_type": record.get("data_type")
        }

        # Calculate position if room exists and positions requested
        if include_positions and room and len(ranges) >= 4:
            width = float(room.get("width_in", 0))
            height = float(room.get("height_in", 0))

            if width > 0 and height > 0:
                anchor_positions = [
                    (0, 0),           # A0
                    (width, 0),       # A1
                    (width, height),  # A2
                    (0, height)       # A3
                ]

                # Get valid distances
                distances = [(i, r) for i, r in enumerate(ranges[:4]) if r > 0]

                if len(distances) >= 3:
                    distances.sort(key=lambda x: x[1])
                    selected_ids = [distances[i][0] for i in range(3)]

                    x_sum, y_sum, count = 0.0, 0.0, 0
                    for i in range(3):
                        for j in range(i + 1, 3):
                            a_id, b_id = selected_ids[i], selected_ids[j]
                            a_x, a_y = anchor_positions[a_id]
                            b_x, b_y = anchor_positions[b_id]
                            temp_x, temp_y = three_point_calculation(a_x, a_y, b_x, b_y, ranges[a_id], ranges[b_id])
                            x_sum += temp_x
                            y_sum += temp_y
                            count += 1

                    if count > 0:
                        x = max(0.0, min(width, x_sum / count))
                        y = max(0.0, min(height, y_sum / count))

                        result_item["position"] = {
                            "x": round(x, 2),
                            "y": round(y, 2),
                            "x_normalized": round(x / width, 4) if width > 0 else None,
                            "y_normalized": round(y / height, 4) if height > 0 else None,
                            "selected_anchors": [f"A{id}" for id in selected_ids]
                        }
                    else:
                        result_item["position"] = None
                else:
                    result_item["position"] = None
            else:
                result_item["position"] = None
        elif include_positions:
            result_item["position"] = None

        results.append(result_item)

    # Build response
    response = {
        "mqtt_topic": mqtt_topic,
        "data": results,
        "count": len(results),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "filters": {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "tag_id": tag_id,
            "include_positions": include_positions
        }
    }

    # Add room info if available
    if room:
        image_file = room.get("image_file")
        response["room"] = {
            "room_id": str(room.get("_id")),
            "label": room.get("label"),
            "width_in": room.get("width_in"),
            "height_in": room.get("height_in"),
            "image_file": image_file,
            "image_url": f"http://{get_server_ip()}/uploads/{image_file}" if image_file else None
        }

    return jsonify(response), 200


@app.route("/api/mqtt/data/<mqtt_topic>/history/by-date", methods=["GET"])
def get_mqtt_history_by_date(mqtt_topic):
    """
    Get historical MQTT data filtered by a specific date and optional hour.

    Query Parameters:
    - date (required): Date in YYYY-MM-DD format (e.g., "2026-02-24")
    - hour (optional): Hour 0-23 to filter a specific hour of that date
    - tag_id (optional): Filter by specific tag ID (e.g., 0, 1, 2)
    - page (optional): Page number (default: 1)
    - per_page (optional): Records per page (default: 100, max: 1000)
    - include_positions (optional): Include calculated x,y positions (default: true)
    """
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"msg": "Missing token"}), 401

    decoded = decode_token(token)
    if not decoded:
        return jsonify({"msg": "Invalid or expired token"}), 401

    email = decoded["email"]

    if not validate_7_digit_uuid(mqtt_topic):
        return jsonify({"msg": "Invalid MQTT topic. Must be a 7-digit number"}), 400

    user_enrollment = enrollments_collection.find_one({"email": email, "mqtt_topic": mqtt_topic})
    if not user_enrollment:
        return jsonify({"msg": "You don't have access to this MQTT topic"}), 403

    # --- Parameters ---
    date_str      = request.args.get("date")
    hour          = request.args.get("hour", type=int)
    tag_id        = request.args.get("tag_id", type=int)
    page          = max(1, request.args.get("page", 1, type=int))
    per_page      = min(1000, max(1, request.args.get("per_page", 100, type=int)))
    include_positions = request.args.get("include_positions", "true").lower() == "true"

    if not date_str:
        return jsonify({"msg": "date is required (format: YYYY-MM-DD)"}), 400

    try:
        parsed_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"msg": "Invalid date format. Use YYYY-MM-DD"}), 400

    if hour is not None and not (0 <= hour <= 23):
        return jsonify({"msg": "hour must be between 0 and 23"}), 400

    # Build time window
    if hour is not None:
        range_start = parsed_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        range_end   = parsed_date.replace(hour=hour, minute=59, second=59, microsecond=999999)
    else:
        range_start = parsed_date.replace(hour=0,  minute=0,  second=0,  microsecond=0)
        range_end   = parsed_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    date_filter = {"$gte": range_start, "$lte": range_end}

    query = {
        "$and": [
            {"$or": [{"mqtt_topic": mqtt_topic}, {"topic": mqtt_topic}]},
            {"$or": [{"ts": date_filter}, {"received_at": date_filter}]}
        ]
    }

    total_count = mqtt_data_collection.count_documents(query)
    total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
    skip = (page - 1) * per_page

    mqtt_records = list(mqtt_data_collection.find(query)
                        .sort([("ts", -1), ("received_at", -1)])
                        .skip(skip).limit(per_page))

    room = rooms_collection.find_one({"mqtt_topic": mqtt_topic, "email": email})

    results = []
    for record in mqtt_records:
        data_str = record.get("data") or record.get("message", "")
        parsed_tag_id = None
        ranges = []

        if data_str:
            try:
                tag_info = json.loads(data_str)
                parsed_tag_id = tag_info.get("id")
                ranges = tag_info.get("range", [])
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        if tag_id is not None and parsed_tag_id != tag_id:
            continue

        timestamp = record.get("ts") or record.get("received_at") or record.get("timestamp")
        timestamp_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp) if timestamp else None

        item = {
            "record_id": str(record.get("_id")),
            "tag_id": parsed_tag_id,
            "ranges": {
                "A0": ranges[0] if len(ranges) > 0 else None,
                "A1": ranges[1] if len(ranges) > 1 else None,
                "A2": ranges[2] if len(ranges) > 2 else None,
                "A3": ranges[3] if len(ranges) > 3 else None
            },
            "raw_ranges": ranges,
            "timestamp": timestamp_str
        }

        if include_positions and room and len(ranges) >= 4:
            width  = float(room.get("width_in", 0))
            height = float(room.get("height_in", 0))
            if width > 0 and height > 0:
                anchor_positions = [(0,0),(width,0),(width,height),(0,height)]
                distances = [(i, r) for i, r in enumerate(ranges[:4]) if r > 0]
                if len(distances) >= 3:
                    distances.sort(key=lambda x: x[1])
                    sel = [distances[i][0] for i in range(3)]
                    xs, ys, cnt = 0.0, 0.0, 0
                    for i in range(3):
                        for j in range(i+1, 3):
                            ax, ay = anchor_positions[sel[i]]
                            bx, by = anchor_positions[sel[j]]
                            tx, ty = three_point_calculation(ax, ay, bx, by, ranges[sel[i]], ranges[sel[j]])
                            xs += tx; ys += ty; cnt += 1
                    if cnt > 0:
                        x = max(0.0, min(width,  xs / cnt))
                        y = max(0.0, min(height, ys / cnt))
                        item["position"] = {
                            "x": round(x, 2),
                            "y": round(y, 2),
                            "x_normalized": round(x / width,  4),
                            "y_normalized": round(y / height, 4),
                            "selected_anchors": [f"A{i}" for i in sel]
                        }
                    else:
                        item["position"] = None
                else:
                    item["position"] = None
            else:
                item["position"] = None
        elif include_positions:
            item["position"] = None

        results.append(item)

    response = {
        "mqtt_topic": mqtt_topic,
        "data": results,
        "count": len(results),
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "filters": {
            "date": date_str,
            "hour": hour,
            "time_window": {
                "from": range_start.isoformat(),
                "to":   range_end.isoformat()
            },
            "tag_id": tag_id,
            "include_positions": include_positions
        }
    }

    if room:
        image_file = room.get("image_file")
        response["room"] = {
            "room_id": str(room.get("_id")),
            "label": room.get("label"),
            "width_in": room.get("width_in"),
            "height_in": room.get("height_in"),
            "image_file": image_file,
            "image_url": f"http://{get_server_ip()}/uploads/{image_file}" if image_file else None
        }

    return jsonify(response), 200




# ====== INITIALIZATION ======
def backfill_used_emails():
    """
    Backfill used_emails collection with existing emails from users collection.
    This ensures all existing emails are marked as used.
    This function ONLY READS from users_collection and WRITES to used_emails_collection.
    It NEVER deletes or modifies existing data.
    """
    try:
        existing_users = list(users_collection.find({}, {"email": 1}))
        print(f"Backfilling {len(existing_users)} existing emails...")
        
        backfilled_count = 0
        for user in existing_users:
            email = user.get("email", "").lower().strip()
            if email:
                result = used_emails_collection.update_one(
                    {"email": email},
                    {"$setOnInsert": {"email": email, "marked_at": datetime.datetime.utcnow()}},
                    upsert=True
                )
                if result.upserted_id:
                    backfilled_count += 1
        
        print(f"✓ Backfilled {backfilled_count} new emails into used_emails collection")
    except Exception as e:
        print(f"⚠ Warning: Could not backfill used emails: {e}")
        import traceback
        traceback.print_exc()

def backfill_used_topics():
    """
    Backfill used_topics collection with existing topics from enrollments collection.
    This ensures all existing MQTT topics are marked as enrolled.
    This function ONLY READS from enrollments_collection and WRITES to used_topics_collection.
    It NEVER deletes or modifies existing data.
    """
    try:
        # Only backfill fully enrolled topics (skip pending so they are not marked enrolled in used_topics)
        existing_enrollments = list(enrollments_collection.find(
            {"$or": [{"status": {"$exists": False}}, {"status": {"$ne": "pending"}}]},
            {"mqtt_topic": 1, "email": 1, "enrolled_at": 1}
        ))
        print(f"Backfilling {len(existing_enrollments)} existing MQTT topics...")

        backfilled_count = 0
        for enrollment in existing_enrollments:
            topic = enrollment.get("mqtt_topic", "").strip()
            if topic and validate_7_digit_uuid(topic):
                enrolled_at = enrollment.get("enrolled_at", datetime.datetime.utcnow())
                enrolled_by = enrollment.get("email", "")
                result = used_topics_collection.update_one(
                    {"mqtt_topic": topic},
                    {
                        "$set": {
                            "mqtt_topic": topic,
                            "enrolled": True,
                            "enrolled_at": enrolled_at,
                            "enrolled_by": enrolled_by
                        },
                        "$setOnInsert": {"marked_at": datetime.datetime.utcnow()}
                    },
                    upsert=True
                )
                if result.upserted_id or result.modified_count > 0:
                    backfilled_count += 1
        
        print(f"✓ Backfilled {backfilled_count} topics into used_topics collection (marked as enrolled)")
    except Exception as e:
        print(f"⚠ Warning: Could not backfill used topics: {e}")
        import traceback
        traceback.print_exc()

# Backfill on startup (only when server actually starts)
def initialize_server():
    """Initialize server - backfill collections with existing data"""
    print("\n" + "="*50)
    print("Initializing UWB Server...")
    print("="*50)
    backfill_used_emails()
    backfill_used_topics()
    print("="*50 + "\n")

# ====== WEBSOCKET ENDPOINTS ======

# Store active WebSocket connections
active_connections = {}

@socketio.on('connect')
def handle_connect(auth=None):
    """Handle WebSocket connection - accepts token from query string or auth"""
    # Try to get token from query string first (easier for Postman)
    token = request.args.get('token')
    
    # If not in query, try auth object
    if not token and auth:
        token = auth.get('token')
    
    # If still no token, try from headers (for nginx proxy)
    if not token:
        token = request.headers.get('Authorization')
    
    if not token:
        print("WebSocket connection rejected: No token provided")
        disconnect()
        return False
    
    decoded = decode_token(token)
    if not decoded:
        print("WebSocket connection rejected: Invalid token")
        disconnect()
        return False
    
    email = decoded["email"]
    active_connections[request.sid] = {
        "email": email,
        "room_id": None,
        "mqtt_topic": None,
        "active": True
    }
    emit('connected', {'msg': 'Connected successfully', 'email': email})
    print(f"WebSocket connected: {email} (sid: {request.sid})")
    return True

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    if request.sid in active_connections:
        email = active_connections[request.sid].get("email")
        del active_connections[request.sid]
        print(f"WebSocket disconnected: {email} (sid: {request.sid})")

@socketio.on('start_visualization')
def handle_start_visualization(data):
    """
    Start real-time visualization for a room and MQTT topic.
    
    Expected data:
    {
        "room_id": "67890abcdef1234567890123",
        "mqtt_topic": "1000087",
        "update_interval": 0.5  // Optional, default 0.5 seconds
    }
    """
    if request.sid not in active_connections:
        emit('error', {'msg': 'Not authenticated'})
        return
    
    conn = active_connections[request.sid]
    email = conn["email"]
    
    room_id = data.get("room_id")
    mqtt_topic = data.get("mqtt_topic")
    update_interval = float(data.get("update_interval", 0.5))
    
    if not room_id or not mqtt_topic:
        emit('error', {'msg': 'room_id and mqtt_topic are required'})
        return
    
    # Validate room_id
    try:
        room_oid = ObjectId(room_id)
    except Exception:
        emit('error', {'msg': 'Invalid room_id'})
        return
    
    # Validate MQTT topic
    if not validate_7_digit_uuid(mqtt_topic):
        emit('error', {'msg': 'Invalid MQTT topic. Must be a 7-digit number'})
        return
    
    # Get room
    room = rooms_collection.find_one({"_id": room_oid})
    if not room:
        emit('error', {'msg': 'Room not found'})
        return
    
    if room.get("email") != email:
        emit('error', {'msg': "You don't have access to this room"})
        return
    
    # Store connection info
    conn["room_id"] = room_id
    conn["mqtt_topic"] = mqtt_topic
    conn["update_interval"] = update_interval
    conn["room"] = room
    
    emit('visualization_started', {
        'msg': 'Visualization started',
        'room_id': room_id,
        'mqtt_topic': mqtt_topic,
        'update_interval': update_interval
    })

    # Capture sid before starting thread (request context won't be available in thread)
    client_sid = request.sid

    # Start background thread for updates
    def send_updates(sid):
        while sid in active_connections and active_connections[sid].get("active"):
            try:
                conn = active_connections.get(sid)
                if not conn or not conn.get("room_id"):
                    break

                room_data = conn["room"]
                topic = conn["mqtt_topic"]
                user_email = conn["email"]

                # Calculate positions
                tag_positions, error = calculate_tag_positions(topic, room_data, user_email)

                if error:
                    socketio.emit('error', {'msg': error}, to=sid)
                else:
                    width = float(room_data.get("width_in", 0))
                    height = float(room_data.get("height_in", 0))

                    socketio.emit('position_update', {
                        'timestamp': datetime.datetime.utcnow().isoformat(),
                        'room_id': conn["room_id"],
                        'mqtt_topic': topic,
                        'room_dimensions_in': {
                            'width_in': width,
                            'height_in': height
                        },
                        'anchor_positions': {
                            'A0': {'x': 0, 'y': 0},
                            'A1': {'x': width, 'y': 0},
                            'A2': {'x': width, 'y': height},
                            'A3': {'x': 0, 'y': height}
                        },
                        'tag_positions': tag_positions,
                        'tag_count': len(tag_positions)
                    }, to=sid)

                time.sleep(update_interval)
            except Exception as e:
                try:
                    socketio.emit('error', {'msg': f'Update error: {str(e)}'}, to=sid)
                except:
                    pass
                time.sleep(update_interval)

    thread = threading.Thread(target=send_updates, args=(client_sid,), daemon=True)
    thread.start()

@socketio.on('stop_visualization')
def handle_stop_visualization():
    """Stop real-time visualization"""
    if request.sid in active_connections:
        active_connections[request.sid]["active"] = False
        active_connections[request.sid]["room_id"] = None
        active_connections[request.sid]["mqtt_topic"] = None
        emit('visualization_stopped', {'msg': 'Visualization stopped'})

# ====== RUN ======
if __name__ == "__main__":
    # Only run initialization when server actually starts
    initialize_server()
    print("Starting Flask server with WebSocket support...")
    print("\n" + "="*60)
    print("WebSocket Connection URLs:")
    print("="*60)
    print("Direct (port 5000): ws://15.204.231.252:5000/?token=YOUR_TOKEN")
    print("Through nginx (port 80): ws://15.204.231.252:80/?token=YOUR_TOKEN")
    print("="*60)
    print("\n⚠️  If port 5000 connection fails, try port 80 (nginx proxy)")
    print("⚠️  Make sure firewall allows port 5000: sudo ufw allow 5000/tcp")
    print("="*60 + "\n")
    
    # Try to run on port 5000, but also support port 80 if nginx is configured
    try:
        socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True, debug=False)
    except OSError as e:
        if "Address already in use" in str(e) or "address already in use" in str(e).lower():
            print(f"\n⚠️  Port 5000 is already in use. Trying port 8080...")
            print("   Connect to: ws://15.204.231.252:8080/?token=YOUR_TOKEN\n")
            socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True, debug=False)
        else:
            raise

