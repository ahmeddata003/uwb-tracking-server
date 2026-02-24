#!/usr/bin/env python3
"""
WebSocket Server for UWB Real-Time Visualization
This script runs the Flask-SocketIO server on port 8000
"""
from final_server import app, socketio, initialize_server

if __name__ == '__main__':
    initialize_server()
    print("="*60)
    print("🛰️  UWB WebSocket Server")
    print("="*60)
    print("Server running on: http://0.0.0.0:8000")
    print("WebSocket URL: ws://15.204.231.252:8000")
    print("="*60)
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=8000, 
        allow_unsafe_werkzeug=True, 
        debug=False
    )

