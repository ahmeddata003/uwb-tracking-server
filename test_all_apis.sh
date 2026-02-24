#!/bin/bash
# UWB Tracking API - Complete Test Suite

BASE_URL="http://localhost:80"
TOKEN=""
ROOM_ID=""
MQTT_TOPIC="7777001"

echo "========================================"
echo "    UWB TRACKING API - TEST SUITE"
echo "========================================"

# 1. Health Check
echo -e "\n[1] HEALTH CHECK"
curl -s "$BASE_URL/" | tee /tmp/test1.json
echo ""

# 2. Signup
echo -e "\n[2] SIGNUP"
curl -s -X POST "$BASE_URL/api/signup" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"testapi77@test.com","password":"SecurePass123"}' | tee /tmp/test2.json
echo ""

# 3. Login
echo -e "\n[3] LOGIN"
curl -s -X POST "$BASE_URL/api/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"testapi77@test.com","password":"SecurePass123"}' | tee /tmp/test3.json
TOKEN=$(cat /tmp/test3.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
echo -e "\nToken: ${TOKEN:0:50}..."

# 4. Verify Token
echo -e "\n[4] VERIFY TOKEN"
curl -s "$BASE_URL/api/verify" -H "Authorization: $TOKEN" | tee /tmp/test4.json
echo ""

# 5. Config Mode
echo -e "\n[5] CONFIG MODE"
curl -s "$BASE_URL/api/config_mode" -H "Authorization: $TOKEN" | tee /tmp/test5.json
echo ""

# 6. Enroll Device
echo -e "\n[6] ENROLL DEVICE"
curl -s -X POST "$BASE_URL/api/enrollment" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"mqtt_topic\":\"$MQTT_TOPIC\",\"broker\":\"test.mosquitto.org\",\"server_ip\":\"15.204.231.252\",\"mqtt_username\":\"test\",\"mqtt_password\":\"test\",\"port\":\"1883\",\"mobile_ssid\":\"TestWiFi\",\"mobile_passcode\":\"wifi123\"}" | tee /tmp/test6.json
echo ""

# 7. List Enrollments
echo -e "\n[7] LIST ENROLLMENTS"
curl -s "$BASE_URL/api/enrollments" -H "Authorization: $TOKEN" | tee /tmp/test7.json
echo ""

# 8. Update Enrollment
echo -e "\n[8] UPDATE ENROLLMENT"
curl -s -X PUT "$BASE_URL/api/enrollment/$MQTT_TOPIC" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"broker":"broker.hivemq.com"}' | tee /tmp/test8.json
echo ""

# 9. Get Devices
echo -e "\n[9] GET DEVICES BY TOPIC"
curl -s "$BASE_URL/api/devices/$MQTT_TOPIC" -H "Authorization: $TOKEN" | tee /tmp/test9.json
echo ""

# 10. Create Room
echo -e "\n[10] CREATE ROOM"
curl -s -X POST "$BASE_URL/api/rooms" \
  -H "Authorization: $TOKEN" \
  -F "A0_A1=800" -F "A1_A2=600" -F "A2_A3=800" -F "A3_A0=600" \
  -F "label=Test Room 77" -F "mqtt_topic=$MQTT_TOPIC" | tee /tmp/test10.json
ROOM_ID=$(cat /tmp/test10.json | python3 -c "import sys,json; print(json.load(sys.stdin).get('room_id',''))" 2>/dev/null)
echo -e "\nRoom ID: $ROOM_ID"

# 11. List Rooms
echo -e "\n[11] LIST ROOMS"
curl -s "$BASE_URL/api/rooms" -H "Authorization: $TOKEN" | tee /tmp/test11.json
echo ""

# 12. Get Room Details
echo -e "\n[12] GET ROOM DETAILS"
curl -s "$BASE_URL/api/rooms/$ROOM_ID" -H "Authorization: $TOKEN" | tee /tmp/test12.json
echo ""

# 13. Update Room
echo -e "\n[13] UPDATE ROOM"
curl -s -X PUT "$BASE_URL/api/rooms/$ROOM_ID" \
  -H "Authorization: $TOKEN" \
  -F "label=Updated Room Name" | tee /tmp/test13.json
echo ""

# 14. Create Dummy MQTT Data
echo -e "\n[14] CREATE DUMMY MQTT DATA"
curl -s -X POST "$BASE_URL/api/test/dummy-mqtt-data" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"mqtt_topic\":\"$MQTT_TOPIC\",\"tag_count\":3,\"auto_enroll\":true}" | tee /tmp/test14.json
echo ""

# 15. Store MQTT Data (No Auth)
echo -e "\n[15] STORE MQTT DATA (No Auth Required)"
curl -s -X POST "$BASE_URL/api/mqtt/data" \
  -H "Content-Type: application/json" \
  -d "{\"mqtt_topic\":\"$MQTT_TOPIC\",\"tag_id\":0,\"ranges\":[100,120,110,130,0,0,0,0]}" | tee /tmp/test15.json
echo ""

# 16. Get MQTT Data
echo -e "\n[16] GET MQTT DATA BY TOPIC"
curl -s "$BASE_URL/api/mqtt/data/$MQTT_TOPIC" -H "Authorization: $TOKEN" | tee /tmp/test16.json
echo ""

# 17. Get Latest MQTT Data
echo -e "\n[17] GET LATEST MQTT DATA"
curl -s "$BASE_URL/api/mqtt/data/$MQTT_TOPIC/latest" -H "Authorization: $TOKEN" | tee /tmp/test17.json
echo ""

# 18. Get MQTT History
echo -e "\n[18] GET MQTT HISTORY"
curl -s "$BASE_URL/api/mqtt/data/$MQTT_TOPIC/history?limit=10" -H "Authorization: $TOKEN" | tee /tmp/test18.json
echo ""

# 19. Visualize Positions
echo -e "\n[19] VISUALIZE POSITIONS"
curl -s -X POST "$BASE_URL/api/visualize" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"room_id\":\"$ROOM_ID\",\"mqtt_topic\":\"$MQTT_TOPIC\"}" | tee /tmp/test19.json
echo ""

echo "========================================"
echo "    ALL TESTS COMPLETED!"
echo "========================================"
echo "Token: $TOKEN"
echo "Room ID: $ROOM_ID"
echo "MQTT Topic: $MQTT_TOPIC"

