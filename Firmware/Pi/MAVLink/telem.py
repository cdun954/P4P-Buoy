from pymavlink import mavutil
import time

# Change to your Pixhawk serial port and baud rate
master = mavutil.mavlink_connection('COM8', baud=115200)
master.wait_heartbeat()
print("Heartbeat received.")

# Request streams at your preferred rate (optional, usually only needed on radios)
# master.mav.request_data_stream_send(
#     master.target_system,
#     master.target_component,
#     mavutil.mavlink.MAV_DATA_STREAM_ALL,
#     5,  # 5 Hz
#     1   # Start
# )

# Store latest message of each type
latest = {
    "heartbeat": None,
    "global_position": None,
    "gps_raw": None,
    "attitude": None,
    "servo_output": None,
    "sys_status": None,
    "battery_status": None,
    "rc_channels": None,
    "statustext": None
}

def print_report():
    print("\n===== TELEMETRY REPORT [{}] =====".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    hb = latest["heartbeat"]
    if hb:
        mode = mavutil.mode_string_v10(hb)
        armed = "ARMED" if hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED else "DISARMED"
        print(f"Flight Mode: {mode} | {armed}")
    gps = latest["global_position"]
    gps_raw = latest["gps_raw"]
    if gps:
        print(f"GPS:   Lat: {gps.lat/1e7:.7f}, Lon: {gps.lon/1e7:.7f}, Alt: {gps.alt/1000:.2f} m")
        print(f"       Rel Alt: {gps.relative_alt/1000:.2f} m, Heading: {gps.hdg/100.0:.1f}°, Vx: {gps.vx} cm/s, Vy: {gps.vy} cm/s, Vz: {gps.vz} cm/s")
    if gps_raw:
        print(f"       GPS Fix: {gps_raw.fix_type} | Sats: {gps_raw.satellites_visible} | HDOP: {gps_raw.eph/100.0:.2f}")
    att = latest["attitude"]
    if att:
        print(f"Attitude: Roll: {att.roll:.3f} rad, Pitch: {att.pitch:.3f} rad, Yaw: {att.yaw:.3f} rad")
    servo = latest["servo_output"]
    if servo:
        outputs = [servo.servo1_raw, servo.servo2_raw, servo.servo3_raw, servo.servo4_raw,
                   servo.servo5_raw, servo.servo6_raw, servo.servo7_raw, servo.servo8_raw]
        print(f"Servo Outputs [MAIN1-8]: {outputs}")
    rc = latest["rc_channels"]
    if rc:
        rc_values = [rc.chan1_raw, rc.chan2_raw, rc.chan3_raw, rc.chan4_raw, rc.chan5_raw, rc.chan6_raw, rc.chan7_raw, rc.chan8_raw]
        print(f"RC Inputs: {rc_values}")
    sysstat = latest["sys_status"]
    if sysstat:
        vbat = sysstat.voltage_battery / 1000.0
        curr = sysstat.current_battery / 100.0
        print(f"Battery: {vbat:.2f} V, {curr:.2f} A, Remaining: {sysstat.battery_remaining}%")
    batt = latest["battery_status"]
    if batt:
        cell_voltages = [v/1000.0 for v in batt.voltages if v != 0xFFFF]
        print(f"  Battery Cells (V): {cell_voltages}")
    status = latest["statustext"]
    if status:
        print(f"StatusMsg: {status.text}")
    print("="*44)

# Main loop: update and print latest telemetry every second
last_print = time.time()
while True:
    msg = master.recv_match(blocking=True, timeout=1)
    if msg:
        mtype = msg.get_type()
        if mtype == "HEARTBEAT":
            latest["heartbeat"] = msg
        elif mtype == "GLOBAL_POSITION_INT":
            latest["global_position"] = msg
        elif mtype == "GPS_RAW_INT":
            latest["gps_raw"] = msg
        elif mtype == "ATTITUDE":
            latest["attitude"] = msg
        elif mtype == "SERVO_OUTPUT_RAW":
            latest["servo_output"] = msg
        elif mtype == "SYS_STATUS":
            latest["sys_status"] = msg
        elif mtype == "BATTERY_STATUS":
            latest["battery_status"] = msg
        elif mtype == "RC_CHANNELS":
            latest["rc_channels"] = msg
        elif mtype == "STATUSTEXT":
            latest["statustext"] = msg
    if time.time() - last_print > 1:
        print_report()
        last_print = time.time()
