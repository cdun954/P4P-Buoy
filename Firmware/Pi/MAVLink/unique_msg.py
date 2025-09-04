from pymavlink import mavutil

master = mavutil.mavlink_connection('COM8', baud=115200)
master.wait_heartbeat()
print("Connected.")

seen_types = set()
while True:
    msg = master.recv_match(blocking=True)
    if msg:
        mtype = msg.get_type()
        if mtype not in seen_types:
            print(f"{mtype}:")
            print(msg)  # This prints all fields and values for that message type
            print("-" * 40)
            seen_types.add(mtype)
