from pymavlink import mavutil

# ===== Configuration =====
FC_SERIAL_PORT = '/dev/ttyACM0'            # Adjust if needed
FC_BAUDRATE = 115200
GCS_UDP_ADDR = '100.69.169.70'             # Your GCS IP
GCS_UDP_PORT = 14550                       # Mission Planner default

# ===== Setup MAVLink connections =====
fc = mavutil.mavlink_connection(FC_SERIAL_PORT, baud=FC_BAUDRATE)
gcs = mavutil.mavlink_connection(f'udpout:{GCS_UDP_ADDR}:{GCS_UDP_PORT}')

# ===== Wait for FC heartbeat to confirm connection =====
fc.wait_heartbeat()

# ===== Foward messages between FC and GCS =====
while True:
    # FC → GCS
    fc_msg = fc.recv_match(blocking=False)
    if fc_msg:
        gcs.write(fc_msg.get_msgbuf())
    # GCS → FC
    gcs_msg = gcs.recv_match(blocking=False)
    if gcs_msg:
        fc.write(gcs_msg.get_msgbuf()) 