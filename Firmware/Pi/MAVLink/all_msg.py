from pymavlink import mavutil

master = mavutil.mavlink_connection('tcp:0.0.0.0:5762')
print("Waiting for heartbeat...")
master.wait_heartbeat()
print("Connected.")

seen_types = set()
while True:
    msg = master.recv_match(blocking=True)
    if msg:
        print(f"SENT: {msg.get_type()}")
