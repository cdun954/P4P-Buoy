import time
import signal
import sys
import certifi
import paho.mqtt.client as mqtt

# ==== Broker config ====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

# ==== Topics ====  
TOPIC_SUB = "pi/cmd"
TOPIC_PUB = "pi/telem"

running = True

def parse_cmd(payload: str):
    """Return (cmd:str, args:str|None). Accepts 'cmd' or 'cmd arg text'."""
    s = payload.strip()
    if not s:
        return "", None
    parts = s.split(maxsplit=1)
    return parts[0].lower(), (parts[1] if len(parts) > 1 else None)

def cmd_update(client, args):
    # TODO:
    pass

def cmd_cam(client, args):
    # if camera is on, turn off
    # else turn on
    # done by opening/closing the pi_stream script
    pass

def cmd_proxy(client, args):
    # if mavproxy is on, turn off
    # else turn on
    # done by opening/closing the mavproxy script

    pass

# Map command keyword -> handler
DISPATCH = {
    "update": cmd_update,
    "cam":    cmd_cam,
    "proxy":  cmd_proxy,
}

# ---------- MQTT callbacks ----------
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] connected rc={rc}")
    client.subscribe([(TOPIC_SUB, 0)])

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace")
    print(f"[MQTT] {msg.topic} -> {payload}")
    if msg.topic != TOPIC_SUB:
        return
    cmd, args = parse_cmd(payload)
    handler = DISPATCH.get(cmd)
    if handler:
        try:
            handler(client, args)
        except Exception as e:
            # incorrect cmd
            pass
 
def on_disconnect(client, userdata, rc):
    print(f"[MQTT] disconnected rc={rc}")

def build_client():
    c = mqtt.Client(
        client_id="pi-cmd-hub",
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    c.username_pw_set(USERNAME, PASSWORD)
    c.tls_set(ca_certs=certifi.where())
    c.on_connect = on_connect
    c.on_message = on_message
    c.on_disconnect = on_disconnect
    c.reconnect_delay_set(min_delay=1, max_delay=30)
    return c

def _stop(*_):
    global running
    running = False

signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)

def main():
    client = build_client()
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()

    while running:
        time.sleep(1)

if __name__ == "__main__":
    main()

