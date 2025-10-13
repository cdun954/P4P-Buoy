import time
from pymavlink import mavutil
import math

EARTH_R = 6371000.0  # meters

def _haversine_m(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2)
    return 2 * EARTH_R * math.asin(math.sqrt(a))

def connect_fc():
    print("Connecting to FC...")
    master = mavutil.mavlink_connection('udp:127.0.0.1:14552')
    # Wait a heartbeat before sending commands
    master.wait_heartbeat() 
    print("[FC] Connected! System ID:", master.target_system)
    return master

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


def do_loiter_at(master, lat, lon, radius_m=5, alt=0):
    cmd = (mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM)

    p1 = 0                   # seconds (only used for LOITER_TIME)
    p2 = 0                   # unused
    p3 = float(radius_m)     # loiter radius (meters)
    p4 = 0                   # 0: default/cw; sign may select direction on some frames
    # params 5/6/7: target location (deg, deg, meters)
    master.mav.command_long_send(
        master.target_system, master.target_component,
        cmd, 0,
        p1, p2, p3, p4,
        float(lat), float(lon), float(alt)
    )
    while read_mode(master) != "LOITER":
        time.sleep(0.1)
    print(f"[FC] Loitering at ({lat}, {lon}) at {radius_m}m radius")

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

# send guided waypoint (lat, lon in degrees) and speed (m/s)
def send_guided_waypoint(master, lat, lon, speed=1.0):
    # Send SET_POSITION_TARGET_GLOBAL_INT (position-only target)
    print(f"[FC] Sending GUIDED waypoint to ({lat}, {lon})...")
    master.mav.set_position_target_global_int_send(
        0,  # time_boot_ms (ignored)
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_INT,
        0b111111111100,  # ignore everything except x/y position
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
        return None # no heartbeat
    return bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) 

def is_at_wp(master, target_lat, target_lon):
    gps = read_gps(master)
    if not gps:
        return None # no GPS fix
    return _haversine_m(gps["lat"], gps["lon"], target_lat, target_lon) < 1.0  # 1 meter threshold