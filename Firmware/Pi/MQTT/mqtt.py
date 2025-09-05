import time
import signal
import sys
import certifi
import paho.mqtt.client as mqtt

'''
Must listen on "pi/cmd" for commands from GUI
- "ping" -> respond with "pong"
- "cam" -> toggle camera (not implemented)
- "proxy" -> toggle proxy mode (not implemented)

Must publish to "pi/telem" for data to the GUI
- 
- 
- 
- 
- 

Must run on startup of the Pi
'''





# ==== Broker config ====
BROKER_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud"
BROKER_PORT = 8883
USERNAME    = "P4P-Buoy"
PASSWORD    = "P4P108buoy"

# ==== Topics ====
TOPIC_SUB = "pi/cmd"
TOPIC_PUB = "pi/telem"

running = True

def handle_sigint(sig, frame):
    global running
    running = False
signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] connected rc={rc}")
    # Subscribe when (re)connected
    client.subscribe([(TOPIC_SUB, 0)])

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace")
    print(f"[MQTT] {msg.topic} -> {payload}")
    # Example: respond to simple commands
    if msg.topic == TOPIC_SUB:
        if payload.lower() == "ping":
            client.publish(TOPIC_PUB, "pong")
        elif payload.lower().startswith("echo "):
            client.publish(TOPIC_PUB, payload[5:])
        elif payload.lower() == "reboot":
            client.publish(TOPIC_PUB, "reboot requested (not implemented)")
        # add your own handlers here

def on_disconnect(client, userdata, rc):
    print(f"[MQTT] disconnected rc={rc}")

def main():
    client = mqtt.Client(
        client_id="pi-client",
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
    )
    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(ca_certs=certifi.where())

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Async connect + loop_start lets us publish from the main thread
    client.connect_async(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()

    # do stuff here:
    

if __name__ == "__main__":
    main()
