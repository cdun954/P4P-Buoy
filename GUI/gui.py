import sys, random, string
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWebEngineWidgets import QWebEngineView
import paho.mqtt.client as mqtt
from PyQt5.uic import loadUi
import certifi
import json

"""
gui.py 

The PyQt5 GUI application for the P4P Buoy project.
Features:
- Full GUI with tabs for Control, Camera, Autonomy, and Testing
- Communicates with the Raspberry Pi and ESP32 via MQTT
- Displays live camera feed from the Pi
- Displays telemetry data and system status
- Displays autonomy status and visualisation
"""

# ==== PYQT5 SETUP =====
UI_FILE = "GUI/gui.ui"

# ===== MQTT CONFIG =====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883 
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

TOPIC_STATUS_ESP = "buoy/esp/status"
TOPIC_POWER_ESP  = "buoy/esp/power"
TOPIC_CMD_ESP    = "buoy/esp/cmd"
TOPIC_STATUS_PI  = "buoy/pi/status"
TOPIC_AUTON_PI   = "buoy/pi/autonomy"
TOPIC_SENSOR_PI  = "buoy/pi/sensor"
TOPIC_CMD_PI     = "buoy/pi/cmd"

# ===== CAMERA CONFIG =====
PI_IP = "100.69.169.69" # STATIC IP of the Pi
PORT = 5000
CAMERA_STREAM_URL = f"http://{PI_IP}:{PORT}/video_feed"

# ===== VARIABLES ===== uneeded?
mavproxy_on = False  # Whether MAVLink comms is active
system_state = False  # RC, AUTO, IDLE, etc.


# ===== HELPERS =====
def _rand_id(prefix="gui-"):
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class GUI(QtWidgets.QMainWindow):
    # Signal from MQTT thread → UI thread
    mqtt_msg = QtCore.pyqtSignal(str, str)   # (topic, payload)
    mqtt_status = QtCore.pyqtSignal(str)     # status/log line

    def __init__(self):
        super(GUI, self).__init__()
        loadUi(UI_FILE, self)

        self.setupUi()
        self.setupMQTT()
        self.setupButtons()

        self.show()

    #=============================================#
    #                 GUI SETUP                   #
    #=============================================#
    def setupUi(self):
        #------------- CONTROL TAB ---------------#
        self.labelConnection = getattr(self, "connection_txt", None)

        # Control Buttons
        self.btnMavproxy = getattr(self, "mavproxy_btn", None)
        self.btnRcOverride = getattr(self, "rc_btn", None)
        self.btnUpdate = getattr(self, "update_btn", None)
        self.btnRtl = getattr(self, "rtl_btn", None)
        self.btnPause = getattr(self, "pause_btn", None)
        self.btnResume = getattr(self, "resume_btn", None)

        # Pi Status Labels
        self.labelMavproxy = getattr(self, "mavproxy_txt", None)
        self.labelPiStatusTime = getattr(self, "pistatustime_txt", None)
        self.labelPiState = getattr(self, "pistate_txt", None)

        # ESP Status Labels
        self.labelEspStatusTime = getattr(self, "espstatustime_txt", None)
        self.labelEspState = getattr(self, "espstate_txt", None)
        self.labelRelayFC = getattr(self, "relayfc_txt", None)
        self.labelRelayPi = getattr(self, "relaypi_txt", None)
        self.labelRelayModem = getattr(self, "relaymodem_txt", None)

        # FC Status Labels
        self.labelFCArmStatus = getattr(self, "fcarmstatus_txt", None)
        self.labelFCMode = getattr(self, "fcmode_txt", None)

        # Power Labels
        self.labelBattV = getattr(self, "battv_txt", None)
        self.labelEspA = getattr(self, "espa_txt", None)
        self.labelPiA = getattr(self, "pia_txt", None)
        self.labelFCA = getattr(self, "fca_txt", None)
        self.labelModemA = getattr(self, "modema_txt", None)
        self.labelEspPowerTime = getattr(self, "esppowertime_txt", None)

        # Sensor Labels
        #TODO:

        # Update Time Label
        self.labelUpdateTime = getattr(self, "updatetime_txt", None)

        #------------- CAMERA TAB ----------------#
        # Camera Display
        self.cameraView = getattr(self, "cam_view", None)
        if self.cameraView: self.cameraView.setUrl(QtCore.QUrl(CAMERA_STREAM_URL))
        # Camera Button
        self.btnToggleCam = getattr(self, "cam_btn", None)

        #------------ AUTONOMY TAB ---------------#
        #TODO:

        #------------- TESTING TAB ---------------#
        # Send Buttons
        self.btnGuidedTest = getattr(self, "guidedtest_btn", None)

    def setupButtons(self):
        #------------- CONTROL TAB ---------------#
        if self.btnMavproxy:
            self.btnMavproxy.clicked.connect(self.btnMavproxyFunc)

        if self.btnRcOverride:
            self.btnRcOverride.clicked.connect(
                lambda: self.publish(TOPIC_CMD_PI, "toggle_rc_override")
            )

        if self.btnUpdate:
            self.btnUpdate.clicked.connect(
                lambda: (self.publish(TOPIC_CMD_PI, "update"), 
                          self.publish(TOPIC_CMD_ESP, "update"))
            )

        if self.btnRtl:
            self.btnRtl.clicked.connect(
                lambda: self.publish(TOPIC_CMD_ESP, "rtl")
            )
        
        if self.btnPause:
            self.btnPause.clicked.connect(
                lambda: (self.publish(TOPIC_CMD_PI, "pause"),
                          self.publish(TOPIC_CMD_ESP, "pause"))
            )

        if self.btnResume:
            self.btnResume.clicked.connect(
                lambda: (self.publish(TOPIC_CMD_PI, "resume"),
                          self.publish(TOPIC_CMD_ESP, "resume"))
            )

        #------------- CAMERA TAB ----------------#
        if self.btnToggleCam:
            self.btnToggleCam.clicked.connect(
                lambda: self.publish(TOPIC_CMD_PI, "toggle_cam")
            )

        #------------ AUTONOMY TAB ---------------#
        #TODO:

        #------------- TESTING TAB ---------------#
        if self.btnGuidedTest:
            self.btnGuidedTest.clicked.connect(
                lambda: self.publish(TOPIC_CMD_PI, "guided_test")
            )


    #=============================================#
    #                 BTN FUNCs                   #
    #=============================================#
    def btnMavproxyFunc(self):
        global mavproxy_on
        mavproxy_on = not mavproxy_on
        self.publish(TOPIC_CMD_PI, "toggle_mavproxy")
        self._set_status_label(self.labelMavproxy, mavproxy_on)
    
    def btnRCOverrideFunc(self):
        self.publish(TOPIC_CMD_PI, "toggle_rc_override")

    def _set_status_label(self, label, on):
        if not label:
            return
        if on:
            label.setText("ACTIVE")
            label.setStyleSheet("color: rgb(0,170,0);")  # green
        else:
            label.setText("INACTIVE")
            label.setStyleSheet("color: rgb(220,0,0);")  # red


    #=============================================#
    #                 RECV MQTT                   #
    #=============================================#
    # helpers
    def _fmt_num(self, val, ndp=2, unit=""):
        try:
            s = f"{float(val):.{ndp}f}"
            return f"{s} {unit}".strip()
        except Exception:
            return "—"

    def _onoff(self, val):
        return "ON" if bool(val) else "OFF"
    
    def updateEspPower(self, payload):
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[ESP Power] bad JSON: {e}")
            return
        
        # Power/state fields
        if self.labelBattV:   self.labelBattV.setText(self._fmt_num(d.get("v_batt"), 2, "V"))
        if self.labelEspA:    self.labelEspA.setText(self._fmt_num(d.get("i_esp"),  3, "A"))
        if self.labelPiA:     self.labelPiA.setText(self._fmt_num(d.get("i_pi"),   3, "A"))
        if self.labelFCA:     self.labelFCA.setText(self._fmt_num(d.get("i_fc"),   3, "A"))
        if self.labelModemA:  self.labelModemA.setText(self._fmt_num(d.get("i_modem"), 3, "A"))

        if self.labelEspPowerTime:
            self.labelEspPowerTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))

    def updatePiSensor(self, payload):
        # pi sensor updates should be seperate to other status, more frequent
        pass
    
    def updateEspStatus(self, payload):
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[ESP Status] bad JSON: {e}")
            return

        # ESP power-state (string)
        if self.labelEspState:
            self.labelEspState.setText(str(d.get("state", "—")).upper())

        # Relay labels (ON/OFF text)
        if self.labelRelayPi:     self.labelRelayPi.setText(self._onoff(d.get("relay_pi")))
        if self.labelRelayFC:     self.labelRelayFC.setText(self._onoff(d.get("relay_fc")))
        if self.labelRelayModem:  self.labelRelayModem.setText(self._onoff(d.get("relay_modem")))

        if self.labelEspStatusTime:
            self.labelEspStatusTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))

    def updatePiStatus(self, payload):
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[ESP Status] bad JSON: {e}")
            return
        
        # FC state fields

        # Mavproxy status
        if self.labelMavproxy:
            self._set_status_label(self.labelMavproxy, d.get("mavproxy_on", False))
        
        pass

    #=============================================#
    #                 MQTT SETUP                  #
    #=============================================#
    def setupMQTT(self):
        # Connect signals --> UI slots
        self.mqtt_msg.connect(self.on_mqtt_msg_ui)
        self.mqtt_status.connect(self.on_mqtt_status_ui)
        self._build_mqtt()

    def _build_mqtt(self):
        self.mqtt = mqtt.Client(
            client_id=_rand_id("dashboard-"),
            clean_session=True,
            protocol=mqtt.MQTTv311,
            transport="tcp",
        )
        self.mqtt.username_pw_set(USERNAME, PASSWORD)
        self.mqtt.tls_set(ca_certs=certifi.where())  # TLS root CA

        self.mqtt.on_connect = self._on_connect
        self.mqtt.on_message = self._on_message
        self.mqtt.on_disconnect = self._on_disconnect

        self.mqtt_status.emit("[MQTT] Connecting…")
        # async connect + start loop
        self.mqtt.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
        self.mqtt.loop_start()

    # ---------- MQTT callbacks (background thread) ----------
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        self.mqtt_status.emit(f"[MQTT] Connected (rc={rc})")
        client.subscribe([(TOPIC_STATUS_ESP, 0), (TOPIC_POWER_ESP, 0), (TOPIC_STATUS_PI, 0), (TOPIC_SENSOR_PI, 0)])
        # Subscribe to telemetry

    def _on_message(self, client, userdata, msg):
        payload = msg.payload.decode(errors="replace")
        # Emit to UI thread
        self.mqtt_msg.emit(msg.topic, payload)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        self.mqtt_status.emit(f"[MQTT] Disconnected (rc={rc})")

    # ---------- Publish from UI thread ----------
    def publish(self, topic, payload):
        try:
            # no wait: fire-and-forget
            self.mqtt.publish(topic, payload, qos=0, retain=False)
            self.mqtt_status.emit(f"➡ Published {topic}: {payload}")
        except Exception as e:
            self.mqtt_status.emit(f"[MQTT] Publish error: {e}")

    # ---------- Slots (UI thread) ----------
    @QtCore.pyqtSlot(str, str)
    def on_mqtt_msg_ui(self, topic, payload):
        # Update specific labels if present
        if topic == TOPIC_STATUS_ESP:
            self.updateEspStatus(payload)
        elif topic == TOPIC_POWER_ESP:
            self.updateEspPower(payload)
        elif topic == TOPIC_STATUS_PI:
            self.updatePiStatus(payload)
        elif topic == TOPIC_SENSOR_PI:
            self.updatePiSensor(payload)


    @QtCore.pyqtSlot(str)
    def on_mqtt_status_ui(self, line):
        print(line)

    # Clean shutdown
    def closeEvent(self, event):
        try:
            self.mqtt_status.emit("[MQTT] Shutting down…")
            self.mqtt.loop_stop()
            self.mqtt.disconnect()
        except Exception:
            pass
        event.accept()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = GUI()
    sys.exit(app.exec_())
