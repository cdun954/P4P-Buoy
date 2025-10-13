from pymavlink import mavutil
import time

# --- Setup connection ---
master = mavutil.mavlink_connection('COM8', baud=115200)
master.wait_heartbeat()
print("Connected to system", master.target_system)

# --- Helper: set mode ---
def set_mode(mode_name):
    """Change flight mode by name."""
    mode_id = master.mode_mapping()[mode_name]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    print(f"[MODE] Requested: {mode_name}")

# --- Helper: get current mode string ---
def get_current_mode():
    msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=1)
    if not msg:
        return "NO HEARTBEAT"
    custom_mode = msg.custom_mode
    for name, mode_id in master.mode_mapping().items():
        if mode_id == custom_mode:
            return name
    return f"UNKNOWN({custom_mode})"

# --- List of modes to cycle through ---
modes = ["MANUAL", "HOLD", "AUTO", "GUIDED", "LOITER", "RTL"]

print("Cycling through modes every 5 seconds; printing current mode every 1 second...")

current_mode_index = 0
last_change = time.time()
last_print = time.time()

# --- Main loop ---
while True:
    now = time.time()

    # Change mode every 5 seconds
    if now - last_change >= 5:
        set_mode(modes[current_mode_index])
        current_mode_index = (current_mode_index + 1) % len(modes)
        last_change = now

    # Print mode every 1 second
    if now - last_print >= 1:
        mode = get_current_mode()
        print(f"[STATUS] Current Mode: {mode}")
        last_print = now
