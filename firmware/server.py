# ==== backend_pico_server.py ====
# MicroPython code for Raspberry Pi Pico W
# Serves live sensor data over HTTP (JSON)

import network
import socket
import time
import json
from random import randint, uniform

# --- WiFi credentials ---
SSID = "YOUR_WIFI_SSID"       # <-- change this
PASSWORD = "YOUR_WIFI_PASSWORD"  # <-- and this

# Connect to WiFi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)
print("🌐 Connecting to WiFi...", end="")
while not wlan.isconnected():
    time.sleep(0.5)
print("\n✅ Connected:", wlan.ifconfig())
ip = wlan.ifconfig()[0]

# --- HTTP Web Server ---
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
server = socket.socket()
server.bind(addr)
server.listen(1)
print(f"🌍 Web server running on http://{ip}/")

def read_sensors():
    """Simulate sensor readings — replace with real reads later."""
    hr = randint(60, 100)
    spo2 = uniform(95, 100)
    systolic = randint(110, 130)
    diastolic = randint(70, 85)
    temp_c = uniform(36.0, 37.5)
    air_q = randint(100, 200)
    return {
        "bpm": hr,
        "spo2": spo2,
        "systolic": systolic,
        "diastolic": diastolic,
        "temperature": temp_c,
        "air_quality": air_q,
        "physio_status": "Good" if hr < 100 else "Warning",
        "env_status": "Safe" if air_q < 300 else "Risk",
        "fused_status": "Normal" if hr < 100 else "Alert"
    }

while True:
    cl, addr = server.accept()
    _ = cl.recv(1024)  # ignore request details
    data = read_sensors()
    response = json.dumps(data)

    # ✅ Send headers separately so we can add CORS
    cl.send('HTTP/1.1 200 OK\r\n')
    cl.send('Content-Type: application/json\r\n')
    cl.send('Access-Control-Allow-Origin: *\r\n')  # ✅ This line enables web dashboard fetches
    cl.send('\r\n')
    cl.send(response)
    cl.close()