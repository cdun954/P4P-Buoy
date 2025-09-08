import time
import signal
import sys
import os
import subprocess
import certifi
import paho.mqtt.client as mqtt

"""
main.py

Central command hub for the Raspberry Pi on the P4P Buoy.
Handles:
- Receiving commands via MQTT and dispatching them
- Starting/stopping mavproxy and camera streaming
- (Future) Sending telemetry data via MQTT
"""

# ======================== #
#        CONSTANTS         #
# ======================== #

# ==== venv dir ===
VENV_DIR = "/home/pi/Desktop/python/bin/python3"

# ==== Broker config ====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

# ==== MQTT Topics ====  
TOPIC_CMD = "boat/pi/cmd"
TOPIC_TELEM = "boat/pi/telem"

# ==== MAVPROXY config ====
MAVPROXY = "/home/pi/Desktop/python/bin/mavproxy.py"
FC_SERIAL_PORT = "/dev/ttyACM"
FC_BAUDRATE = 115200
LAPTOP_IP = "100.69.169.70"
LAPTOP_PORT = 14550
PHONE_IP = "100.69.169.71"
PHONE_PORT = 14551
AUTO_IP = "127.0.0.1"
AUTO_PORT = 14552

# ==== CAM config ====
CAMERA = "/home/pi/Desktop/project/camera.py"

# ========================= #
#         GLOBALS           #
# ========================= #
running = True

# ========================= #
#       CMD HANDLERS        #
# ========================= #

def cmd_update(client, args):
    # TODO:
    pass

def cmd_cam(client, args):
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    if "camera" in result.stdout:
        # camera is running, kill it
        print("Killed Camera.")
        subprocess.run("tmux kill-window -t project:camera", shell=True)
    else:
        # camera is not running, start it
        print("Starting Camera...")
        start_cam()
    pass

def cmd_proxy(client, args):
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    if "mavproxy" in result.stdout:
        # mavproxy is running, kill it
        print("Killed MAVProxy.")
        subprocess.run("tmux kill-window -t project:mavproxy", shell=True)
    else:
        # mavproxy is not running, start it
        print("Starting MAVProxy...")
        start_mavproxy()

# ========================= #
#          COMMANDS         #
# ========================= #

def start_mavproxy():
    # make sure port is correct: ls /dev/tty*
    port_num = 0
    while True:
        candidate = f"{FC_SERIAL_PORT}{port_num}"
        if os.path.exists(candidate):
            port = candidate
            print(f"FC Connection Found!: {candidate}")
            break
        port_num += 1
        if port_num > 9:
            print("No FC Connection Found :(")
            return

    cmd = " ".join([
        f"{VENV_DIR}",
        f"{MAVPROXY}",
        f"--master={FC_SERIAL_PORT}{port_num}",
        f"--out=udp:{LAPTOP_IP}:{LAPTOP_PORT}",
        f"--out=udp:{PHONE_IP}:{PHONE_PORT}",
        f"--out=udp:{AUTO_IP}:{AUTO_PORT}",
        f"--baud={FC_BAUDRATE}"
    ])
    # run in tmux
    tmux_cmd = f"tmux new-window -t project -n mavproxy {cmd}"
    print(f"Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True)

def start_cam():
    cmd = f"{VENV_DIR} {CAMERA}"
    tmux_cmd = f"tmux new-window -t project -n camera {cmd}"
    print(f"Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True)

# ================================= #
#          MQTT CALLBACKS           #
# ================================= #
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] connected rc={rc}")
    client.subscribe([(TOPIC_CMD, 0)])

# Map command keyword -> handler
DISPATCH = {
    "update": cmd_update,
    "toggle_cam":    cmd_cam,
    "toggle_mavproxy":  cmd_proxy,
}

def parse_cmd(payload: str):
    """Return (cmd:str, args:str|None). Accepts 'cmd' or 'cmd arg text'."""
    s = payload.strip()
    if not s:
        return "", None
    parts = s.split(maxsplit=1)
    return parts[0].lower(), (parts[1] if len(parts) > 1 else None)

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace")
    print(f"[MQTT] {msg.topic} -> {payload}")
    if msg.topic != TOPIC_CMD:
        return
    cmd, args = parse_cmd(payload)
    handler = DISPATCH.get(cmd)
    if handler:
        try:
            handler(client, args)
        except Exception as e:
            # incorrect cmd
            pass
 
def on_disconnect(client, userdata, rc):
    print(f"[MQTT] disconnected rc={rc}")

def build_client():
    c = mqtt.Client(
        client_id="pi-cmd-hub",
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    c.username_pw_set(USERNAME, PASSWORD)
    c.tls_set(ca_certs=certifi.where())
    c.on_connect = on_connect
    c.on_message = on_message
    c.on_disconnect = on_disconnect
    c.reconnect_delay_set(min_delay=1, max_delay=30)
    return c

def _stop(*_):
    global running
    # graceful shutdown here
    running = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


# ========================= #
#           MAIN            #
# ========================= #
def main():
    client = build_client()
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()

    while running:
        time.sleep(1)

if __name__ == "__main__":
    main()

