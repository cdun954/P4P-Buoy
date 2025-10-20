import mavlink_cmd as m
import math, time

# small-angle, spherical-earth approximation
# to build a square around a point as the SW corner
EARTH_R = 6371000.0
RAD_TO_DEG = (180.0 / math.pi)
def corner_coords(fc, edge_m=10):
    origin = m.read_gps(fc)
    lat0, lon0 = origin["lat"], origin["lon"]
    dlat = edge_m / EARTH_R * RAD_TO_DEG
    _lon = math.cos(math.radians(lat0))
    dlon = edge_m / (EARTH_R * _lon) * RAD_TO_DEG
    return [
        (lat0,      lon0 + dlon),  # E
        (lat0+dlat, lon0 + dlon),  # NE
        (lat0+dlat, lon0),         # N
        (lat0,      lon0)          # origin
    ]

# connect
fc = m.connect_fc()

# arm
if not m.is_armed(fc):
    m.arm(fc)
    time.sleep(2)

# wps
wps = corner_coords(fc)

# loop through wps, GUIDED -> LOITER -> RPT
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







