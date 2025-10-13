from pymavlink import mavutil
import time, math

# --- Connection ---
master = mavutil.mavlink_connection("udp:100.69.169.69:14550")
master.wait_heartbeat()
print(f"Connected to sys {master.target_system} comp {master.target_component}")

# --- Parameters ---
WAYPOINTS = [
    (-37.001234, 174.999876),   # lat, lon 1
    (-37.002500, 174.998400),   # lat, lon 2
]
ARRIVE_THRESH = 5.0  # meters

# --- Simple helpers ---
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dphi  = math.radians(lat2-lat1)
    dlamb = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlamb/2)**2
    return 2*R*math.asin(math.sqrt(a))

def get_pos():
    msg = master.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
    if msg:
        return (msg.lat/1e7, msg.lon/1e7)
    return None

# --- Arm if disarmed ---
while True:
    hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb:
        armed = (hb.base_mode & 128) != 0
        mode  = master.mode_mapping().get(hb.custom_mode, str(hb.custom_mode))
        if not armed:
            print("Arming...")
            master.mav.command_long_send(master.target_system, master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1,0,0,0,0,0,0)
        if mode != "GUIDED":
            print("Switching to GUIDED...")
            master.set_mode(master.mode_mapping()["GUIDED"])
        if armed and mode == "GUIDED":
            break

# --- Go through waypoints ---
for i,(lat,lon) in enumerate(WAYPOINTS,1):
    print(f"Sending waypoint {i}: {lat},{lon}")
    master.mav.set_position_target_global_int_send(
        int(time.time()*1000), master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_INT,  # frame
        0b111111000111000,                     # type_mask (only pos active)
        int(lat*1e7), int(lon*1e7), 0,         # target lat/lon/alt
        0,0,0, 0,0,0, 0,0                      # velocity/accel/yaw ignored
    )

    # Wait until reached
    while True:
        pos = get_pos()
        if pos:
            d = haversine(pos[0],pos[1],lat,lon)
            print(f"  Dist {d:.1f} m", end="\r")
            if d < ARRIVE_THRESH:
                print(f"\n Arrived at WP{i}")
                break
        time.sleep(1)

print("All waypoints complete.")
