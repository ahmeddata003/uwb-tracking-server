import pygame
import paho.mqtt.client as mqtt
import json
import math
import time

RED = [255, 0, 0]
BLACK = [0, 0, 0]
WHITE = [255, 255, 255]

class UWB:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []

        if self.type == 1:
            self.color = RED
        else:
            self.color = BLACK

    def set_location(self, x, y):
        self.x = x
        self.y = y
        self.status = True

    def cal(self):
        # Map range to anchor index
        distances = [(i, r) for i, r in enumerate(self.list) if r > 0]

        # Sort by distance (closest anchors)
        distances.sort(key=lambda x: x[1])

        # Use only the 3 nearest anchors
        if len(distances) >= 3:
            selected_ids = [distances[i][0] for i in range(3)]

            x = 0.0
            y = 0.0

            for i in range(3):
                for j in range(i + 1, 3):
                    temp_x, temp_y = self.three_point_uwb(selected_ids[i], selected_ids[j])
                    x += temp_x
                    y += temp_y

            x = int(x / 3)
            y = int(y / 3)

            self.set_location(x, y)
            self.status = True

    def three_point_uwb(self, a_id, b_id):
        x, y = self.three_point(anc[a_id].x, anc[a_id].y, anc[b_id].x,
                                anc[b_id].y, self.list[a_id], self.list[b_id])

        return x, y

    def three_point(self, x1, y1, x2, y2, r1, r2):
        temp_x = 0.0
        temp_y = 0.0
        # 圆心距离
        p2p = (x1 - x2)*(x1 - x2) + (y1 - y2)*(y1 - y2)
        p2p = math.sqrt(p2p)

        # 判断是否相交
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1 * r1 - r2 * r2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p

        return temp_x, temp_y

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to MQTT broker with code {rc}")
    client.subscribe("UWB123")

def on_message(client, userdata, msg):
    raw_message = msg.payload.decode('utf-8')
    print(f"Received: {raw_message}")
    try:
        data = json.loads(raw_message)
        if 'id' in data and 'range' in data:
            tag_id = data['id']
            if tag_id < len(tag):
                tag[tag_id].list = data['range']
                tag[tag_id].cal()
            else:
                print(f"[WARNING] Invalid tag ID: {tag_id}")
        else:
            print(f"[WARNING] Missing 'id' or 'range' in JSON: {raw_message}")
    except ValueError as e:
        print(f"[LOG] Invalid JSON: {raw_message}")

def draw_uwb(uwb):
    pixel_x = int(uwb.x * cm2p + x_offset)
    pixel_y = SCREEN_Y - int(uwb.y * cm2p + y_offset)

    if uwb.status:
        r = 10
        temp_str = uwb.name + " (" + str(uwb.x) + "," + str(uwb.y) + ")"
        font = pygame.font.SysFont("Consola", 24)
        surf = font.render(temp_str, True, uwb.color)
        screen.blit(surf, [pixel_x, pixel_y])
        pygame.draw.circle(screen, uwb.color, [pixel_x + 20, pixel_y + 50], r, 0)

def fresh_page():
    runtime = time.time()
    screen.fill(WHITE)
    for uwb in anc:
        draw_uwb(uwb)
    for uwb in tag:
        draw_uwb(uwb)

    pygame.draw.line(screen, BLACK, (CENTER_X_PIEXL, 0),
                     (CENTER_X_PIEXL, SCREEN_Y), 1)
    pygame.draw.line(screen, BLACK, (0, CENTER_Y_PIEXL),
                     (SCREEN_X, CENTER_Y_PIEXL), 1)

    pygame.display.flip()

    #print("Fresh Over, Use Time:")
    #print(time.time() - runtime)

def distance(x1, y1, x2, y2):
    return math.sqrt((x2-x1) ** 2 + (y2 - y1)**2)

# Main Function .............................................................

SCREEN_X = 800
SCREEN_Y = 800

pygame.init()
screen = pygame.display.set_mode([SCREEN_X, SCREEN_Y])

# MQTT Setup
MQTT_BROKER = "15.204.231.252"
MQTT_PORT = 1883
MQTT_USER = "taha"
MQTT_PASS = "taha"
client = mqtt.Client(protocol=mqtt.MQTTv5)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

anc = []
tag = []
anc_count = 4
tag_count = 2

A0X, A0Y = 0, 0
A1X, A1Y = 280, 0
A2X, A2Y = 280, 610
A3X, A3Y = 0, 610

CENTER_X = int((A0X+A1X+A2X)/3)
CENTER_Y = int((A0Y+A1Y+A2Y)/3)

r0 = distance(A0X, A0Y, CENTER_X, CENTER_Y)
r1 = distance(A1X, A1Y, CENTER_X, CENTER_Y)
r2 = distance(A2X, A2Y, CENTER_X, CENTER_Y)
r3 = distance(A3X, A3Y, CENTER_X, CENTER_Y)

r = max(r0, r1, r2, r3)

cm2p = SCREEN_X / 2 * 0.9 / r

x_offset = SCREEN_X / 2 - CENTER_X * cm2p
y_offset = SCREEN_Y / 2 - CENTER_Y * cm2p

CENTER_X_PIEXL = CENTER_X * cm2p + x_offset
CENTER_Y_PIEXL = CENTER_Y * cm2p + y_offset

for i in range(anc_count):
    name = "ANC " + str(i)
    anc.append(UWB(name, 0))
for i in range(tag_count):
    name = "TAG " + str(i)
    tag.append(UWB(name, 1))
anc[0].set_location(A0X, A0Y)
anc[1].set_location(A1X, A1Y)
anc[2].set_location(A2X, A2Y)
anc[3].set_location(A3X, A3Y)

fresh_page()
client.publish("UWB123", "begin")

runtime = time.time()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            client.loop_stop()
            client.disconnect()
            pygame.quit()
            exit()

    if (time.time() - runtime) > 0.5:
        fresh_page()
        runtime = time.time()
