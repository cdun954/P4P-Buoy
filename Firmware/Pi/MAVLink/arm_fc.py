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