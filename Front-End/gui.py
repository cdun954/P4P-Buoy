import sys, random, string
from PyQt5 import QtWidgets, QtCore
from PyQt5.uic import loadUi
import paho.mqtt.client as mqtt
import certifi

# ===== MQTT CONFIG =====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883 
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

TOPIC_TELEM_ESP = "esp/test"
TOPIC_TELEM_PI  = "pi/test"
TOPIC_CMD_ESP   = "esp/cmd"
TOPIC_CMD_PI    = "pi/cmd"


def _rand_id(prefix="gui-"):
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class GUI(QtWidgets.QMainWindow):
    # Signal from MQTT thread → UI thread
    mqtt_msg = QtCore.pyqtSignal(str, str)   # (topic, payload)
    mqtt_status = QtCore.pyqtSignal(str)     # status/log line

    def __init__(self):
        super(GUI, self).__init__()
        loadUi("Front-End/interface.ui", self)

        self.labelEsp = getattr(self, "recvesp_label", None)
        self.labelPi  = getattr(self, "recvpi_label",  None)
        self.btnSendEsp = getattr(self, "sendesp_button", None)
        self.btnSendPi  = getattr(self, "sendpi_button",  None)

        # Wire buttons (if present)
        if self.btnSendEsp:
            self.btnSendEsp.clicked.connect(
                lambda: self.publish(TOPIC_CMD_ESP, "hello from GUI")
            )
        if self.btnSendPi:
            self.btnSendPi.clicked.connect(
                lambda: self.publish(TOPIC_CMD_PI, "hello from GUI")
            )

        # Connect signals → UI slots
        self.mqtt_msg.connect(self.on_mqtt_msg_ui)
        self.mqtt_status.connect(self.on_mqtt_status_ui)

        # Start MQTT
        self._build_mqtt()
        self.show()

    # ---------- MQTT setup ----------
    def _build_mqtt(self):
        # Use loop_start() to run network loop in its own thread
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
        client.subscribe([(TOPIC_TELEM_ESP, 0), (TOPIC_TELEM_PI, 0)])

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
        if topic == TOPIC_TELEM_ESP and self.labelEsp:
            self.labelEsp.setText(payload)
        elif topic == TOPIC_TELEM_PI and self.labelPi:
            self.labelPi.setText(payload)
        # You can also append to a QTextEdit log if you have one
        if hasattr(self, "textLog"):  # optional log widget
            self.textLog.append(f"[{topic}] {payload}")

    @QtCore.pyqtSlot(str)
    def on_mqtt_status_ui(self, line):
        print(line)
        if hasattr(self, "textLog"):
            self.textLog.append(line)

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
