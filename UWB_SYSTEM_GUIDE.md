# 🛰️ UWB Indoor Position Tracking System

## Simple Guide for Everyone

---

# What is This System?

This system tracks the **real-time location of people or objects inside a room** using UWB (Ultra-Wideband) technology.

### Think of it like GPS, but for indoors!

```
    ┌────────────────────────────────────────────┐
    │                  ROOM                       │
    │                                             │
    │  📍A3                              📍A2     │
    │   (Anchor)                      (Anchor)    │
    │                                             │
    │                                             │
    │              🏃 Person                      │
    │              with Tag                       │
    │                                             │
    │                                             │
    │  📍A0                              📍A1     │
    │   (Anchor)                      (Anchor)    │
    │                                             │
    └────────────────────────────────────────────┘
```

---

# Key Components

## 1️⃣ Anchors (Fixed Devices)
- **What**: Small devices mounted at room corners
- **Quantity**: 4 anchors per room (A0, A1, A2, A3)
- **Purpose**: Reference points with known positions

## 2️⃣ Tags (Mobile Devices)  
- **What**: Small devices worn by people or attached to objects
- **Quantity**: Can track multiple tags simultaneously
- **Purpose**: The thing being tracked

## 3️⃣ Server (This System)
- **What**: Cloud computer at `15.204.231.252`
- **Purpose**: Receives data, calculates positions, shows on screen

---

# How Does It Work?

## Step-by-Step Process

```
STEP 1: Tag measures distance to each anchor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

         A3 ─────────────────── A2
          │         120 inches   │
          │            ↗         │
     95   │         📱          │  110
   inches │        (Tag)        │ inches
          │            ↘         │
          │         100 inches   │
         A0 ─────────────────── A1


STEP 2: Tag sends distances to server via WiFi/MQTT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📱 Tag  ──────►  📡 MQTT Broker  ──────►  💻 Server
    
    Message: {"id": 0, "range": [100, 110, 120, 95, 0, 0, 0, 0]}
                                ↑    ↑    ↑   ↑
                               A0   A1   A2  A3


STEP 3: Server calculates exact position
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Using math (trilateration), server finds X,Y position
    
    Result: Tag is at position (250, 180) inches from corner A0


STEP 4: Position shown on screen/app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ┌─────────────────────────┐
    │ 🖥️ Live Visualization   │
    │                         │
    │    A3 ──────────── A2   │
    │     │              │    │
    │     │    🔴 Tag 0  │    │
    │     │        🔵 Tag 1   │
    │     │              │    │
    │    A0 ──────────── A1   │
    │                         │
    └─────────────────────────┘
```

---

# System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         COMPLETE SYSTEM                          │
└─────────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  Anchor  │     │  Anchor  │     │  Anchor  │     │  Anchor  │
  │    A0    │     │    A1    │     │    A2    │     │    A3    │
  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                                │
                         UWB Signals
                                │
                                ▼
                        ┌──────────────┐
                        │     TAG      │
                        │   (Mobile)   │
                        └──────┬───────┘
                               │
                          WiFi/MQTT
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      CLOUD SERVER                                 │
│                    15.204.231.252                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│  │    MQTT     │  │   MongoDB   │  │  Position   │               │
│  │   Broker    │─▶│  Database   │─▶│ Calculator  │               │
│  │  Port 1883  │  │             │  │             │               │
│  └─────────────┘  └─────────────┘  └──────┬──────┘               │
│                                           │                       │
│                                           ▼                       │
│                                   ┌─────────────┐                 │
│                                   │  WebSocket  │                 │
│                                   │  Real-Time  │                 │
│                                   │   Updates   │                 │
│                                   └──────┬──────┘                 │
└──────────────────────────────────────────┼───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────┐
                    │         📱 Mobile App / 🖥️ Web       │
                    │         Real-Time Tracking View      │
                    └──────────────────────────────────────┘
```

---

# Data Message Format

## What the Tag Sends:

```json
{
    "id": 0,
    "range": [100, 110, 120, 95, 0, 0, 0, 0]
}
```

| Field | Meaning |
|-------|---------|
| `id` | Tag number (0, 1, 2, etc.) |
| `range[0]` | Distance to Anchor A0 (inches) |
| `range[1]` | Distance to Anchor A1 (inches) |
| `range[2]` | Distance to Anchor A2 (inches) |
| `range[3]` | Distance to Anchor A3 (inches) |
| `range[4-7]` | Reserved (set to 0) |

---

# Quick Setup Guide

## For Device/Hardware Team

### MQTT Connection Settings:

| Setting | Value |
|---------|-------|
| **Broker IP** | `15.204.231.252` |
| **Port** | `1883` |
| **Username** | `taha` |
| **Password** | `taha` |
| **Topic** | Your 7-digit ID (e.g., `1000001`) |

### Message to Publish:

```
Topic: 1000001
Message: {"id": 0, "range": [100, 110, 120, 95, 0, 0, 0, 0]}
```

---

## For App/Software Team

### API Server: `http://15.204.231.252`

### Basic API Flow:

```
1. SIGNUP    →  POST /api/signup     →  Create account
2. LOGIN     →  POST /api/login      →  Get token
3. ENROLL    →  POST /api/enrollment →  Register device
4. ROOM      →  POST /api/rooms      →  Create room
5. VISUALIZE →  POST /api/visualize  →  Get positions!
```

**After login:** Call **GET /api/enrollments** and **GET /api/rooms** and build the UI from that response so the user's topics and room IDs are preserved across re-login and app restarts.

### WebSocket (Real-Time):

```
URL: ws://15.204.231.252:8000

1. Connect with token
2. Send: start_visualization
3. Receive: position_update (every 0.5 seconds)
```

---

# Room Setup

## Measuring Your Room

```
    A3 ─────────────────────────────── A2
    │                                   │
    │         Measure these             │
    │         four distances:           │
    │                                   │
    │  A3-A0    Your Room      A2-A1    │
    │  (left)                  (right)  │
    │                                   │
    │                                   │
    A0 ─────────────────────────────── A1
              A0-A1 (bottom)
              A2-A3 (top)
```

### Room Registration:

| Field | Description | Example |
|-------|-------------|---------|
| `A0_A1` | Bottom wall length (inches) | `800` |
| `A1_A2` | Right wall length (inches) | `600` |
| `A2_A3` | Top wall length (inches) | `800` |
| `A3_A0` | Left wall length (inches) | `600` |
| `label` | Room name | `"Living Room"` |
| `mqtt_topic` | Device ID | `"1000001"` |

---

# Position Output

## What You Get Back:

```json
{
    "room_dimensions_in": {
        "width_in": 800,
        "height_in": 600
    },
    "anchor_positions": {
        "A0": {"x": 0, "y": 0},
        "A1": {"x": 800, "y": 0},
        "A2": {"x": 800, "y": 600},
        "A3": {"x": 0, "y": 600}
    },
    "tag_positions": {
        "0": {
            "x": 250,
            "y": 180,
            "x_normalized": 0.31,
            "y_normalized": 0.30,
            "status": true
        },
        "1": {
            "x": 520,
            "y": 400,
            "x_normalized": 0.65,
            "y_normalized": 0.67,
            "status": true
        }
    }
}
```

### Understanding Positions:

| Field | Meaning |
|-------|---------|
| `x`, `y` | Position in inches from A0 corner |
| `x_normalized` | Position as % of width (0.0 to 1.0) |
| `y_normalized` | Position as % of height (0.0 to 1.0) |
| `status` | `true` = valid position, `false` = error |

---

# Coordinate System

```
    (0, 600)                    (800, 600)
        A3 ─────────────────────── A2
        │                           │
        │     Y increases ↑         │
        │                           │
        │         X increases →     │
        │                           │
        │                           │
        A0 ─────────────────────── A1
    (0, 0)                      (800, 0)


    Origin (0,0) is at A0 (bottom-left corner)
```

---

# Common Questions

## Q: How accurate is the tracking?
**A:** UWB technology is accurate to within a few inches (typically 10-30cm).

## Q: How many tags can I track?
**A:** The system can track multiple tags simultaneously. Each tag has a unique ID (0, 1, 2, etc.).

## Q: What if a tag goes out of range?
**A:** The tag's `status` will be `false` and position won't be updated.

## Q: Can I track in multiple rooms?
**A:** Yes! Create separate rooms with different `mqtt_topic` values.

## Q: How fast are updates?
**A:** WebSocket provides updates every 0.5 seconds (configurable).

---

# Troubleshooting

| Problem | Check This |
|---------|-----------|
| No position data | Is MQTT publishing? Check `topic` matches |
| Position seems wrong | Verify room dimensions in inches |
| Can't connect to API | Check token, verify server is online |
| WebSocket disconnects | Token may have expired, re-login |

---

# Contact & Support

**Server IP:** `15.204.231.252`

**API Documentation:** See `API_DOCUMENTATION.md`

**Postman Collection:** See `UWB_Tracking_API.postman_collection.json`

---

*Document Version: 1.0*
*Last Updated: January 2026*

