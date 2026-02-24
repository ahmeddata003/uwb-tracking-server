# UWB Tracking Server — API Reference

**Base URL:** `http://15.204.231.252`  
**WebSocket URL:** `ws://15.204.231.252:8000`  
**Auth:** All protected endpoints require `Authorization: <token>` header  
**Token:** Obtained from `/api/login` — valid for 30 days

---

## Table of Contents

1. [Auth](#1-auth)
   - [Sign Up](#11-sign-up)
   - [Login](#12-login)
   - [Verify Token](#13-verify-token)
   - [Refresh Token](#14-refresh-token)
2. [Device Enrollment](#2-device-enrollment)
   - [Enroll Device](#21-enroll-device)
   - [Get My Enrollments](#22-get-my-enrollments)
   - [Get Device by Topic](#23-get-device-by-topic)
3. [Rooms](#3-rooms)
   - [Create Room](#31-create-room)
   - [List Rooms](#32-list-rooms)
   - [Get Room Details](#33-get-room-details)
   - [Update Room](#34-update-room)
4. [MQTT Data](#4-mqtt-data)
   - [Get Latest Data](#41-get-latest-data)
   - [History (Range Filter)](#42-history-range-filter)
   - [History by Date / Hour / Minute](#43-history-by-date)
5. [Visualization](#5-visualization)
   - [REST: Compute Position](#51-rest-compute-position)
   - [WebSocket: Live Tracking](#52-websocket-live-tracking)

---

## 1. Auth

### 1.1 Sign Up

**POST** `/api/signup`

```bash
curl -X POST http://15.204.231.252/api/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ahmed Ali",
    "email": "ahmed@example.com",
    "password": "mypassword123"
  }'
```

**Response `201`**
```json
{ "msg": "User registered successfully" }
```

**Error `409`** — Email already exists  
**Error `400`** — Missing fields

---

### 1.2 Login

**POST** `/api/login`

```bash
curl -X POST http://15.204.231.252/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "ahmed@example.com",
    "password": "mypassword123"
  }'
```

**Response `200`**
```json
{
  "msg": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

> **Save this token** — use it as `Authorization` header in all other requests.

---

### 1.3 Verify Token

**GET** `/api/verify`

```bash
curl -X GET http://15.204.231.252/api/verify \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{ "msg": "Token is valid", "email": "ahmed@example.com" }
```

---

### 1.4 Refresh Token

**POST** `/api/refresh`

```bash
curl -X POST http://15.204.231.252/api/refresh \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{ "msg": "Token refreshed", "token": "NEW_TOKEN_HERE" }
```

---

## 2. Device Enrollment

### 2.1 Enroll Device

**POST** `/api/enrollment`

Links a UWB device (identified by MQTT topic) to your account.

```bash
curl -X POST http://15.204.231.252/api/enrollment \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_ip": "15.204.231.252",
    "mqtt_username": "taha",
    "mqtt_password": "taha",
    "port": 1883,
    "mqtt_topic": "1000002",
    "mobile_ssid": "MyWifi",
    "mobile_passcode": "wifipassword"
  }'
```

**Response `201`**
```json
{ "msg": "Device enrolled successfully" }
```

**Error `409`** — Topic already in use  
**Error `400`** — Missing fields or invalid topic

> `mqtt_topic` must be a 7-digit number (e.g. `1000002`).

---

### 2.2 Get My Enrollments

**GET** `/api/enrollments`

```bash
curl -X GET http://15.204.231.252/api/enrollments \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{
  "enrollments": [
    {
      "mqtt_topic": "1000002",
      "server_ip": "15.204.231.252",
      "mqtt_username": "taha",
      "port": 1883,
      "mobile_ssid": "MyWifi",
      "enrolled_at": "2026-02-24T18:31:45.310000"
    }
  ],
  "count": 1
}
```

---

### 2.3 Get Device by Topic

**GET** `/api/devices/<mqtt_topic>`

```bash
curl -X GET http://15.204.231.252/api/devices/1000002 \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{
  "mqtt_topic": "1000002",
  "server_ip": "15.204.231.252",
  "enrolled_at": "2026-02-24T18:31:45.310000"
}
```

---

## 3. Rooms

### 3.1 Create Room

**POST** `/api/rooms`  
Content-Type: `multipart/form-data`

All 4 sides in **inches**. Must be a rectangle (A0_A1 == A2_A3, A1_A2 == A3_A0).

```bash
# Without image
curl -X POST http://15.204.231.252/api/rooms \
  -H "Authorization: YOUR_TOKEN" \
  -F "label=Main Hall" \
  -F "mqtt_topic=1000002" \
  -F "A0_A1=300" \
  -F "A1_A2=400" \
  -F "A2_A3=300" \
  -F "A3_A0=400"

# With floor plan image
curl -X POST http://15.204.231.252/api/rooms \
  -H "Authorization: YOUR_TOKEN" \
  -F "label=Main Hall" \
  -F "mqtt_topic=1000002" \
  -F "A0_A1=300" \
  -F "A1_A2=400" \
  -F "A2_A3=300" \
  -F "A3_A0=400" \
  -F "image=@/path/to/floorplan.jpg"
```

**Anchor layout:**
```
A3 -----(A3_A0)----- A0
|                    |
(A2_A3)           (A0_A1)
|                    |
A2 -----(A1_A2)----- A1
```

**Response `201`**
```json
{
  "msg": "Room created successfully",
  "room_id": "699df1d6f561133613233cd7",
  "label": "Main Hall",
  "mqtt_topic": "1000002",
  "width_in": 300.0,
  "height_in": 400.0,
  "area_sqft": 833.33,
  "image_url": "http://15.204.231.252/uploads/abc123.jpg"
}
```

> **Min side:** 198 inches (16.5 ft) | **Max side:** 29800 inches

---

### 3.2 List Rooms

**GET** `/api/rooms`

```bash
curl -X GET http://15.204.231.252/api/rooms \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{
  "rooms": [
    {
      "room_id": "699df1d6f561133613233cd7",
      "label": "Main Hall",
      "mqtt_topic": "1000002",
      "width_in": 300.0,
      "height_in": 400.0,
      "area_sqft": 833.33,
      "image_url": null,
      "created_at": "2026-02-24T18:45:42.305000"
    }
  ],
  "count": 1
}
```

---

### 3.3 Get Room Details

**GET** `/api/rooms/<room_id>`

```bash
curl -X GET http://15.204.231.252/api/rooms/699df1d6f561133613233cd7 \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{
  "room_id": "699df1d6f561133613233cd7",
  "label": "Main Hall",
  "mqtt_topic": "1000002",
  "width_in": 300.0,
  "height_in": 400.0,
  "area_sqft": 833.33,
  "A0_A1": 300.0,
  "A1_A2": 400.0,
  "A2_A3": 300.0,
  "A3_A0": 400.0,
  "image_url": null,
  "created_at": "2026-02-24T18:45:42.305000"
}
```

---

### 3.4 Update Room

**PUT** `/api/rooms/<room_id>`  
Content-Type: `multipart/form-data`

```bash
# Update label only
curl -X PUT http://15.204.231.252/api/rooms/699df1d6f561133613233cd7 \
  -H "Authorization: YOUR_TOKEN" \
  -F "label=Updated Room Name"

# Update with new floor plan image
curl -X PUT http://15.204.231.252/api/rooms/699df1d6f561133613233cd7 \
  -H "Authorization: YOUR_TOKEN" \
  -F "label=Updated Room" \
  -F "image=@/path/to/new_floorplan.jpg"
```

**Response `200`**
```json
{ "msg": "Room updated successfully" }
```

---

## 4. MQTT Data

### 4.1 Get Latest Data

**GET** `/api/mqtt/data/<mqtt_topic>/latest`

Returns the most recent message for each tag on this topic.

```bash
curl -X GET http://15.204.231.252/api/mqtt/data/1000002/latest \
  -H "Authorization: YOUR_TOKEN"
```

**Response `200`**
```json
{
  "mqtt_topic": "1000002",
  "device_count": 1,
  "latest_data": [...]
}
```

---

### 4.2 History (Range Filter)

**GET** `/api/mqtt/data/<mqtt_topic>/history`

Filter by datetime range with optional tag filter and pagination.

```bash
# All history (paginated)
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history?page=1&per_page=50" \
  -H "Authorization: YOUR_TOKEN"

# Filter by datetime range
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history?start_date=2026-02-24T00:00:00&end_date=2026-02-24T23:59:59" \
  -H "Authorization: YOUR_TOKEN"

# Filter by tag ID
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history?tag_id=1&per_page=100" \
  -H "Authorization: YOUR_TOKEN"

# Without position calculation (faster)
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history?include_positions=false" \
  -H "Authorization: YOUR_TOKEN"
```

**Query Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `start_date` | — | ISO datetime e.g. `2026-02-24T00:00:00` |
| `end_date` | — | ISO datetime e.g. `2026-02-24T23:59:59` |
| `tag_id` | — | Filter by tag (e.g. `0`, `1`) |
| `page` | `1` | Page number |
| `per_page` | `100` | Records per page (max 1000) |
| `include_positions` | `true` | Calculate X/Y positions |

---

### 4.3 History by Date

**GET** `/api/mqtt/data/<mqtt_topic>/history/by-date`

Flexible time filter — supports date only, date + hour, or date + hour + minute.

---

#### By date only (full 24 hours)

```bash
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24" \
  -H "Authorization: YOUR_TOKEN"
```

---

#### By date + hour (1-hour window)

```bash
# hour=23 → 11:00 PM to 11:59 PM
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24&hour=23" \
  -H "Authorization: YOUR_TOKEN"

# hour=9 → 9:00 AM to 9:59 AM
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24&hour=9" \
  -H "Authorization: YOUR_TOKEN"
```

---

#### By date + hour + minute (1-minute window)

```bash
# hour=23, minute=45 → 11:45 PM to 11:45:59 PM
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24&hour=23&minute=45" \
  -H "Authorization: YOUR_TOKEN"

# With tag filter
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24&hour=23&minute=45&tag_id=1" \
  -H "Authorization: YOUR_TOKEN"
```

---

#### All parameters combined

```bash
curl -X GET "http://15.204.231.252/api/mqtt/data/1000002/history/by-date?date=2026-02-24&hour=23&minute=45&tag_id=1&page=1&per_page=50" \
  -H "Authorization: YOUR_TOKEN"
```

---

**Query Parameters:**

| Parameter | Required | Example | Description |
|---|---|---|---|
| `date` | ✅ | `2026-02-24` | Full day — `YYYY-MM-DD` |
| `hour` | optional | `23` | Narrows to 1 hour (`0`–`23`) |
| `minute` | optional | `45` | Narrows to 1 minute (`0`–`59`) — requires `hour` |
| `tag_id` | optional | `1` | Filter by specific tag |
| `page` | optional | `1` | Page number (default `1`) |
| `per_page` | optional | `100` | Records per page (default `100`, max `1000`) |
| `include_positions` | optional | `true` | Include X/Y calculation (default `true`) |

> `minute` requires `hour` — returns error if used alone.

---

**Response `200`**
```json
{
  "mqtt_topic": "1000002",
  "count": 100,
  "data": [
    {
      "record_id": "699df52faa1ac7a5a02e267e",
      "tag_id": 1,
      "timestamp": "2026-02-24T23:45:32.623000",
      "ranges": { "A0": 65, "A1": 0, "A2": 95, "A3": 74 },
      "raw_ranges": [65, 0, 95, 74, 0, 0, 0, 0],
      "position": {
        "x": 84.41,
        "y": 249.85,
        "x_normalized": 0.2814,
        "y_normalized": 0.6246,
        "selected_anchors": ["A0", "A3", "A2"]
      }
    }
  ],
  "filters": {
    "date": "2026-02-24",
    "hour": 23,
    "minute": 45,
    "time_window": {
      "from": "2026-02-24T23:45:00",
      "to": "2026-02-24T23:45:59.999999"
    },
    "tag_id": null,
    "include_positions": true
  },
  "pagination": {
    "page": 1,
    "per_page": 100,
    "total_records": 87,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  },
  "room": {
    "room_id": "699df1d6f561133613233cd7",
    "label": "Main Hall",
    "width_in": 300.0,
    "height_in": 400.0,
    "image_url": "http://15.204.231.252/uploads/floorplan.jpg"
  }
}

```

---

## 5. Visualization

### 5.1 REST: Compute Position

**POST** `/api/visualize`

One-shot position calculation using latest MQTT data for a room.

```bash
curl -X POST http://15.204.231.252/api/visualize \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "699df1d6f561133613233cd7",
    "mqtt_topic": "1000002"
  }'
```

**Response `200`**
```json
{
  "msg": "Positions computed",
  "room_id": "699df1d6f561133613233cd7",
  "label": "Main Hall",
  "mqtt_topic": "1000002",
  "room_dimensions_in": { "width_in": 300.0, "height_in": 400.0 },
  "anchor_positions": {
    "A0": { "x": 0,     "y": 0   },
    "A1": { "x": 300.0, "y": 0   },
    "A2": { "x": 300.0, "y": 400.0 },
    "A3": { "x": 0,     "y": 400.0 }
  },
  "tag_count": 2,
  "tag_positions": {
    "0": {
      "x": 105.73, "y": 269.65,
      "x_normalized": 0.3524, "y_normalized": 0.6741,
      "status": true,
      "ranges": { "A0": 119, "A1": 0, "A2": 107, "A3": 121 },
      "selected_anchors": ["A2", "A0", "A3"],
      "timestamp": "2026-02-24T23:59:59.318000"
    },
    "1": {
      "x": 84.41, "y": 249.85,
      "x_normalized": 0.2814, "y_normalized": 0.6246,
      "status": true,
      "ranges": { "A0": 65, "A1": 0, "A2": 95, "A3": 74 },
      "selected_anchors": ["A0", "A3", "A2"],
      "timestamp": "2026-02-24T23:59:59.623000"
    }
  }
}
```

---

### 5.2 WebSocket: Live Tracking

Connect to the WebSocket server for real-time position updates every 0.5 seconds.

**Connection URL:** `ws://15.204.231.252:8000/?token=YOUR_TOKEN`

---

#### Step 1 — Connect

```bash
# Using wscat (npm install -g wscat)
wscat -c "ws://15.204.231.252:8000/?token=YOUR_TOKEN"
```

**Server sends:**
```json
{ "msg": "Connected successfully", "email": "ahmed@example.com" }
```

---

#### Step 2 — Start Visualization

Send this event after connecting:

```json
{
  "room_id": "699df1d6f561133613233cd7",
  "mqtt_topic": "1000002",
  "update_interval": 0.5
}
```

Event name: `start_visualization`

**Server confirms:**
```json
{
  "msg": "Visualization started",
  "room_id": "699df1d6f561133613233cd7",
  "mqtt_topic": "1000002",
  "update_interval": 0.5
}
```

---

#### Step 3 — Receive Live Updates

Server pushes `position_update` every 0.5 seconds:

```json
{
  "timestamp": "2026-02-24T23:55:22.510000",
  "room_id": "699df1d6f561133613233cd7",
  "mqtt_topic": "1000002",
  "room_dimensions_in": { "width_in": 300.0, "height_in": 400.0 },
  "anchor_positions": {
    "A0": { "x": 0,     "y": 0     },
    "A1": { "x": 300.0, "y": 0     },
    "A2": { "x": 300.0, "y": 400.0 },
    "A3": { "x": 0,     "y": 400.0 }
  },
  "tag_count": 2,
  "tag_positions": {
    "0": {
      "x": 145.5, "y": 323.1,
      "x_normalized": 0.485, "y_normalized": 0.808,
      "status": true,
      "ranges": { "A0": 38, "A1": 0, "A2": 40, "A3": 22 },
      "selected_anchors": ["A3", "A0", "A2"],
      "timestamp": "2026-02-24T23:55:22.270000"
    },
    "1": {
      "x": 98.1, "y": 270.0,
      "x_normalized": 0.327, "y_normalized": 0.675,
      "status": true,
      "ranges": { "A0": 36, "A1": 0, "A2": 38, "A3": 22 },
      "selected_anchors": ["A3", "A0", "A2"],
      "timestamp": "2026-02-24T23:55:22.430000"
    }
  }
}
```

---

#### Step 4 — Stop Visualization

Send event `stop_visualization` (no data needed).

**Server confirms:**
```json
{ "msg": "Visualization stopped" }
```

---

#### WebSocket Event Summary

| Event (send) | Description |
|---|---|
| `start_visualization` | Start live position stream |
| `stop_visualization` | Stop live position stream |

| Event (receive) | Description |
|---|---|
| `connected` | Auth success |
| `visualization_started` | Stream started |
| `position_update` | Live X/Y for all tags |
| `visualization_stopped` | Stream stopped |
| `error` | Something went wrong |

---

## Position Mapping for Mobile UI

Use `x_normalized` and `y_normalized` (values `0.0` to `1.0`) to place a tag dot on a floor plan image:

```
dot_pixel_x = x_normalized × image_width_px
dot_pixel_y = y_normalized × image_height_px
```

**Anchor corners on the floor plan:**

```
A3 (0, 1) -------- A2 (1, 1)
    |                    |
    |                    |
A0 (0, 0) -------- A1 (1, 0)
```

---

## Error Reference

| Code | Meaning |
|---|---|
| `400` | Bad request / missing fields |
| `401` | Missing or invalid token |
| `403` | No access to this topic or room |
| `404` | Resource not found |
| `409` | Conflict (email/topic already exists) |
| `500` | Server error |
