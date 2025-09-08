#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>

""" 
main.ino

Power management controller
Features:
- Manages power states based on battery voltage
- Handles MQTT commands from GCS
- Controls relays for power distribution
- Monitors current and voltage via ADC
- FSM with states: FULL, MID, LOW, CRIT
"""

/*==============================
          CONSTANTS
===============================*/ 
// ======== MAVLink ==========
// TODO:

// ======== PI GPIO ==========
#define PI_SHUTDOWN_PIN  4??

// ======== Relays ==========
#define RELAY_PI_PIN     23
#define RELAY_MODEM_PIN  22
#define RELAY_FC_PIN     21

// ======== ADC ==========
#define ADC_I_PI_PIN     36
#define ADC_I_FC_PIN     39
#define ADC_I_MODEM_PIN  34
#define ADC_I_ESP_PIN    35
#define ADC_V_BATT_PIN   32

const float ADC_VREF      = 3.3;      // ESP32 ADC reference (Volts)
const int   ADC_RES       = 12;       // 12-bit ADC
const float ADC_MAX       = 4095;     // 12-bit ADC
const float ADC_I_CONV    = 69;       // current sensor conversion factor
const float ADC_V_CONV    = 69;       // voltage battery conversion factor

// ======== Voltage Thresholds ==========
const float V_HYSTERESIS    = 0.3;
const float V_MID_BOUNDARY  = 14.8;
const float V_LOW_BOUNDARY  = 14;
const float V_CRIT_BOUNDARY = 13.2;

// ======== WiFi ==========
const char* WIFI_SSID = "IE_Room_BKUP";
const char* WIFI_PW   = "ieroom12345";

// ======== MQTT ==========
const char* MQTT_HOST = "f1bd5a3c43044a3a816321410ca20435.s1.eu.hivemq.cloud";
const int   MQTT_PORT = 8883;
const char* MQTT_USER = "P4P-Buoy";  
const char* MQTT_PASS = "P4P108buoy"; 

static const char CA_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)EOF";

const char* MQTT_TOPIC_CMD   = "buoy/esp/cmd";
const char* MQTT_TOPIC_TELEM = "buoy/esp/telem";

/*==============================
            GLOBALS
===============================*/
// WiFi and MQTT clients
WiFiClientSecure wifiClient;
PubSubClient client(wifiClient);
String clientId;

// Relay status'
bool relayPiStatus    = false;
bool relayModemStatus = false;
bool relayFCStatus    = false;

// State
enum State { IDLE, FULL, MID, LOW, CRIT };
State state = IDLE;
State prevState = IDLE;

/*==============================
      FUNCTION DECLARATIONS
===============================*/
// MQTT/WiFi
void setupWiFi();
void setupMQTT();
void mqttEnsureConnected();
void mqttCallback(char* topic, byte* payload, unsigned int len);
bool sendMsg(const char* topic, const char* msg);

// FSM
const char* getStateName(State s);
void enterState(State s);
void doFull();
void doMid();
void doLow();
void doIdle();

// ADC
float readBattVoltage();
float readADCCurrent(int pin);

/*==============================
          MQTT COMMANDS
===============================*/
void cmdUpdate() {
  // force update status
  // read adc and send telemetry
  float v_batt = readBattVoltage();
  float i_pi   = readADCCurrent(ADC_I_PI_PIN);
  float i_fc   = readADCCurrent(ADC_I_FC_PIN);
  float i_modem= readADCCurrent(ADC_I_MODEM_PIN);
  float i_esp  = readADCCurrent(ADC_I_ESP_PIN);
  const char* state_str = getStateName(state);
  bool relay_pi    = relayPiStatus;
  bool relay_modem = relayModemStatus;
  bool relay_fc    = relayFCStatus;

  // timestamp
  // gps?

  // package into json
  // send via mqtt MQTT_TOPIC_TELEM
}

void cmdPause() {
  // pause all operations
  // enter idle state
  prevState = state;
  enterState(IDLE);
}

void cmdResume() {
  // resume operations
  enterState(prevState);
}

struct Cmd {
  const char* name;
  void (*func)();
};

Cmd commands[] = {
  {"update", cmdUpdate},
  {"pause", cmdPause},
  {"resume", cmdResume}
};

/*==============================
      MQTT/WIFI FUNCTIONS
===============================*/
void setupWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PW);
  while (WiFi.status() != WL_CONNECTED) { delay(300); }
}

void setupMQTT() {
  wifiClient.setCACert(CA_CERT);
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(mqttCallback);
  clientId = "esp32-" + String((uint32_t)ESP.getEfuseMac(), HEX);
}

void mqttEnsureConnected() {
  while (!client.connected()) {
    if (client.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
      client.subscribe(MQTT_TOPIC_SUB);
    } else { delay(2000); }
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int len) {
  static char msg[512];
  len = min(len, (unsigned int)(sizeof(msg)-1));
  memcpy(msg, payload, len);
  msg[len] = '\0';
  if (strcmp(topic, MQTT_TOPIC_CMD) == 0) {
    for (auto &cmd : DISPATCH) {
      if (strcmp(msg, cmd.name) == 0) {
        cmd.fn();
        return;
      }
    }
  }
}

bool sendMsg(const char* topic, const char* msg) {
  return client.publish(topic, msg);
}


/*==============================
          ADC FUNCTIONS
===============================*/
float readBattVoltage(){
  int raw = analogRead(ADC_V_BATT_PIN);
  float v_adc  = (raw / ADC_MAX) * ADC_VREF; // convert to pin voltage
  float v = v_adc * ADC_V_CONV;   // Convert to real battery voltage
  return v;
}

float readADCCurrent(int pin){
  int raw = analogRead(pin);
  float v_adc  = (raw / ADC_MAX) * ADC_VREF; // convert to pin voltage
  float cur = v_adc * ADC_I_CONV;   // Convert to real current 
  return cur;
}

/*==============================
          RELAY FUNCTIONS
===============================*/

// need to ensure they are held in case of low power mode (ie deep sleep)

void relayModemOn(){
  digitalWrite(RELAY_MODEM_PIN, HIGH);
  relayModemStatus = true;
}

void relayModemOff(){
  digitalWrite(RELAY_MODEM_PIN, LOW);
  relayModemStatus = false;
}

void relayPiOn(){
  digitalWrite(RELAY_PI_PIN, HIGH);
  relayPiStatus = true;
}

void relayPiOff(){
  digitalWrite(RELAY_PI_PIN, LOW);
  digitalWrite(PI_SHUTDOWN_PIN, HIGH);
  delay(1000);    
  relayPiStatus = false;
}

void relayFCOn(){
  digitalWrite(RELAY_FC_PIN, HIGH);
  relayFCStatus = true;
  // wait for boot, then arm
  delay(5000);
  // armFC();
}

void relayFCOff(){
  // disarm first, then wait
  // disarmFC();
  delay(2000);
  digitalWrite(RELAY_FC_PIN, LOW);
  relayFCStatus = false;
}

/*==============================
          FSM FUNCTIONS
===============================*/
const char* getStateName(State s) {
  switch (s) {
    case IDLE: return "IDLE";
    case FULL: return "FULL";
    case MID:  return "MID";
    case LOW:  return "LOW";
    case CRIT: return "CRIT";
    default:   return "UNKNOWN";
  }
}

void enterState(State s) {
  state = s;
  switch (state){
    case FULL:
      // entering full
      // ensure all systems on
      break;

    case MID:
      // entering mid
      // ensure all on except for FC
      // must disarm and force fc shutdown first
      break;

    case LOW:
      // entering low
      // ensure all off 
      // need to let pi know to shutdown
      break;

    case CRIT:
      // entering crit
      // ensure all off
      // turn FC on
      // arm FC
      // force RTL
      break;
    case IDLE:
      // entering idle
      // everything on?
      break;
  }
}

void doFull(){
  // full behaviour here
  // pretty much just monitor and report
}

void doMid(){
  // mid behaviour here
  // pretty much just monitor and report
}

void doLow(){
  // low behaviour here
  // deep sleep for period of time
  // wake up, check voltage and report
  // go back to sleep
}

void doIdle(){
  // idle behaviour here
  // entered from user command (pause)
  // everything on?
}


/*==============================
            SETUP
===============================*/
void setup() {
  // init adc
  analogReadResolution(ADC_RES); // 12-bit
  analogSetAttenuation(ADC_11db); // Full-scale ~3.3–3.6 V

  // determine state from battery voltage
  float v_batt = readBattVoltage();
  if (v_batt >= V_MID_BOUNDARY) enterState(FULL);
  else if (v_batt >= V_LOW_BOUNDARY) enterState(MID);
  else if (v_batt >= V_CRIT_BOUNDARY) enterState(LOW);
  else enterState(CRIT);

  // init rest of system
  Serial.begin(115200);
  setupWiFi();
  setupMQTT();
}

/*==============================
            LOOP
===============================*/
void loop() {
  float v_batt = readBattVoltage();

  switch (state) {
    case FULL:
      doFull();
      if (v_batt < V_MID_BOUNDARY) enterState(MID);
      break;

    case MID:
      doMid();
      if (v_batt >= V_MID_BOUNDARY + V_HYSTERESIS) enterState(FULL);
      if (v_batt < V_LOW_BOUNDARY) enterState(LOW);
      break;

    case LOW:
      doLow();
      if (v_batt >= V_LOW_BOUNDARY + V_HYSTERESIS) enterState(MID);
      if (v_batt < V_CRIT_BOUNDARY) enterState(CRIT);
      break;

    case IDLE:
      doIdle();
      break;
  }
}
