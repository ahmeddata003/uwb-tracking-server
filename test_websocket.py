#!/usr/bin/env python3
"""
WebSocket Test Script for UWB Real-Time Visualization
"""
import socketio
import time
import sys

# Configuration
SERVER_URL = 'http://localhost:8000'
TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6IndzdGVzdEB0ZXN0LmNvbSIsImV4cCI6MTc2NzY2ODE5N30.Ma738GfCJYyCgMg2mw4P6RCV0ldsmloODqJVdRKaeas'
ROOM_ID = '695b28c8c5a4b6ab3a80cbab'
MQTT_TOPIC = '5000001'

# Create Socket.IO client
sio = socketio.Client(logger=False, engineio_logger=False)

@sio.event
def connect():
    print('✅ Connected to WebSocket server!')

@sio.event
def disconnect():
    print('❌ Disconnected from server')

@sio.on('connected')
def on_connected(data):
    print(f'✅ Authenticated: {data}')

@sio.on('visualization_started')
def on_visualization_started(data):
    print(f'✅ Visualization started: {data}')

@sio.on('visualization_stopped')
def on_visualization_stopped(data):
    print(f'⏹️ Visualization stopped: {data}')

@sio.on('position_update')
def on_position_update(data):
    print(f'\n📍 Position Update at {data.get("timestamp")}:')
    print(f'   Room: {data.get("room_id")}')
    print(f'   Tags: {data.get("tag_count")}')
    
    tag_positions = data.get('tag_positions', {})
    for tag_id, pos in tag_positions.items():
        if pos.get('status'):
            print(f'   Tag {tag_id}: x={pos.get("x"):.2f}, y={pos.get("y"):.2f} (normalized: {pos.get("x_normalized"):.4f}, {pos.get("y_normalized"):.4f})')
        else:
            print(f'   Tag {tag_id}: No position - {pos.get("error", "unknown")}')

@sio.on('error')
def on_error(data):
    print(f'❌ Error: {data}')

def main():
    print('='*60)
    print('🛰️  UWB WebSocket Real-Time Visualization Test')
    print('='*60)
    print(f'Server: {SERVER_URL}')
    print(f'Room ID: {ROOM_ID}')
    print(f'MQTT Topic: {MQTT_TOPIC}')
    print('='*60)
    
    try:
        print('\n🔌 Connecting to WebSocket server...')
        sio.connect(
            SERVER_URL,
            auth={'token': TOKEN},
            transports=['websocket', 'polling']
        )

        # Wait for connection to be fully established
        time.sleep(1)

        # Start visualization
        print(f'\n📡 Starting visualization for room: {ROOM_ID}, topic: {MQTT_TOPIC}')
        sio.emit('start_visualization', {
            'room_id': ROOM_ID,
            'mqtt_topic': MQTT_TOPIC,
            'update_interval': 1.0
        })

        # Wait for updates
        print('\n⏳ Waiting for position updates (Ctrl+C to stop)...\n')
        update_count = 0
        while update_count < 5:  # Get 5 updates then stop
            time.sleep(1)
            update_count += 1

        print('\n⏹️ Stopping visualization...')
        sio.emit('stop_visualization')
        time.sleep(1)
        
    except KeyboardInterrupt:
        print('\n\n⏹️ Interrupted by user')
    except Exception as e:
        print(f'\n❌ Error: {e}')
    finally:
        if sio.connected:
            sio.disconnect()
        print('\n✅ Test completed!')
        print('='*60)

if __name__ == '__main__':
    main()

