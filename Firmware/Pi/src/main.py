import time
import signal
import sys
import os
import subprocess
import certifi
import random
import paho.mqtt.client as mqtt
import json
# from algo_test import run_coverage, save_map, load_map
import mavlink_cmd as m

"""
main.py

Central command hub for the Raspberry Pi on the P4P Buoy.
Handles:
- Receiving commands via MQTT and dispatching them
- Starting/stopping mavproxy and camera streaming
- Sending telemetry data via MQTT
- (Future) Water quality sensors integration
- (Future) Coordinate traversal automation
"""

# ======================== #
#        CONSTANTS         #
# ======================== #

# ==== venv dir ===
VENV_PATH = "/home/pi/Desktop/python/bin/python3"

# ==== Broker config ====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

# ==== MQTT Topics ====  
TOPIC_CMD = "buoy/pi/cmd"
TOPIC_STATUS = "buoy/pi/status"
TOPIC_SENSOR = "buoy/pi/sensor"
TOPIC_AUTON = "buoy/pi/autonomy"

# ==== MAVPROXY config ====
MAVPROXY_PATH = "/home/pi/Desktop/python/bin/mavproxy.py"
FC_SERIAL_PORT = "/dev/ttyACM"
FC_BAUDRATE = 115200
LAPTOP_IP = "100.69.169.70"
LAPTOP_PORT = 14550
PHONE_IP = "100.69.169.71"
PHONE_PORT = 14551
AUTO_IP = "127.0.0.1"
AUTO_PORT = 14552
CROM_IP = "100.69.169.72"
CROM_PORT = 14553

# ==== CAM config ====
CAMERA_PATH = "/home/pi/Desktop/project/camera.py"

# ==== Autonomy Config ====
GUIDED_TEST_PATH = "/home/pi/Desktop/project/guided_test.py"
AUTONOMY_PATH = "/home/pi/Desktop/project/algo_test.py"
FEN_PATH = "/home/pi/Desktop/project/taka_lake.fen"

# ==== Process names ====
MAVPROXY = "mavproxy"
CAMERA = "camera"
GUIDED_TEST = "guided_test"
AUTONOMY = "autonomy"

# ========================= #
#         GLOBALS           #
# ========================= #

running = True
paused = False
sens_temp = 0.0
sens_ph = 7.0
sens_turb = 0.0
sens_nitrate = 0.0
sens_phosphate = 0.0

# autonomy parameters last set
grid_size = 0.00015
edge_ratio = 0.7
travel_speed = 1.2
loiter_radius = 1
loiter_time = 10
max_wp_time = 10


# ========================= #
#       CMD HANDLERS        #
# ========================= #

def cmd_update(client, args):
    update_sensors(client, args)
    update_status(client, True)

def update_sensors(client, args):
    global sens_temp, sens_ph, sens_turb, sens_nitrate, sens_phosphate
    sensor_data = {
        "temperature":  sens_temp,
        "ph":           sens_ph,
        "turbidity":    sens_turb,
        "nitrate":      sens_nitrate,
        "phosphate":    sens_phosphate
    }
    print(f"Sensor Update")
    client.publish(TOPIC_SENSOR, json.dumps(sensor_data))

def update_status(client, args=False):
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    mavproxy_on = MAVPROXY in result.stdout
    cam_on = CAMERA in result.stdout
    autonomy_on = GUIDED_TEST in result.stdout

    # check FC armed status
    fc_mode = "ERROR"
    fc_armed = False
    if args is True:
        mav = m.connect_fc(mavproxy_on)
        if mav is not None:
            fc_armed = m.is_armed(mav)
            fc_mode = m.read_mode(mav)

    status = {
        "mavproxy_on": mavproxy_on,
        "camera_on": cam_on,
        "autonomy_on": autonomy_on, 
        "state": "IDLE" if not autonomy_on else "AUTO",
        "fc_mode": fc_mode,
        "fc_armed": fc_armed

    }
    print(f"Status Update")
    client.publish(TOPIC_STATUS, json.dumps(status))

def cmd_pause(client, args):
    global paused
    close_process(GUIDED_TEST)
    if process_is_open(AUTONOMY):
        close_process(AUTONOMY)
        paused = True

    m.set_mode(m.connect_fc(process_is_open(MAVPROXY)), "HOLD")
    update_status(client, args)

def cmd_resume(client, args):
    # start autonomy if not running
    global paused
    if paused:
        paused = False
        start_autonomy(args)
    
    update_status(client, args)

def cmd_rc_override(client, args):
    # cancel autonomy if running and send RC override command
    close_process(GUIDED_TEST)
    close_process(AUTONOMY)

    m.set_mode(m.connect_fc(process_is_open(MAVPROXY)), "MANUAL")

def cmd_rtl(client, args):
    # cancel autonomy if running and send RTL command
    close_process(GUIDED_TEST)
    close_process(AUTONOMY)

    m.set_mode(m.connect_fc(process_is_open(MAVPROXY)), "RTL")

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
    if process_is_open(MAVPROXY):
        # mavproxy is running, kill it
        print("Killed MAVProxy.")
        close_process(MAVPROXY)
    else:
        # mavproxy is not running, start it
        print("Starting MAVProxy...")
        start_mavproxy()

def cmd_auto(client, args):
    if process_is_open(AUTONOMY):
        # kill
        print("Killed Autonomy.")
        close_process(AUTONOMY)
    else:
        # start
        print("Starting Autonomy...")
        start_autonomy(args)

def cmd_guided_test(client, args):
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    if "guided_test" in result.stdout:
        # kill
        print("Killed Guided Test.")
        subprocess.run("tmux kill-window -t project:guided_test", shell=True)
    else:
        # start
        print("Starting Guided Test...")
        start_guided_test()

# ========================= #
#          COMMANDS         #
# ========================= #
def start_mavproxy():
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
        f"{VENV_PATH}",
        f"{MAVPROXY_PATH}",
        f"--master={FC_SERIAL_PORT}{port_num}",
        f"--out=udp:{LAPTOP_IP}:{LAPTOP_PORT}",
        f"--out=udp:{PHONE_IP}:{PHONE_PORT}",
        f"--out=udp:{AUTO_IP}:{AUTO_PORT}",
        f"--out=udp:{CROM_IP}:{CROM_PORT}",
        f"--baud={FC_BAUDRATE}"
    ])
    # run in tmux
    tmux_cmd = f"tmux new-window -t project -n mavproxy {cmd}"
    print(f"Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True) 

def start_cam():
    cmd = f"{VENV_PATH} {CAMERA_PATH}"
    tmux_cmd = f"tmux new-window -t project -n camera {cmd}"
    print(f"Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True)

def start_guided_test():
    cmd = f"{VENV_PATH} {GUIDED_TEST_PATH}"
    tmux_cmd = f"tmux new-window -t project -n guided_test {cmd}"
    print(f"Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True)

def process_water_quality_sensors():
    global sens_temp, sens_ph, sens_turb, sens_nitrate, sens_phosphate

    # dummy values for now
    sens_temp = random.randint(10, 30)
    sens_ph = random.randint(6, 8)
    sens_turb = random.randint(0, 100)

    sens_nitrate = random.randint(0, 50)
    sens_phosphate = random.randint(0, 50)

def start_autonomy(args):
    """
    Params expected (from GUI, JSON string):
      grid_size      -> --tile-size-lat (deg); also mirrored to --tile-size-lon
      edge_ratio     -> --coverage-threshold (0..1)
      travel_speed   -> --wp_speed (m/s)
      loiter_radius  -> --loiter-radius (m)
      loiter_time    -> --loiter-sec (s)
      max_wp_time    -> --max-wp-time-s (s)
    """
    try:
        params = json.loads(args) if args else {}
    except Exception as e:
        print(f"[AUTON] Invalid JSON args: {e}")
        return
    
    # === Map GUI fields -> CLI flags ===
    global grid_size, edge_ratio, travel_speed, loiter_radius, loiter_time, max_wp_time
    grid_size     = params.get("grid_size")
    edge_ratio    = params.get("edge_ratio")
    travel_speed  = params.get("travel_speed")
    loiter_radius = params.get("loiter_radius")
    loiter_time   = params.get("loiter_time")
    max_wp_time   = params.get("max_wp_time")

    # === Build command ===
    cmd_parts = [
        f"{VENV_PATH}",
        f"{AUTONOMY_PATH}",
        f"--fen", f"{FEN_PATH}",        # adjust to your .fen path
    ]

    if grid_size is not None:
        cmd_parts += ["--tile-size-lat", str(grid_size), "--tile-size-lon", str(grid_size)]
    if edge_ratio is not None:
        cmd_parts += ["--coverage-threshold", str(edge_ratio)]
    if travel_speed is not None:
        cmd_parts += ["--wp_speed", str(travel_speed)]
    if loiter_radius is not None:
        cmd_parts += ["--loiter-radius", str(loiter_radius)]
    if loiter_time is not None:
        cmd_parts += ["--loiter-sec", str(loiter_time)]
    if max_wp_time is not None:
        cmd_parts += ["--max-wp-time-s", str(max_wp_time)]

    # === Combine and launch in tmux ===
    cmd = " ".join(cmd_parts)
    tmux_cmd = f"tmux new-window -t project -n autonomy {cmd}"
    print(f"[AUTON] Executing: {tmux_cmd}")
    subprocess.run(tmux_cmd, shell=True)

# =============================== #
#          TMUX COMMANDS          #
# =============================== #
def process_is_open(window_name: str) -> bool:
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    return window_name in result.stdout

def close_process(window_name: str):
    if process_is_open(window_name):
        print(f"Killed {window_name}.")
        subprocess.run(f"tmux kill-window -t project:{window_name}", shell=True)

def open_process(window_name: str, cmd: str|None):
    if not process_is_open(window_name):
        print(f"Starting {window_name}...")
        tmux_cmd = f"tmux new-window -t project -n {window_name} {cmd}" if cmd else f"tmux new-window -t project -n {window_name}"
        print(f"Executing: {tmux_cmd}")
        subprocess.run(tmux_cmd, shell=True)
    
def close_all_processes():
    result = subprocess.run("tmux list-windows -t project", shell=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        window_name = line.split(":")[1].strip().split()[0]
        print(f"Killed {window_name}.")
        subprocess.run(f"tmux kill-window -t project:{window_name}", shell=True)


# ================================= #
#          MQTT CALLBACKS           #
# ================================= #
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] connected rc={rc}")
    client.subscribe([(TOPIC_CMD, 0)])

# Map command keyword -> handler
DISPATCH = {
    "pause":            cmd_pause,
    "resume":           cmd_resume,
    "rc_override":      cmd_rc_override,
    "update":           cmd_update,
    "toggle_cam":       cmd_cam,
    "toggle_mavproxy":  cmd_proxy,
    "guided_test":      cmd_guided_test,
    "rtl":              cmd_rtl,
    "toggle_autonomy":  cmd_auto
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

    # CMD messages
    if msg.topic == TOPIC_CMD:
        cmd, args = parse_cmd(payload)
        handler = DISPATCH.get(cmd)
        if handler:
            try:
                handler(client, args)
            except Exception as e:
                print("[ERR] Command handler failed:", e)
        else:
            print(f"[ERR] Unknown command: {cmd}")
 
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
        # update
        process_water_quality_sensors()
        update_sensors(client, None)
        update_status(client, False)

if __name__ == "__main__":
    main()

