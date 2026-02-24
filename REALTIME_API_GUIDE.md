# UWB Real-Time API – Developer Guide

## What it is

Real-time tag positions are delivered over **Socket.IO** (WebSocket). Connect once, then receive `position_update` events at a fixed interval (e.g. every 0.5s).

---

## 1. Get a JWT token

```bash
# Login (use your credentials)
curl -X POST http://15.204.231.252/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}'
```

Use the `token` from the response in the next step.

---

## 2. Connect to the WebSocket

**URL:** `http://15.204.231.252:8000`  
**Auth:** Send your JWT when connecting.

**JavaScript (browser):**

```javascript
const socket = io('http://15.204.231.252:8000', {
  auth: { token: 'YOUR_JWT_TOKEN' },
  transports: ['websocket', 'polling']
});

socket.on('connected', (data) => {
  console.log('Connected:', data.email);
});

socket.on('position_update', (data) => {
  console.log('Tags:', data.tag_positions);
  console.log('Room size:', data.room_dimensions_in);
});

socket.on('error', (err) => console.error(err));
```

**Python:**

```python
import socketio

sio = socketio.Client()
sio.connect('http://15.204.231.252:8000', auth={'token': 'YOUR_JWT_TOKEN'})

@sio.on('connected')
def on_connected(data):
    print('Connected', data)

@sio.on('position_update')
def on_position(data):
    print('Tags:', data['tag_positions'])

@sio.on('error')
def on_error(err):
    print('Error', err)
```

---

## 3. Start receiving position updates

You need a **room_id** (from creating/fetching a room) and the **mqtt_topic** for that room.

Emit once:

```javascript
socket.emit('start_visualization', {
  room_id: '695b2c38b106433e76b326d9',   // your room's ObjectId
  mqtt_topic: '1000087',                   // 7-digit topic bound to that room
  update_interval: 0.5                     // optional, seconds between updates (default 0.5)
});
```

Listen for confirmation and updates:

```javascript
socket.on('visualization_started', () => {
  console.log('Stream started');
});

socket.on('position_update', (data) => {
  // data.tag_positions  -> { "0": { x, y, x_normalized, y_normalized, status }, ... }
  // data.room_dimensions_in, data.anchor_positions, data.tag_count
});
```

---

## 4. Stop updates

```javascript
socket.emit('stop_visualization');
```

---

## 5. Where the data comes from

- **Real data:** UWB devices POST to `POST /api/mqtt/data` (no auth). Same `mqtt_topic` and room. The real-time stream uses this stored data.
- **Testing without hardware:** Call `POST /api/test/dummy-mqtt-data` with `mqtt_topic` (and optional `tag_count`, `auto_enroll: true`) to insert fake MQTT records. Then start the WebSocket with that `mqtt_topic` and the room’s `room_id`.

---

## Quick reference

| Step              | Action |
|-------------------|--------|
| Auth              | `POST /api/login` → use `token` |
| Connect           | Socket.IO to `http://15.204.231.252:8000` with `auth: { token }` |
| Start stream      | `emit('start_visualization', { room_id, mqtt_topic, update_interval? })` |
| Receive           | `on('position_update', callback)` |
| Stop              | `emit('stop_visualization')` |

**Events from server:** `connected`, `visualization_started`, `position_update`, `visualization_stopped`, `error`.
