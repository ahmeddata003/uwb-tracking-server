# UWB Position Tracking API Documentation

## Overview

This API provides a complete backend system for Ultra-Wideband (UWB) indoor position tracking. It supports device enrollment, room configuration, real-time position calculation, and WebSocket-based live visualization.

## Server Information

| Property | Value |
|----------|-------|
| **Base URL** | `http://15.204.231.252` |
| **WebSocket URL** | `ws://15.204.231.252:8000` |
| **API Version** | 1.0 |

## Authentication

All protected endpoints require a JWT token in the `Authorization` header.

```
Authorization: <your_jwt_token>
```

Tokens are obtained via the Login endpoint and expire after a configurable period.

---

## 1. Authentication Endpoints

### 1.1 Health Check

Check if the API server is running.

**Endpoint:** `GET /`

**Authentication:** None required

**Response:**
```json
{
    "msg": "Standalone Auth API is running"
}
```

---

### 1.2 Sign Up

Register a new user account.

**Endpoint:** `POST /api/signup`

**Authentication:** None required

**Request Body:**
```json
{
    "name": "John Doe",
    "email": "john@example.com",
    "password": "SecurePassword123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | User's full name |
| email | string | Yes | Valid email address (unique) |
| password | string | Yes | Password (min 8 characters recommended) |

**Success Response (201):**
```json
{
    "msg": "User registered successfully"
}
```

**Error Responses:**
- `400` - Missing required fields
- `409` - Email already exists

---

### 1.3 Login

Authenticate and obtain a JWT token.

**Endpoint:** `POST /api/login`

**Authentication:** None required

**Request Body:**
```json
{
    "email": "john@example.com",
    "password": "SecurePassword123"
}
```

**Success Response (200):**
```json
{
    "msg": "Login successful",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Response (401):**
```json
{
    "msg": "Invalid credentials"
}
```

**Client integration:** After login (or on app start with an existing token), call **GET /api/enrollments** and **GET /api/rooms** and use the response as the source of truth for the user's topics and rooms. Do not rely only on in-memory or session storage so that data is preserved across re-login and restarts.

---

### 1.4 Verify Token

Verify if a JWT token is valid.

**Endpoint:** `GET /api/verify`

**Authentication:** Required

**Headers:**
```
Authorization: <jwt_token>
```

**Success Response (200):**
```json
{
    "msg": "Token is valid",
    "email": "john@example.com"
}
```

---

### 1.5 Get Config Mode

Get current MQTT configuration settings.

**Endpoint:** `GET /api/config_mode`

**Authentication:** Required

**Success Response (200):**
```json
{
    "mqtt_topic": "1000003",
    "mqtt_username": "user",
    "mqtt_password": "pass",
    "port": 1883,
    "server_ip": "15.204.231.252"
}
```

---

## 2. Device Enrollment Endpoints

### 2.1 Enroll Device

Enroll a new UWB device/anchor system.

**Endpoint:** `POST /api/enrollment`

**Authentication:** Required

**Request Body:**
```json
{
    "mqtt_topic": "1000001",
    "broker": "test.mosquitto.org",
    "server_ip": "15.204.231.252",
    "mqtt_username": "myuser",
    "mqtt_password": "mypass",
    "port": "1883",
    "mobile_ssid": "WiFi_Network",
    "mobile_passcode": "wifi_password"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| mqtt_topic | string | Yes | Unique identifier for device (e.g., "1000001") |
| broker | string | Yes | MQTT broker hostname |
| server_ip | string | Yes | Server IP for data transmission |
| mqtt_username | string | Yes | MQTT authentication username |
| mqtt_password | string | Yes | MQTT authentication password |
| port | string | Yes | MQTT broker port (usually "1883") |
| mobile_ssid | string | Yes | WiFi network name for device |
| mobile_passcode | string | Yes | WiFi password for device |

**Success Response (201):**
```json
{
    "msg": "Device enrolled successfully"
}
```

---

### 2.2 List Enrollments

Get all devices enrolled by the authenticated user (including topics reserved as **pending** when created via config mode; complete enrollment via POST /api/enrollment to activate).

**Endpoint:** `GET /api/enrollments`

**Authentication:** Required

**Success Response (200):**
```json
{
    "devices": [
        {
            "mqtt_topic": "1000001",
            "mqtt_username": "myuser",
            "mqtt_password": "mypass",
            "port": "1883",
            "server_ip": "15.204.231.252",
            "mobile_ssid": "WiFi_Network",
            "mobile_passcode": "wifi_password",
            "enrolled_at": "Mon, 05 Jan 2026 03:12:56 GMT",
            "email": "john@example.com",
            "room": {
                "bound": true,
                "room_id": "695b2c38b106433e76b326d9",
                "label": "Living Room"
            }
        }
    ]
}
```

Entries may include `"status": "pending"` when the topic was created via GET /api/config_mode but full enrollment has not been completed yet; the client can show "Complete setup to activate" for those.

---

### 2.3 Update Enrollment

Update enrollment configuration for a specific device.

**Endpoint:** `PUT /api/enrollment/{mqtt_topic}`

**Authentication:** Required

**Request Body (all fields optional):**
```json
{
    "broker": "new.broker.com",
    "mqtt_username": "newuser",
    "mqtt_password": "newpass",
    "port": "8883",
    "mobile_ssid": "New_WiFi",
    "mobile_passcode": "new_password"
}
```

**Success Response (200):**
```json
{
    "msg": "Enrollment updated successfully"
}
```

---

### 2.4 Get Devices by Topic

Get all devices enrolled under a specific MQTT topic.

**Endpoint:** `GET /api/devices/{mqtt_topic}`

**Authentication:** Required

**Success Response (200):**
```json
{
    "mqtt_topic": "1000001",
    "device_count": 1,
    "devices": [
        {
            "mqtt_topic": "1000001",
            "mqtt_username": "myuser",
            "enrolled_at": "Mon, 05 Jan 2026 03:12:56 GMT"
        }
    ]
}
```

---

## 3. Room Management Endpoints

### 3.1 Create Room

Create a new room for position tracking. Rooms are defined by four anchor distances.

**Endpoint:** `POST /api/rooms`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| A0_A1 | number | Yes | Distance (inches) between anchors A0 and A1 (bottom) |
| A1_A2 | number | Yes | Distance (inches) between anchors A1 and A2 (right) |
| A2_A3 | number | Yes | Distance (inches) between anchors A2 and A3 (top) |
| A3_A0 | number | Yes | Distance (inches) between anchors A3 and A0 (left) |
| label | string | Yes | Room name/label |
| mqtt_topic | string | Yes | Associated device MQTT topic |
| room_image | file | No | Floor plan image (PNG, JPG) |

**cURL Example:**
```bash
curl -X POST "http://15.204.231.252/api/rooms" \
  -H "Authorization: YOUR_TOKEN" \
  -F "A0_A1=800" \
  -F "A1_A2=600" \
  -F "A2_A3=800" \
  -F "A3_A0=600" \
  -F "label=Living Room" \
  -F "mqtt_topic=1000001"
```

**Success Response (201):**
```json
{
    "msg": "Room created successfully",
    "room_id": "695b2c38b106433e76b326d9",
    "label": "Living Room",
    "mqtt_topic": "1000001",
    "width_in": 800.0,
    "height_in": 600.0,
    "area_sqft": 3333.33,
    "image_file": "abc123def456.png",
    "image_url": "http://15.204.231.252/uploads/abc123def456.png"
}
```

> **Note:** `image_file` and `image_url` will be `null` if no image was uploaded.

**Room Layout:**
```
    A3 ─────────────── A2
    │                  │
    │    (Room Area)   │
    │                  │
    A0 ─────────────── A1
```

---

### 3.2 List Rooms

Get all rooms created by the authenticated user.

**Endpoint:** `GET /api/rooms`

**Authentication:** Required

**Success Response (200):**
```json
{
    "rooms": [
        {
            "room_id": "695b2c38b106433e76b326d9",
            "label": "Living Room",
            "mqtt_topic": "1000001",
            "width_in": 800.0,
            "height_in": 600.0,
            "area_sqft": 3333.33,
            "image_file": "abc123def456.png",
            "image_url": "http://15.204.231.252/uploads/abc123def456.png",
            "created_at": "2026-01-05T03:12:56.941000"
        }
    ]
}
```

---

### 3.3 Get Room Details

Get detailed information about a specific room.

**Endpoint:** `GET /api/rooms/{room_id}`

**Authentication:** Required

**Success Response (200):**
```json
{
    "room_id": "695b2c38b106433e76b326d9",
    "label": "Living Room",
    "mqtt_topic": "1000001",
    "A0_A1": 800.0,
    "A1_A2": 600.0,
    "A2_A3": 800.0,
    "A3_A0": 600.0,
    "width_in": 800.0,
    "height_in": 600.0,
    "area_sqft": 3333.33,
    "image_file": "abc123def456.png",
    "image_url": "http://15.204.231.252/uploads/abc123def456.png",
    "created_at": "2026-01-05T03:12:56.941000",
    "updated_at": null
}
```

---

### 3.4 Update Room

Update room configuration.

**Endpoint:** `PUT /api/rooms/{room_id}`

**Authentication:** Required

**Content-Type:** `multipart/form-data`

All fields are optional - only include fields you want to update.

**Success Response (200):**
```json
{
    "msg": "Room updated successfully",
    "room_id": "695b2c38b106433e76b326d9",
    "label": "Updated Room Name",
    "mqtt_topic": "1000001",
    "width_in": 800.0,
    "height_in": 600.0,
    "area_sqft": 3333.33,
    "image_file": "abc123def456.png",
    "image_url": "http://15.204.231.252/uploads/abc123def456.png",
    "updated_at": "2026-01-05T03:15:00.000000"
}
```

---

## 4. MQTT Data Endpoints

### 4.1 Store MQTT Data

Store incoming MQTT data from UWB devices. **No authentication required** - this endpoint is called by IoT devices.

**Endpoint:** `POST /api/mqtt/data`

**Authentication:** None (device endpoint)

**Request Body:**
```json
{
    "mqtt_topic": "1000001",
    "device_id": "tag_0",
    "message": "{\"id\": 0, \"range\": [100, 120, 110, 95, 0, 0, 0, 0]}",
    "timestamp": "2026-01-05T03:12:57.021003"
}
```

---

### 4.2 Get MQTT Data by Topic

Retrieve all MQTT data for a specific topic.

**Endpoint:** `GET /api/mqtt/data/{mqtt_topic}`

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | integer | 100 | Max records to return |
| device_id | string | null | Filter by device ID |
| data_type | string | null | Filter by data type |

**Success Response (200):**
```json
{
    "mqtt_topic": "1000001",
    "count": 3,
    "data": [
        {
            "device_id": "tag_0",
            "data_type": "uwb_tag_data",
            "message": "{\"id\": 0, \"range\": [100, 120, 110, 95, 0, 0, 0, 0]}",
            "timestamp": "2026-01-05T03:12:57.021003",
            "received_at": "Mon, 05 Jan 2026 03:12:57 GMT"
        }
    ]
}
```

---

### 4.3 Get Latest MQTT Data

Get the most recent MQTT data for each device.

**Endpoint:** `GET /api/mqtt/data/{mqtt_topic}/latest`

**Authentication:** Required

**Success Response (200):**
```json
{
    "mqtt_topic": "1000001",
    "device_count": 3,
    "latest_data": [
        {
            "device_id": "tag_0",
            "data_type": "uwb_tag_data",
            "message": "{\"id\": 0, \"range\": [100, 120, 110, 95]}",
            "timestamp": "2026-01-05T03:12:57.021003"
        },
        {
            "device_id": "tag_1",
            "message": "{\"id\": 1, \"range\": [69, 50, 53, 74]}"
        }
    ]
}
```

---

### 4.4 Get MQTT History

Get historical MQTT data with optional date filtering.

**Endpoint:** `GET /api/mqtt/data/{mqtt_topic}/history`

**Authentication:** Required

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| limit | integer | Max records (default: 100) |
| page | integer | Page number for pagination |
| start_date | string | Filter from date (YYYY-MM-DD) |
| end_date | string | Filter to date (YYYY-MM-DD) |
| tag_id | integer | Filter by tag ID |
| include_positions | boolean | Include calculated positions (default: true) |

**Example:**
```
GET /api/mqtt/data/1000001/history?limit=50&start_date=2026-01-01&include_positions=true
```

**Success Response (200):**
```json
{
    "mqtt_topic": "1000001",
    "count": 3,
    "data": [
        {
            "record_id": "695b2c393c4d958ab451fe60",
            "tag_id": 0,
            "device_id": "tag_0",
            "raw_ranges": [100, 120, 110, 95, 0, 0, 0, 0],
            "ranges": {"A0": 100, "A1": 120, "A2": 110, "A3": 95},
            "position": {
                "x": 515.91,
                "y": 190.84,
                "x_normalized": 0.6449,
                "y_normalized": 0.3181,
                "selected_anchors": ["A0", "A1", "A2"]
            },
            "timestamp": "2026-01-05T03:12:57.021000"
        }
    ],
    "room": {
        "room_id": "695b2c38b106433e76b326d9",
        "label": "Living Room",
        "width_in": 800.0,
        "height_in": 600.0
    },
    "pagination": {
        "page": 1,
        "per_page": 100,
        "total_records": 3,
        "total_pages": 1,
        "has_next": false,
        "has_prev": false
    }
}
```

---

### 4.5 Create Dummy MQTT Data (Testing)

Generate test MQTT data for development/testing purposes.

**Endpoint:** `POST /api/test/dummy-mqtt-data`

**Authentication:** Required

**Request Body:**
```json
{
    "mqtt_topic": "1000001",
    "tag_count": 3,
    "auto_enroll": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| mqtt_topic | string | Required | Target MQTT topic |
| tag_count | integer | 3 | Number of tags to simulate |
| auto_enroll | boolean | false | Auto-enroll device if not exists |

**Success Response (201):**
```json
{
    "msg": "Created 3 dummy MQTT records",
    "mqtt_topic": "1000001",
    "timestamp": "2026-01-05T03:12:57.021003",
    "records": [
        {"tag_id": 0, "record_id": "695b2c393c4d958ab451fe60", "ranges": [25, 28, 29, 30, 0, 0, 0, 0]},
        {"tag_id": 1, "record_id": "695b2c393c4d958ab451fe61", "ranges": [69, 50, 53, 74, 0, 0, 0, 0]},
        {"tag_id": 2, "record_id": "695b2c393c4d958ab451fe62", "ranges": [100, 120, 110, 95, 0, 0, 0, 0]}
    ]
}
```

---

## 5. Visualization Endpoints

### 5.1 Visualize Positions

Calculate and return current tag positions for a room.

**Endpoint:** `POST /api/visualize`

**Authentication:** Required

**Request Body:**
```json
{
    "room_id": "695b2c38b106433e76b326d9",
    "mqtt_topic": "1000001"
}
```

**Success Response (200):**
```json
{
    "msg": "Positions computed",
    "room_id": "695b2c38b106433e76b326d9",
    "label": "Living Room",
    "mqtt_topic": "1000001",
    "room_dimensions_in": {
        "width_in": 800.0,
        "height_in": 600.0
    },
    "anchor_positions": {
        "A0": {"x": 0, "y": 0},
        "A1": {"x": 800.0, "y": 0},
        "A2": {"x": 800.0, "y": 600.0},
        "A3": {"x": 0, "y": 600.0}
    },
    "tag_count": 3,
    "tag_positions": {
        "0": {
            "x": 515,
            "y": 190,
            "x_normalized": 0.64375,
            "y_normalized": 0.31667,
            "status": true,
            "ranges": {"A0": 25, "A1": 28, "A2": 29, "A3": 30},
            "selected_anchors": ["A0", "A1", "A2"],
            "timestamp": "2026-01-05T03:12:57.021000"
        },
        "1": {
            "x": 572,
            "y": 210,
            "x_normalized": 0.715,
            "y_normalized": 0.35,
            "status": true
        },
        "2": {
            "x": 250,
            "y": 397,
            "x_normalized": 0.3125,
            "y_normalized": 0.6617,
            "status": true
        }
    }
}
```

**Position Calculation:**
- Positions are calculated using trilateration from UWB range measurements
- The system automatically selects the 3 best anchors for each tag
- Coordinates are in inches, with (0,0) at anchor A0
- Normalized values (0-1) represent position as percentage of room dimensions

---

## 6. WebSocket API (Real-Time)

### Connection

Connect to the WebSocket server for real-time position updates.

**URL:** `ws://15.204.231.252:8000`

**Authentication:** Include token in connection query or auth object

**Socket.IO Client Example (JavaScript):**
```javascript
const socket = io('http://15.204.231.252:8000', {
    auth: { token: 'YOUR_JWT_TOKEN' },
    transports: ['websocket', 'polling']
});

// Or with query string
const socket = io('http://15.204.231.252:8000?token=YOUR_JWT_TOKEN');
```

---

### Events

#### `connect` → `connected`

On successful connection and authentication:

```javascript
socket.on('connected', (data) => {
    console.log(data);
    // { msg: 'Connected successfully', email: 'john@example.com' }
});
```

---

#### `start_visualization`

Start receiving position updates for a room.

**Emit:**
```javascript
socket.emit('start_visualization', {
    room_id: '695b2c38b106433e76b326d9',
    mqtt_topic: '1000001',
    update_interval: 0.5  // Optional, default 0.5 seconds
});
```

**Receive:**
```javascript
socket.on('visualization_started', (data) => {
    console.log(data);
    // { msg: 'Visualization started', room_id: '...', mqtt_topic: '...', update_interval: 0.5 }
});
```

---

#### `position_update`

Receive real-time position updates.

```javascript
socket.on('position_update', (data) => {
    console.log(data);
    /*
    {
        timestamp: '2026-01-05T03:12:57.021003',
        room_id: '695b2c38b106433e76b326d9',
        mqtt_topic: '1000001',
        room_dimensions_in: { width_in: 800.0, height_in: 600.0 },
        anchor_positions: {
            A0: { x: 0, y: 0 },
            A1: { x: 800, y: 0 },
            A2: { x: 800, y: 600 },
            A3: { x: 0, y: 600 }
        },
        tag_positions: {
            '0': { x: 515, y: 190, x_normalized: 0.64, y_normalized: 0.32, status: true },
            '1': { x: 572, y: 210, x_normalized: 0.72, y_normalized: 0.35, status: true }
        },
        tag_count: 2
    }
    */
});
```

---

#### `stop_visualization`

Stop receiving position updates.

**Emit:**
```javascript
socket.emit('stop_visualization');
```

**Receive:**
```javascript
socket.on('visualization_stopped', (data) => {
    console.log(data);
    // { msg: 'Visualization stopped' }
});
```

---

#### `error`

Receive error messages.

```javascript
socket.on('error', (data) => {
    console.error(data);
    // { msg: 'Error description' }
});
```

---

### Complete WebSocket Example

```javascript
const io = require('socket.io-client');

const socket = io('http://15.204.231.252:8000', {
    auth: { token: 'YOUR_JWT_TOKEN' }
});

socket.on('connect', () => console.log('Connected'));

socket.on('connected', (data) => {
    console.log('Authenticated:', data.email);

    // Start visualization
    socket.emit('start_visualization', {
        room_id: '695b2c38b106433e76b326d9',
        mqtt_topic: '1000001',
        update_interval: 0.5
    });
});

socket.on('position_update', (data) => {
    console.log(`Update at ${data.timestamp}:`);
    for (const [tagId, pos] of Object.entries(data.tag_positions)) {
        console.log(`  Tag ${tagId}: (${pos.x}, ${pos.y})`);
    }
});

socket.on('error', (data) => console.error('Error:', data.msg));

// Stop after 30 seconds
setTimeout(() => {
    socket.emit('stop_visualization');
    socket.disconnect();
}, 30000);
```

---

## 7. Error Handling

### Standard Error Response Format

All error responses follow this format:

```json
{
    "msg": "Error description"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created successfully |
| 400 | Bad request (invalid input) |
| 401 | Unauthorized (invalid/missing token) |
| 403 | Forbidden (no permission) |
| 404 | Not found |
| 409 | Conflict (e.g., duplicate email) |
| 500 | Internal server error |

---

## 8. Testing Guide

### Quick Start Testing

1. **Create User:**
```bash
curl -X POST http://15.204.231.252/api/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"Test123456"}'
```

2. **Login & Get Token:**
```bash
curl -X POST http://15.204.231.252/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123456"}'
```

3. **Enroll Device:**
```bash
curl -X POST http://15.204.231.252/api/enrollment \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mqtt_topic":"1000001","broker":"test.mosquitto.org","server_ip":"15.204.231.252","mqtt_username":"test","mqtt_password":"test","port":"1883","mobile_ssid":"WiFi","mobile_passcode":"pass"}'
```

4. **Create Room:**
```bash
curl -X POST http://15.204.231.252/api/rooms \
  -H "Authorization: YOUR_TOKEN" \
  -F "A0_A1=800" -F "A1_A2=600" -F "A2_A3=800" -F "A3_A0=600" \
  -F "label=Test Room" -F "mqtt_topic=1000001"
```

5. **Create Test Data:**
```bash
curl -X POST http://15.204.231.252/api/test/dummy-mqtt-data \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mqtt_topic":"1000001","tag_count":3,"auto_enroll":true}'
```

6. **Visualize Positions:**
```bash
curl -X POST http://15.204.231.252/api/visualize \
  -H "Authorization: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"room_id":"YOUR_ROOM_ID","mqtt_topic":"1000001"}'
```

### Test WebSocket

Open in browser: `http://15.204.231.252/websocket_test.html`

Or use the Python test script: `python test_websocket.py`

---

## 9. WebSocket Testing in Postman (Step-by-Step)

Postman supports Socket.IO connections. Follow these steps to test the WebSocket API:

### Step 1: Get Your JWT Token

First, login to get a token:

```bash
curl -X POST http://15.204.231.252/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}'
```

Copy the `token` from the response.

### Step 2: Create Socket.IO Request in Postman

1. Click **New** button (top-left corner)
2. Select **Socket.IO Request** (not WebSocket!)
3. A new Socket.IO tab opens

![Postman New Request](https://i.imgur.com/placeholder.png)

### Step 3: Configure Connection URL

Enter in the URL field:
```
http://15.204.231.252:8000
```

### Step 4: Configure Authentication

1. Click **Settings** tab (next to Events)
2. Under **Handshake**, find **Auth** section
3. Enter your token as JSON:

```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InlvdXJAZW1haWwuY29tIiwiZXhwIjoxNzY3NjY5MTc2fQ.xxxxx"
}
```

**Settings Screenshot Reference:**
```
┌─────────────────────────────────────────┐
│ Settings                                │
├─────────────────────────────────────────┤
│ Client version: [v4           ▼]        │
│ Handshake path: [/socket.io    ]        │
│                                         │
│ Handshake                               │
│ ├─ Auth                                 │
│ │  {"token": "eyJhbG..."}              │
│ └─ Headers                              │
└─────────────────────────────────────────┘
```

### Step 5: Add Event Listeners

1. Click **Events** tab
2. Click **+ Add** button for each event
3. Add these event listeners:

| Event Name | Description |
|------------|-------------|
| `connected` | Fires when authenticated successfully |
| `position_update` | Real-time tag positions (fires every update_interval) |
| `visualization_started` | Confirms visualization has started |
| `visualization_stopped` | Confirms visualization has stopped |
| `error` | Error messages from server |

**Events Tab Reference:**
```
┌─────────────────────────────────────────┐
│ Events                    [+ Add]       │
├─────────────────────────────────────────┤
│ ☑ connected                             │
│ ☑ position_update                       │
│ ☑ visualization_started                 │
│ ☑ visualization_stopped                 │
│ ☑ error                                 │
└─────────────────────────────────────────┘
```

### Step 6: Connect to Server

1. Click the **Connect** button
2. Status should change to "Connected"
3. You should see in the Messages panel:

```
← connected
{
    "msg": "Connected successfully",
    "email": "your@email.com"
}
```

### Step 7: Start Position Tracking

1. Click **Message** tab (bottom section)
2. Set **Event name**: `start_visualization`
3. Set **Message** (JSON format):

```json
{
    "room_id": "695b2c38b106433e76b326d9",
    "mqtt_topic": "1000001",
    "update_interval": 0.5
}
```

4. Click **Send**

**Message Tab Reference:**
```
┌─────────────────────────────────────────┐
│ Message                                 │
├─────────────────────────────────────────┤
│ Event name: [start_visualization    ]   │
│                                         │
│ Message (JSON):                         │
│ ┌─────────────────────────────────────┐ │
│ │ {                                   │ │
│ │   "room_id": "695b2c38...",        │ │
│ │   "mqtt_topic": "1000001",          │ │
│ │   "update_interval": 0.5            │ │
│ │ }                                   │ │
│ └─────────────────────────────────────┘ │
│                           [Send]        │
└─────────────────────────────────────────┘
```

### Step 8: Watch Real-Time Updates

You'll see position updates in the Messages panel:

```
← visualization_started
{
    "msg": "Visualization started",
    "room_id": "695b2c38b106433e76b326d9",
    "mqtt_topic": "1000001",
    "update_interval": 0.5
}

← position_update
{
    "timestamp": "2026-01-05T03:15:00.000000",
    "room_id": "695b2c38b106433e76b326d9",
    "room_dimensions_in": {"width_in": 800, "height_in": 600},
    "anchor_positions": {
        "A0": {"x": 0, "y": 0},
        "A1": {"x": 800, "y": 0},
        "A2": {"x": 800, "y": 600},
        "A3": {"x": 0, "y": 600}
    },
    "tag_positions": {
        "0": {"x": 515, "y": 190, "status": true},
        "1": {"x": 572, "y": 210, "status": true},
        "2": {"x": 250, "y": 397, "status": true}
    },
    "tag_count": 3
}

← position_update
{
    "timestamp": "2026-01-05T03:15:00.500000",
    ...tags at new positions (moving!)
}
```

### Step 9: Stop Visualization

1. **Event name**: `stop_visualization`
2. **Message**: `{}` (empty object)
3. Click **Send**

```
→ stop_visualization {}

← visualization_stopped
{
    "msg": "Visualization stopped"
}
```

### Step 10: Disconnect

Click **Disconnect** button to close the connection.

---

### Complete Postman WebSocket Test Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    POSTMAN SOCKET.IO TEST                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. URL: http://15.204.231.252:8000                        │
│                                                             │
│  2. Settings > Auth:                                        │
│     {"token": "eyJhbG..."}                                 │
│                                                             │
│  3. Events to listen:                                       │
│     ☑ connected                                             │
│     ☑ position_update                                       │
│     ☑ visualization_started                                 │
│     ☑ visualization_stopped                                 │
│     ☑ error                                                 │
│                                                             │
│  4. Click [Connect]                                         │
│     ← connected {"msg":"Connected successfully"}            │
│                                                             │
│  5. Send event: start_visualization                         │
│     → {"room_id":"...","mqtt_topic":"..."}                 │
│     ← visualization_started                                 │
│     ← position_update (every 0.5s)                         │
│     ← position_update                                       │
│     ← position_update                                       │
│                                                             │
│  6. Send event: stop_visualization                          │
│     → {}                                                    │
│     ← visualization_stopped                                 │
│                                                             │
│  7. Click [Disconnect]                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Troubleshooting WebSocket Issues

| Problem | Solution |
|---------|----------|
| "Connection refused" | Check server is running: `sudo systemctl status uwb-websocket` |
| "Not authenticated" | Token expired - get a new one via login |
| No position_update events | Run dummy data endpoint first, or check room_id/mqtt_topic |
| "Room not found" | Verify room_id exists with GET /api/rooms |
| Connection drops | Check network, token expiry, or server logs |

### Quick Test with Existing Data

Use these pre-configured test values:

```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6IndzdGVzdEB0ZXN0LmNvbSIsImV4cCI6MTc2NzY2ODE5N30.Ma738GfCJYyCgMg2mw4P6RCV0ldsmloODqJVdRKaeas",
    "room_id": "695b28c8c5a4b6ab3a80cbab",
    "mqtt_topic": "5000001"
}
```

---

## 11. Postman Collection

A complete Postman collection is available at:
`/home/ubuntu/final_server/UWB_Tracking_API.postman_collection.json`

### Import Instructions:
1. Open Postman
2. Click "Import" button
3. Select the JSON file
4. Collection variables will be auto-configured

### Collection Variables:
- `base_url`: http://15.204.231.252
- `ws_url`: ws://15.204.231.252:8000
- `token`: Auto-saved after login
- `room_id`: Auto-saved after room creation
- `mqtt_topic`: Auto-saved after enrollment

---

## 12. Rate Limits & Best Practices

### Recommendations:
- Cache JWT tokens (they're valid for extended periods)
- Use WebSocket for real-time data instead of polling `/api/visualize`
- Batch MQTT data if sending from multiple devices
- Use appropriate `update_interval` for WebSocket (0.5s default is good balance)

### Position Calculation Notes:
- Best results with 4 anchors placed at room corners
- Ensure clear line-of-sight between tags and anchors
- UWB range measurements are in inches
- System automatically selects best 3 anchors for trilateration

---

*Last Updated: January 2026*
*API Version: 1.0*

