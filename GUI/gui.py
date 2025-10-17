import sys, random, string
from PyQt5 import QtWidgets
from PyQt5 import QtCore
from PyQt5.QtWidgets import QPushButton, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.uic import loadUi
import paho.mqtt.client as mqtt
import certifi
import json
import csv, datetime, os

from graph import LiveGraphWindow


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

TOPIC_ESP_STATUS = "buoy/esp/status"
TOPIC_ESP_POWER  = "buoy/esp/power"
TOPIC_ESP_CMD    = "buoy/esp/cmd"

TOPIC_PI_STATUS  = "buoy/pi/status"
TOPIC_PI_AUTON   = "buoy/pi/autonomy"
TOPIC_PI_SENSOR  = "buoy/pi/sensor"
TOPIC_PI_CMD     = "buoy/pi/cmd"

# ===== CAMERA CONFIG =====
PI_IP = "100.69.169.69" # STATIC IP of the Pi
PORT = 5000
CAMERA_STREAM_URL = f"http://{PI_IP}:{PORT}/video_feed"


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

        self.power_data = []  # (timestamp, voltage, i_esp, i_pi, i_fc, i_modem)
        self.sensor_data = []  # (timestamp, turbidity, temperature, pH, nitrate, phosphate)

        self.powerGraphWin = None
        self.sensorGraphWin = None

        self.show()

    #=============================================#
    #                 GUI SETUP                   #
    #=============================================#
    def setupUi(self):
        #------------- CONTROL TAB ---------------#
        self.labelConnection = getattr(self, "connection_txt", None)
        self.load_data_button = self.findChild(QPushButton, 'loadDataButton')


        # Control Buttons
        self.btnMavproxy = self.findChild(QPushButton, 'mavproxy_btn')
        self.btnRcOverride = self.findChild(QPushButton, 'rc_btn')
        self.btnUpdate = self.findChild(QPushButton, 'update_btn')
        self.btnRtl = self.findChild(QPushButton, 'rtl_btn')
        self.btnPause = self.findChild(QPushButton, 'pause_btn')
        self.btnResume = self.findChild(QPushButton, 'resume_btn')
        self.btnMavproxy.clicked.connect(self.btnMavproxyFunc)
        self.btnRcOverride.clicked.connect(self.btnRCOverrideFunc)
        self.btnUpdate.clicked.connect(self.btnUpdateFunc)
        self.btnRtl.clicked.connect(self.btnRtlFunc)
        self.btnPause.clicked.connect(self.btnPauseFunc)
        self.btnResume.clicked.connect(self.btnResumeFunc)

        # Data Buttons
        self.btnDownloadPower = self.findChild(QPushButton, 'powerdl_btn')
        self.btnDownloadSensor = self.findChild(QPushButton, 'sensordl_btn')
        self.btnGraphPower = self.findChild(QPushButton, 'powergraph_btn')
        self.btnGraphSensor = self.findChild(QPushButton, 'sensorgraph_btn')
        self.btnDownloadPower.clicked.connect(self.btnDownloadPowerFunc)
        self.btnDownloadSensor.clicked.connect(self.btnDownloadSensorFunc)  
        self.btnGraphPower.clicked.connect(self.btnGraphPowerFunc)
        self.btnGraphSensor.clicked.connect(self.btnGraphSensorFunc)

        # Pi Status Labels
        self.labelMavproxy = self.findChild(QLabel, 'mavproxy_txt')
        self.labelCamera = self.findChild(QLabel, 'camera_txt')
        self.labelAutonomy = self.findChild(QLabel, 'autonomy_txt')
        self.labelPiState = self.findChild(QLabel, 'pistate_txt')

        # ESP Status Labels
        self.labelEspState = self.findChild(QLabel, 'espstate_txt')
        self.labelRelayFC = self.findChild(QLabel, 'relayfc_txt')
        self.labelRelayPi = self.findChild(QLabel, 'relaypi_txt')
        self.labelRelayModem = self.findChild(QLabel, 'relaymodem_txt')

        # FC Status Labels
        self.labelFCArmStatus = self.findChild(QLabel, 'fcarmstatus_txt')
        self.labelFCMode = self.findChild(QLabel, 'fcmode_txt')

        # Power Labels
        self.labelBattV = self.findChild(QLabel, 'battv_txt')
        self.labelEspA = self.findChild(QLabel, 'espa_txt')
        self.labelPiA = self.findChild(QLabel, 'pia_txt')
        self.labelFCA = self.findChild(QLabel, 'fca_txt')
        self.labelModemA = self.findChild(QLabel, 'modema_txt')

        # Sensor Labels
        self.labelSensTurbidity = self.findChild(QLabel, 'turbidity_txt')
        self.labelSensTemp = self.findChild(QLabel, 'temp_txt')
        self.labelSensPH = self.findChild(QLabel, 'ph_txt')
        self.labelSensNitrate = self.findChild(QLabel, 'nitrate_txt')
        self.labelSensPhosphate = self.findChild(QLabel, 'phosphate_txt')

        # Update Times Labels
        self.labelEspStatusTime = self.findChild(QLabel, 'espstatustime_txt')
        self.labelEspPowerTime = self.findChild(QLabel, 'esppowertime_txt')
        self.labelPiStatusTime = self.findChild(QLabel, 'pistatustime_txt')
        self.labelPiSensorTime = self.findChild(QLabel, 'pisensortime_txt')

        # heartbeats
        self.labelEspHeartbeat = self.findChild(QLabel, 'esphb_txt')
        self.labelPiHeartbeat = self.findChild(QLabel, 'pihb_txt')
        self._set_status_label(self.labelPiHeartbeat, False)
        self._set_status_label(self.labelEspHeartbeat, False)



        #------------- CAMERA TAB ----------------#
        # Camera Display
        self.cameraView = getattr(self, "cam_view", None)
        if self.cameraView: self.cameraView.setUrl(QtCore.QUrl(CAMERA_STREAM_URL))
        # Camera Button
        self.btnToggleCam = self.findChild(QPushButton, 'cam_btn')
        self.btnToggleCam.clicked.connect(self.btnCameraFunc)

        #------------ AUTONOMY TAB ---------------#
        self.autonomyView = self.findChild(QLabel, 'autonomy_view')

        # buttons
        self.btnToggleAutonomy = self.findChild(QPushButton, 'autonomy_btn')
        self.btnResetDefault = self.findChild(QPushButton, 'resetdefault_btn')
        self.btnToggleAutonomy.clicked.connect(self.btnAutonomyFunc)
        self.btnResetDefault.clicked.connect(self.btnResetDefaultFunc)
 
        # sliders
        self.sldrGridSize = self.findChild(QtWidgets.QSlider, 'gridsize_sldr')
        self.sldrEdgeRatio = self.findChild(QtWidgets.QSlider, 'edgeratio_sldr')
        self.sldrTravelSpeed = self.findChild(QtWidgets.QSlider, 'travelspeed_sldr')
        self.sldrLoiterRadius = self.findChild(QtWidgets.QSlider, 'loiterrad_sldr')
        self.sldrLoiterTime = self.findChild(QtWidgets.QSlider, 'loitertime_sldr')
        self.sldrMaxWpTime = self.findChild(QtWidgets.QSlider, 'maxwptime_sldr')

        # spin boxes
        self.spinGridSize = self.findChild(QtWidgets.QSpinBox, 'gridsize_spin')
        self.spinEdgeRatio = self.findChild(QtWidgets.QSpinBox, 'edgeratio_spin')
        self.spinTravelSpeed = self.findChild(QtWidgets.QDoubleSpinBox, 'travelspeed_spin')
        self.spinLoiterRadius = self.findChild(QtWidgets.QSpinBox, 'loiterrad_spin')
        self.spinLoiterTime = self.findChild(QtWidgets.QSpinBox, 'loitertime_spin')
        self.spinMaxWpTime = self.findChild(QtWidgets.QSpinBox, 'maxwptime_spin')

        # bind slider <-> spinbox
        self.bind_slider_spin(self.sldrGridSize,    self.spinGridSize)
        self.bind_slider_spin(self.sldrEdgeRatio,   self.spinEdgeRatio)
        self.bind_slider_spin(self.sldrTravelSpeed, self.spinTravelSpeed, 0.1, 1)
        self.bind_slider_spin(self.sldrLoiterRadius,self.spinLoiterRadius)
        self.bind_slider_spin(self.sldrLoiterTime,  self.spinLoiterTime)  
        self.bind_slider_spin(self.sldrMaxWpTime,   self.spinMaxWpTime)


        #------------- TESTING TAB ---------------#
        self.btnGuidedTest = self.findChild(QPushButton, 'guidedtest_btn')
        self.btnGuidedTest.clicked.connect(
            lambda: self.publish(TOPIC_PI_CMD, "guided_test")
        )

    # Minimal, clean slider <-> spin binder
    def bind_slider_spin(self, slider, spin, scale=1, decimals=None):
        is_double = isinstance(spin, QtWidgets.QDoubleSpinBox)
        if is_double and decimals is not None:
            spin.setDecimals(decimals)
        # Set spin range to reflect slider range (scaled)
        if is_double:
            spin.setRange(slider.minimum()*scale, slider.maximum()*scale)
        else:
            spin.setRange(int(slider.minimum()*scale), int(slider.maximum()*scale))

        def s2sp(v):
            QtCore.QSignalBlocker(spin)
            spin.setValue(v*scale)

        def sp2s(x):
            QtCore.QSignalBlocker(slider)
            iv = int(round(float(x)/scale)) if scale else slider.value()
            iv = max(slider.minimum(), min(slider.maximum(), iv))
            slider.setValue(iv)

        slider.valueChanged.connect(s2sp)
        spin.valueChanged.connect(sp2s)
        s2sp(slider.value())  # init



    #=============================================#
    #                 BTN FUNCs                   #
    #=============================================#

    def btnMavproxyFunc(self):
        self.publish(TOPIC_PI_CMD, "toggle_mavproxy")
    
    def btnRCOverrideFunc(self):
        self.publish(TOPIC_PI_CMD, "rc_override")

    def btnUpdateFunc(self):
        self.publish(TOPIC_PI_CMD, "update")
        self.publish(TOPIC_ESP_CMD, "update")

    def btnRtlFunc(self):
        self.publish(TOPIC_PI_CMD, "rtl")

    def btnPauseFunc(self):
        self.publish(TOPIC_PI_CMD, "pause")
        self.publish(TOPIC_ESP_CMD, "pause")
    
    def btnResumeFunc(self):
        self.publish(TOPIC_PI_CMD, "resume")
        self.publish(TOPIC_ESP_CMD, "resume")

    def btnDownloadPowerFunc(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_rows_to_csv(self.power_data, f"power_data_{ts}.csv")
        self.power_data = []

    def btnDownloadSensorFunc(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._save_rows_to_csv(self.sensor_data, f"sensor_data_{ts}.csv")
        self.sensor_data = []

    def btnGraphPowerFunc(self):
        # Panels for power_data
        panels = [
            {
                "title": "Battery Voltage (V)",
                "series": [
                    {"key": "v_batt", "name": "V_batt"},
                ],
            },
            {
                "title": "Currents (A)",
                "series": [
                    {"key": "i_esp",   "name": "ESP"},
                    {"key": "i_pi",    "name": "Pi"},
                    {"key": "i_fc",    "name": "FC"},
                    {"key": "i_modem", "name": "Modem"},
                ],
            },
        ]
        if self.powerGraphWin is None or not self.powerGraphWin.isVisible():
            self.powerGraphWin = LiveGraphWindow(
                data_ref=self.power_data,
                panels=panels,
                x_mode="timestamp",   # "timestamp" also supported but "index" is simplest
                max_points=1200,  # last ~1200 samples
                update_ms=300,
                parent=self,
            )
            self.powerGraphWin.show()
        else:
            self.powerGraphWin.raise_()
            self.powerGraphWin.activateWindow()

    def btnGraphSensorFunc(self):
        # Panels for sensor_data (group however you like)
        panels = [
            {
                "title": "Water Quality",
                "series": [
                    {"key": "turbidity", "name": "Turbidity (NTU)"},
                    {"key": "temperature", "name": "Temp (°C)"},
                    {"key": "ph", "name": "pH"},
                ],
            },
            {
                "title": "Nutrients (mg/L)",
                "series": [
                    {"key": "nitrate", "name": "Nitrate"},
                    {"key": "phosphate", "name": "Phosphate"},
                ],
            },
        ]
        if self.sensorGraphWin is None or not self.sensorGraphWin.isVisible():
            self.sensorGraphWin = LiveGraphWindow(
                data_ref=self.sensor_data,
                panels=panels,
                x_mode="timestamp",
                max_points=1200,
                update_ms=300,
                parent=self,
            )
            self.sensorGraphWin.show()
        else:
            self.sensorGraphWin.raise_()
            self.sensorGraphWin.activateWindow()

    # cam
    def btnCameraFunc(self):
        self.publish(TOPIC_PI_CMD, "toggle_cam")
        if self.cameraView:
            self.cameraView.setUrl(QtCore.QUrl(CAMERA_STREAM_URL))

    # auton
    def btnAutonomyFunc(self):
        grid_size = self.spinGridSize.value()
        edge_ratio = self.spinEdgeRatio.value() / 100.0
        travel_speed = self.spinTravelSpeed.value()
        loiter_radius = self.spinLoiterRadius.value()
        loiter_time = self.spinLoiterTime.value()
        max_wp_time = self.spinMaxWpTime.value()

        args = {
            "grid_size": grid_size,
            "edge_ratio": edge_ratio,
            "travel_speed": travel_speed,
            "loiter_radius": loiter_radius,
            "loiter_time": loiter_time,
            "max_wp_time": max_wp_time,
            "mavproxy": True,
        }
        payload = "toggle_autonomy " + json.dumps(args, separators=(',', ':'))
        self.publish(TOPIC_PI_CMD, payload)

    def btnResetDefaultFunc(self):
        # sliders
        self.sldrGridSize.setValue(15)      # 15
        self.sldrEdgeRatio.setValue(65)     # 0.65
        self.sldrTravelSpeed.setValue(10)   # 1.0 m/s
        self.sldrLoiterRadius.setValue(5)   # 5 m
        self.sldrLoiterTime.setValue(20)    # 2.0 s
        self.sldrMaxWpTime.setValue(10)    # 10.0 s

        # spinboxes
        self.spinGridSize.setValue(15)
        self.spinEdgeRatio.setValue(65)
        self.spinTravelSpeed.setValue(1.2)
        self.spinLoiterRadius.setValue(5)
        self.spinLoiterTime.setValue(20)
        self.spinMaxWpTime.setValue(10)

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
    
    def _set_status_label(self, label, on):
        if not label:
            return
        if on:
            label.setText("ACTIVE")
            label.setStyleSheet("color: rgb(0,170,0);")  # green
        else:
            label.setText("INACTIVE")
            label.setStyleSheet("color: rgb(220,0,0);")  # red

    def _save_rows_to_csv(self, rows, suggested_name):
        if not rows:
            QtWidgets.QMessageBox.information(self, "No data", "No data to download yet.")
            return
        # Build consistent header = union of keys across rows, with 'timestamp' first if present
        all_keys = set().union(*[r.keys() for r in rows])
        header = ["timestamp"] + sorted(k for k in all_keys if k != "timestamp")

        # Ask user where to save (default filename provided)
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save CSV",
            os.path.join(os.getcwd(), suggested_name),
            "CSV Files (*.csv)"
        )
        if not path:
            return

        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            for r in rows:
                w.writerow(r)

        QtWidgets.QMessageBox.information(self, "Saved", f"Saved {len(rows)} rows to:\n{path}")
    
    # incoming MQTT messages
    def updateEspPower(self, payload):
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[ESP Power] bad JSON: {e}")
            return

        self.power_data.append({
            "timestamp": QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"),
            **d
        })
        
        # Power/state fields
        self.labelBattV.setText(self._fmt_num(d.get("v_batt"), 2, "V"))
        self.labelEspA.setText(self._fmt_num(d.get("i_esp"),  3, "A"))
        self.labelPiA.setText(self._fmt_num(d.get("i_pi"),   3, "A"))
        self.labelFCA.setText(self._fmt_num(d.get("i_fc"),   3, "A"))
        self.labelModemA.setText(self._fmt_num(d.get("i_modem"), 3, "A"))

        self.labelEspPowerTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))

    def updatePiSensor(self, payload):
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[Pi Sensor] bad JSON: {e}")
            return

        self.sensor_data.append({
            "timestamp": QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"),
            **d
        })
        
        # Sensor fields
        self.labelSensTurbidity.setText(self._fmt_num(d.get("turbidity"), 2, "NTU"))
        self.labelSensTemp.setText(self._fmt_num(d.get("temperature"), 2,"°C"))
        self.labelSensPH.setText(self._fmt_num(d.get("ph"), 2, "pH"))
        self.labelSensNitrate.setText(self._fmt_num(d.get("nitrate"), 2, "mg/L"))
        self.labelSensPhosphate.setText(self._fmt_num(d.get("phosphate"), 2, "mg/L"))

        self.labelPiSensorTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))
    
    def updateEspStatus(self, payload):
        self._set_status_label(self.labelEspHeartbeat, True)        
        try:
            self.espHbTimer.stop()
        except Exception:
            pass
        self.espHbTimer = QtCore.QTimer()
        self.espHbTimer.setSingleShot(True)
        self.espHbTimer.timeout.connect(lambda: self._set_status_label(self.labelEspHeartbeat, False))
        self.espHbTimer.start(10000)
        
        
        
        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[ESP Status] bad JSON: {e}")
            return

        # ESP power-state (string)
        self.labelEspState.setText(str(d.get("state", "—")).upper())

        # Relay labels (ON/OFF text)
        self._set_status_label(self.labelRelayPi, d.get("relay_pi", False))
        self._set_status_label(self.labelRelayFC, d.get("relay_fc", False))
        self._set_status_label(self.labelRelayModem, d.get("relay_modem", False))

        self.labelEspStatusTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))

    def updatePiStatus(self, payload):
        self._set_status_label(self.labelPiHeartbeat, True)

        try:
            self.piHbTimer.stop()
        except Exception:
            pass
        self.piHbTimer = QtCore.QTimer()
        self.piHbTimer.setSingleShot(True)
        self.piHbTimer.timeout.connect(lambda: self._set_status_label(self.labelPiHeartbeat, False))
        self.piHbTimer.start(10000)

        try:
            d = json.loads(payload)
        except Exception as e:
            print(f"[Pi Status] bad JSON: {e}")
            return
        
        # FC state fields
        self.labelFCArmStatus.setText(self._onoff(d.get("fc_armed", False)))
        self.labelFCMode.setText(str(d.get("fc_mode", "—")).upper())

        # other status
        self._set_status_label(self.labelMavproxy, d.get("mavproxy_on", False))
        self._set_status_label(self.labelCamera, d.get("camera_on", False))
        self._set_status_label(self.labelAutonomy, d.get("autonomy_on", False))
        self.labelPiState.setText(str(d.get("state", "—")).upper())

        self.labelPiStatusTime.setText(QtCore.QDateTime.currentDateTime().toString("HH:mm:ss"))

    def updateAutonomy(self, payload):
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
        # Subscribe to telemetry
        client.subscribe([
            (TOPIC_ESP_STATUS, 0), 
            (TOPIC_ESP_POWER, 0), 
            (TOPIC_PI_STATUS, 0), 
            (TOPIC_PI_SENSOR, 0),
            (TOPIC_PI_AUTON, 0)
            ])

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
        if topic == TOPIC_ESP_STATUS:
            self.updateEspStatus(payload)
        elif topic == TOPIC_ESP_POWER:
            self.updateEspPower(payload)
        elif topic == TOPIC_PI_STATUS:
            self.updatePiStatus(payload)
        elif topic == TOPIC_PI_SENSOR:
            self.updatePiSensor(payload)
        elif topic == TOPIC_PI_AUTON:
            self.updateAutonomy(payload)
        else:
            print(f"[MQTT] Unknown topic: {topic}")


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
