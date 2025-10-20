from pymavlink import mavutil

# Connect to Pixhawk
master = mavutil.mavlink_connection('COM8', baud=115200)
master.wait_heartbeat()
print("Connected.")

# Send reboot command
master.mav.command_long_send(
    master.target_system,
    master.target_component,
    mavutil.mavlink.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,  # Command ID 246
    0,      # Confirmation
    1,      # param1: 1 = reboot autopilot (0 = do nothing, 3 = reboot autopilot and keep it in bootloader)
    0, 0, 0, 0, 0, 0  # params 2-7 unused
)
print("Sent FC reboot command.")
