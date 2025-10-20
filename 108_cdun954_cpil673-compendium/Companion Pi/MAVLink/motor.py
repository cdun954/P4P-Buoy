from pymavlink import mavutil
import time

# Connect to the Pixhawk via serial (update port as needed)
master = mavutil.mavlink_connection('COM8', baud=115200)

# Wait for a heartbeat
master.wait_heartbeat()
print("Heartbeat received.")

# Arm the vehicle
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 1, 0, 0, 0, 0, 0, 0
)
print("Sent ARM command.")

# Wait a couple seconds for arm to take effect
time.sleep(2)

# RC channel override: set channel 1 (steering) to 1700, others remain unchanged (0)
master.mav.rc_channels_override_send(
    master.target_system,
    master.target_component,
    1500, 0, 1600, 0, 0, 0, 0, 0  # CH1=1550, rest=0 (no override)
)
print("Set RC channel 1 (steering) to 1600.")

time.sleep(0.5)
# RC override: reset channel 1 (steering)   
master.mav.rc_channels_override_send(
    master.target_system,
    master.target_component,
    1500, 0, 1500, 0, 0, 0, 0, 0
)
print("Reset RC channel 1 (steering) to neutral (1500).")

# Disarm the vehicle
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
    0, 0, 0, 0, 0, 0, 0, 0
)
print("Disarmed.")
