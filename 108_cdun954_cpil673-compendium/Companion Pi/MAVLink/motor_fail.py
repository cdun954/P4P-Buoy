from pymavlink import mavutil
import time

# Connect to the Pixhawk via serial (update port as needed)
master = mavutil.mavlink_connection('COM8', baud=115200)

# Wait for a heartbeat
master.wait_heartbeat()
print("Heartbeat received.")

# Wait for the next HEARTBEAT
# check the current mode
while True:
    msg = master.recv_match(type='HEARTBEAT', blocking=True)
    if msg:
        mode = mavutil.mode_string_v10(msg)
        print(f"Current Mode: {mode}")
        break

# Arm the vehicle
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 1, 0, 0, 0, 0, 0, 0
)
print("Sent ARM command.")

# Wait a couple seconds for arm to take effect
time.sleep(5)


# Manually set servo output to 1070 on servo 1
'''
This cannot work as manually setting servo outputs is not supported in SERVOX_FUNCTION 73/74
Must be done via RC override or temporary servo function change to 0/1
'''
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
    0,        # Confirmation
    1,        # Servo output number (1-8 MAIN, 9-14 AUX)
    1700,     # PWM value (μs)
    0,0,0,0,0 # Unused params
)
print("Set servo 1 to 1700 μs.")

time.sleep(2)

# Manually reset servo output
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
    0,        # Confirmation
    1,        # Servo output number (1-8 MAIN, 9-14 AUX)
    1500,     # PWM value (μs)
    0,0,0,0,0 # Unused params
)
print("Reset servo 1.")

# Disarm the vehicle
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 0, 0, 0, 0, 0, 0, 0
)
print("Disarmed.")
