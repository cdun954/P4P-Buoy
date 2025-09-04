import os
import sys
import time
import subprocess
import csv
from pymavlink import mavutil

# ===== Configuration =====
VENV_DIR = "~/Desktop/python"

MAVPROXY = "mavproxy.py"
FC_SERIAL_PORT = "/dev/ttyACM0"
FC_BAUD = 115200

LAPTOP_IP = "100.69.169.70"
LAPTOP_PORT = 14550

PHONE_IP = "100.69.169.71"
PHONE_PORT = 14551
 
AUTO_IP = "127.0.0.1"
AUTO_PORT = 14552

# ===== Setup MavProxy Multiplexer =====
def launch_mavproxy():
    if not os.path.exists(FC_SERIAL_PORT):
        print(f"FC ({FC_SERIAL_PORT}) not found, waiting to become available...")
        while not os.path.exists(FC_SERIAL_PORT):
            time.sleep(0.5)
    print(f"FC ({FC_SERIAL_PORT}) found! Launching MavProxy...")    
    
    activate_venv = f"source {VENV_DIR}/bin/activate"
    start_mavproxy = " ".join([
        f"{MAVPROXY}",
        f"--master={FC_SERIAL_PORT}",
        f"--out=udp:{LAPTOP_IP}:{LAPTOP_PORT}",
        f"--out=udp:{PHONE_IP}:{PHONE_PORT}",
        f"--out=udp:{AUTO_IP}:{AUTO_PORT}",
        f"--baud={FC_BAUD}"
        ])
        
    cmd = f"bash -c '{activate_venv}; {start_mavproxy}; exec bash'"
    return subprocess.Popen([
        "lxterminal",
        "--title", "MAVProxy Telemetry",
        "--command", f"{cmd}"
        ])

# launch mavproxy
mavproxy = launch_mavproxy()
print("MavProxy launched in the background!")

m = mavutil.mavlink_connection(f"udp:{AUTO_IP}:{AUTO_PORT}")


# Open CSV log file
with open("power_servo_log.csv", mode="w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp",
        "voltage_v",
        "current_a",
        "servo1_pwm",
        "servo2_pwm"
    ])

    # Initialise values
    voltage = None
    current = None
    servo1 = None
    servo2 = None

    while True:
        msg = m.recv_match(type=["BATTERY_STATUS", "SERVO_OUTPUT_RAW"], blocking=True)
        if msg is None:
            continue

        updated = False

        if msg.get_type() == "BATTERY_STATUS":
            # Battery voltage comes in millivolts (mV), current in 10 mA units
            voltage = msg.voltages[0] / 1000.0 if msg.voltages[0] != 0xFFFF else None
            current = msg.current_battery / 100.0 if msg.current_battery != -1 else None
            updated = True

        elif msg.get_type() == "SERVO_OUTPUT_RAW":
            # Servo outputs indexed from 0
            servo1 = msg.servo1_raw
            servo2 = msg.servo2_raw
            updated = True

        if updated:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([timestamp, voltage, current, servo1, servo2])
            f.flush()
            print(f"{timestamp} | V: {voltage} V | I: {current} A | S1: {servo1} | S2: {servo2}")

