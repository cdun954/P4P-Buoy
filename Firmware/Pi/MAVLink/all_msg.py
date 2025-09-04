from pymavlink import mavutil

master = mavutil.mavlink_connection('COM8', baud=115200)
master.wait_heartbeat()
print("Connected.")

seen_types = set()
while True:
    msg = master.recv_match(blocking=True)
    if msg:
        print(f"SENT: {msg.get_type()}")
