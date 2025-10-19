import time
from pymavlink import mavutil
import math
import os

# make py request data instead of poll for heartbeat

EARTH_R = 6371000.0  # meters

FC_SERIAL_PORT = "/dev/ttyACM"
FC_HOST = "127.0.0.1"
FC_PORT = 14552
FC_BAUDRATE = 115200



def _haversine_m(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2)
    return 2 * EARTH_R * math.asin(math.sqrt(a))

def connect_fc(mavproxy: bool):
    print("[FC] Connecting to FC...")
    m = mavutil.mavlink_connection("tcp:127.0.0.1:5762")
    if m is not None:
        print("[FC] Connected! System ID:", m.target_system)
        return m
    else:
        print("[FC] Connection failed.")
        return None
    try:
        if mavproxy:
            m = mavutil.mavlink_connection(f"udp:{FC_HOST}:{FC_PORT}", udp_timeout=10)
        else:
            dev = next((f"{FC_SERIAL_PORT}{i}" for i in range(10) if os.path.exists(f"{FC_SERIAL_PORT}{i}")), None)
            if not dev:
                print("[FC] No FC serial device found.")
                return None
            m = mavutil.mavlink_connection(dev, baud=FC_BAUDRATE)
        m.wait_heartbeat(timeout=5)
        print("[FC] Connected! System ID:", m.target_system)
        return m
    except Exception:
        print("[FC] Connection failed.")
        return None

def arm(master):
    print("[FC] Arming...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0
    )
    while not is_armed(master):
        time.sleep(0.1)
    print("[FC] Armed.")

def disarm(master):
    print("[FC] Disarming...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 0, 0, 0, 0, 0, 0, 0
    )
    while is_armed(master):
        time.sleep(0.1)
    print("[FC] Disarmed.")

def set_wp_speed(master, speed_m_s):
    print(f"[FC] Setting WP speed to {speed_m_s} m/s...")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
        0,    # confirmation
        1,    # speed type (1=ground speed)
        float(speed_m_s),  # speed in m/s
        -1,   # throttle (ignored)
        0, 0, 0, 0  # unused
    )

def set_loiter_radius(master, radius_m):
    print(f"[FC] Setting LOITER radius to {radius_m:.1f} m...")
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        b"WP_RADIUS",
        radius_m,
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )


def set_mode(master, mode_name):
    print(f"[FC] Setting mode to {mode_name}...")
    mode_id = master.mode_mapping().get(mode_name)
    if mode_id is None:
        print(f"[FC] Unknown mode: {mode_name}")
        return
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode_id
    )
    while read_mode(master) != mode_name:
        time.sleep(0.1)
    print(f"[FC] Mode set to {mode_name}.")

# send guided waypoint (lat, lon in degrees)
def send_guided_waypoint(master, lat, lon):
    # Send SET_POSITION_TARGET_GLOBAL_INT (position-only target)
    print(f"[FC] Sending GUIDED waypoint to ({lat}, {lon})...")
    master.mav.set_position_target_global_int_send(
        0,
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
        0b111111111100,  # bitmask: ignore everything except x/y position
        int(lat * 1e7),
        int(lon * 1e7),
        0, 0, 0, 0, 0, 0, 0, 0, 0
    )

def read_gps(master):
    msg = master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=5)
    return {
        "lat": msg.lat / 1e7,
        "lon": msg.lon / 1e7,
        "alt": msg.alt / 1e3
    }

def read_mode(master):
    msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    if not msg:
        return None
    
    custom_mode = msg.custom_mode
    mapping = master.mode_mapping() or {}
    # Reverse-lookup by custom_mode
    for name, mid in mapping.items():
        if mid == custom_mode:
            return name
    # Fallback to numeric if unknown mapping
    return f"CUSTOM({custom_mode})"

def is_armed(master):
    msg = master.recv_match(type='HEARTBEAT', blocking=True, timeout=5)
    if not msg:
        return False # no heartbeat
    return bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) 

def is_at_wp(master, target_lat, target_lon):
    gps = read_gps(master)
    if not gps:
        return False # no GPS fix
    return _haversine_m(gps["lat"], gps["lon"], target_lat, target_lon) < 1.5  # 1.5 meter threshold

def set_wp_acceptance_radius(master, radius_m):
    print(f"[FC] Setting WP acceptance radius to {radius_m:.1f} m...")
    master.mav.command_long_send(
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_PARAMETER,  # safer for ArduPilot
        0,                                         # confirmation
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,     # optional param type
        0, 0, 0, 0, 0, 0, 0
    )
