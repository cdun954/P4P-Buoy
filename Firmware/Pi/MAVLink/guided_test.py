import mavlink_cmd as m
import time
import math

# Earth radius in meters
EARTH_R = 6371000.0

def corner_coords(fc, edge_m=10):
    origin = m.read_gps(fc)
    if not origin: return None
    lat0, lon0 = origin["lat"], origin["lon"]
    dlat = edge_m / EARTH_R * (180.0 / math.pi)
    dlon = edge_m / (EARTH_R * math.cos(math.radians(lat0))) * (180.0 / math.pi)
    return [
        (lat0,      lon0 + dlon),  # E
        (lat0+dlat, lon0 + dlon),  # NE
        (lat0+dlat, lon0),         # N
        (lat0,      lon0)          # origin
    ]

# connect
fc = None
while not fc:
    try:
        fc = m.connect_fc()
    except Exception as e:
        print("[ERR] Failed to connect FC:", e)
    time.sleep(2)

# arm
if not m.is_armed(fc):
    m.arm(fc)
    time.sleep(2)

# wps
wps = corner_coords(fc)
if not wps:
    print("No GPS fix")
    exit(1)

while(True):
    for wp in wps:
        # set to GUIDED
        m.set_mode(fc, "GUIDED")
        time.sleep(1)
        m.send_guided_waypoint(fc, wp[0], wp[1])
        while(not m.is_at_wp(fc, wp[0], wp[1])):
            time.sleep(0.1)
        m.set_mode(fc, "LOITER")
        time.sleep(3)
