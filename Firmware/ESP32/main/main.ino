#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>
#include <HardwareSerial.h>
#include <MAVLink.h>
#include <ArduinoJson.h>

/*
main.ino

Power management controller
Features:
- Manages power states based on battery voltage
- Handles MQTT commands from GCS
- Controls relays for power distribution
- Monitors current and voltage via ADC
- FSM with states: FULL, MID, SLEEP, CRIT
*/

/*==============================
          CONSTANTS
===============================*/ 
// ======== MAVLink ==========
#define FC_RX_PIN 16    // ESP32 RX2 (GPIO16)  <- FC TX
#define FC_TX_PIN 17    // ESP32 TX2 (GPIO17)  -> FC
#define FC_BAUD   57600

static uint8_t g_sysid  = 245;
static uint8_t g_compid = MAV_COMP_ID_ONBOARD_COMPUTER;
static uint8_t tgt_sys  = 1;
static uint8_t tgt_comp = MAV_COMP_ID_AUTOPILOT1;

// ======== PI GPIO ==========
#define PI_SHUTDOWN_PIN  4

// ======== Relays ==========
#define RELAY_PI_PIN     23
#define RELAY_MODEM_PIN  22
#define RELAY_FC_PIN     21

// ======= Times ==========
const int TIME_FULL = 10000;   // 10 sec
const int TIME_MID  = 60000;   // 60 sec
const int TIME_SLEEP  = 600000;   // 10 min
const int TIME_CRIT = 30000;    // 30 sec
const int TIME_FC_BOOT = 5000; // 5 sec
const int TIME_MODEM_BOOT = 6000; // 6 sec
const int TIME_LOAD = 2000;    // 2 sec
const int TIME_GPS  = 300000;  // 5 min
const int TIME_IDLE = 60000;   // 60 sec
const int TIME_PI_SHUTDOWN = 5000; // 5 sec


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
const float V_SLEEP_BOUNDARY  = 14;
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

// MAVLink
HardwareSerial FC(2);
static mavlink_message_t rx_msg;
static mavlink_status_t  rx_status;

// Relay status'
bool relayPiStatus    = false;
bool relayModemStatus = false;
bool relayFCStatus    = false;

// State
enum State { IDLE, FULL, MID, SLEEP, CRIT };
State state = FULL;
State prevState = FULL;

// Timing
unsigned long tFull, tMid, tSleep, tIdle, tCrit, tGPS = 0;

/*==============================
      FORWARD DECLARATIONS
===============================*/
// MQTT/WiFi
void setupWiFi();
void wifiEnsureConnected();
void setupMQTT();
void mqttEnsureConnected();
void mqttCallback(char* topic, byte* payload, unsigned int len);
bool sendMsg(const char* topic, const char* msg);

// MQTT commands
void cmdUpdate();
void cmdPause();
void cmdResume();
void cmdForceRTL();


// FSM
void enterState(State s);
void doFull();
void doMid();
void doSleep();
void doCrit();
void doIdle();
const char* getStateName(State s);

// ADC
float readBattVoltage();
float readADCCurrent(int pin);

// Relays / Pins
void setupPins();
void relayModemOn();
void relayModemOff();
void relayPiOn();
void relayPiOff();
void relayFCOn();
void relayFCOff();

// FC / MAVLink
void mavArmFC();
void mavDisarmFC();
void mavForceRTL();
float* getFCGPS();
static void mav_send(const mavlink_message_t &m);
static void mav_cmd_long(uint16_t command,
                         float p1=0,float p2=0,float p3=0,float p4=0,
                         float p5=0,float p6=0,float p7=0);

/*==============================
          MQTT COMMANDS
===============================*/
void cmdUpdate() {
  // force update status
  // read adc and send telemetry
  float v_batt          = readBattVoltage();
  float i_pi            = readADCCurrent(ADC_I_PI_PIN);
  float i_fc            = readADCCurrent(ADC_I_FC_PIN);
  float i_modem         = readADCCurrent(ADC_I_MODEM_PIN);
  float i_esp           = readADCCurrent(ADC_I_ESP_PIN);
  const char* stateName = getStateName(state);
  bool relay_pi         = relayPiStatus;
  bool relay_modem      = relayModemStatus;
  bool relay_fc         = relayFCStatus;

  StaticJsonDocument<256> doc;
  doc["v_batt"]     = v_batt;
  doc["i_pi"]       = i_pi;
  doc["i_fc"]       = i_fc;
  doc["i_modem"]    = i_modem;
  doc["i_esp"]      = i_esp;
  doc["state"]      = stateName;
  doc["relay_pi"]   = relay_pi;
  doc["relay_modem"]= relay_modem;
  doc["relay_fc"]   = relay_fc; 

  char buffer[256];
  size_t n = serializeJson(doc, buffer, sizeof(buffer));
  if (n == 0 || n >= sizeof(buffer)) {
    Serial.println("[MQTT] Failed to serialize telemetry");
    return;
  } else{
    Serial.println("[MQTT] Telemetry Sent!");
    client.publish(MQTT_TOPIC_TELEM, buffer);
  }
}

void cmdPause() {
  // pause all operations
  // enter idle state
  if (state != IDLE) prevState = state;
  enterState(IDLE);
}

void cmdResume() {
  // resume operations
  enterState(prevState);
}

void cmdForceRTL() {
  // CRIT is designed to force RTL
  // enter CRIT state
  enterState(CRIT);
}

struct Cmd {
  const char* name;
  void (*func)();
};

Cmd commands[] = {
  {"update", cmdUpdate},
  {"pause", cmdPause},
  {"resume", cmdResume},
  {"rtl", cmdForceRTL}
};  

/*==============================
      MQTT/WIFI FUNCTIONS
===============================*/
void setupWiFi() {
  WiFi.mode(WIFI_STA);
  Serial.println("[SETUP] Wifi Configured!");
}

void wifiEnsureConnected(){
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PW);
  Serial.println("[WiFi] Connecting...");
  while (WiFi.status() != WL_CONNECTED) { delay(300); }
  Serial.println("[WiFi] Connected!");
}

void setupMQTT() {
  wifiClient.setCACert(CA_CERT);
  client.setServer(MQTT_HOST, MQTT_PORT);
  client.setCallback(mqttCallback);
  clientId = "esp32-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.println("[SETUP] MQTT Configured!");
}

void mqttEnsureConnected() {
  if (client.connected()) return;
  Serial.println("[MQTT] Connecting...");
  while (!client.connected()) {
    if (client.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
      client.subscribe(MQTT_TOPIC_CMD);
    } else { delay(300); }
  }
  Serial.println("[MQTT] Connected");
}

void mqttCallback(char* topic, byte* payload, unsigned int len) {
  static char msg[512];
  len = min(len, (unsigned int)(sizeof(msg)-1));
  memcpy(msg, payload, len);
  msg[len] = '\0';
  Serial.printf("[MQTT] Msg received on topic: %s\n", topic);
  if (strcmp(topic, MQTT_TOPIC_CMD) == 0) {
    for (auto &cmd : commands) {
      if (strcmp(msg, cmd.name) == 0) {
        cmd.func();
        return;
      }
    }
  }
}


/*==============================
          ADC FUNCTIONS
===============================*/
float readBattVoltage(){
  int raw = analogRead(ADC_V_BATT_PIN);
  float v_adc  = (raw / ADC_MAX) * ADC_VREF; // convert to pin voltage
  float v = v_adc * ADC_V_CONV;   // Convert to real battery voltage
  Serial.println("[ADC] Battery Read!");
  return v;
}

float readADCCurrent(int pin){
  int raw = analogRead(pin);
  float v_adc  = (raw / ADC_MAX) * ADC_VREF; // convert to pin voltage
  float cur = v_adc * ADC_I_CONV;   // Convert to real current 
  Serial.println("[ADC] Current Read!");
  return cur;
}

/*==============================
          RELAY FUNCTIONS
===============================*/

// need to ensure they are held in case of sleep power mode (ie deep sleep)
void setupPins(){
  pinMode(RELAY_PI_PIN, OUTPUT);
  pinMode(RELAY_MODEM_PIN, OUTPUT);
  pinMode(RELAY_FC_PIN, OUTPUT);
  pinMode(PI_SHUTDOWN_PIN, OUTPUT);

  // set all to low
  digitalWrite(RELAY_PI_PIN, LOW);
  digitalWrite(RELAY_MODEM_PIN, LOW);
  digitalWrite(RELAY_FC_PIN, LOW);
  digitalWrite(PI_SHUTDOWN_PIN, LOW);
  relayFCStatus    = false;
  relayPiStatus    = false;
  relayModemStatus = false;
  
  Serial.println("[SETUP] Pins Setup!");
}


void relayModemOn(){
  if (!relayModemStatus){
    digitalWrite(RELAY_MODEM_PIN, HIGH);
    relayModemStatus = true;
    Serial.println("[RELAY] Modem Switched On");
    delay(TIME_MODEM_BOOT);
    wifiEnsureConnected();
    mqttEnsureConnected();
  }
  
}

void relayModemOff(){
  if (relayModemStatus){
    digitalWrite(RELAY_MODEM_PIN, LOW);
    relayModemStatus = false;
    Serial.println("[RELAY] Modem Switched Off");
  }
}

void relayPiOn(){
  if (!relayPiStatus){
    digitalWrite(RELAY_PI_PIN, HIGH);
    relayPiStatus = true;
    Serial.println("[RELAY] Pi Switched On");
  }
}

void relayPiOff(){
  if (relayPiStatus){
    digitalWrite(PI_SHUTDOWN_PIN, HIGH);
    delay(TIME_PI_SHUTDOWN);
    digitalWrite(RELAY_PI_PIN, LOW);
    relayPiStatus = false;
    Serial.println("[RELAY] Pi Switched Off");
  }
  
}

void relayFCOn(){
  if (!relayFCStatus){
    digitalWrite(RELAY_FC_PIN, HIGH);
    relayFCStatus = true;
    // wait for boot
    delay(TIME_FC_BOOT);
    Serial.println("[RELAY] FC Switched On");
  }
}

void relayFCOff(){
  // disarm first, then wait
  if (relayFCStatus){
    mavDisarmFC();
    digitalWrite(RELAY_FC_PIN, LOW);
    relayFCStatus = false;
    Serial.println("[RELAY] FC Switched Off");
  }
}

/*==============================
      FC/MAVLink FUNCTIONS
===============================*/
void mavArmFC() {
  mav_cmd_long(MAV_CMD_COMPONENT_ARM_DISARM, 1.0f);
  delay(TIME_LOAD);
  Serial.println(F("[MAV] ARM sent"));
}

void mavDisarmFC() {
  mav_cmd_long(MAV_CMD_COMPONENT_ARM_DISARM, 0.0f);
  delay(TIME_LOAD);
  Serial.println(F("[MAV] DISARM sent"));
}

void mavForceRTL() {
  mavlink_message_t m;
  const uint8_t  base_mode   = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED;
  const uint32_t custom_mode = 8; // Rover Smart RTL
  mavlink_msg_set_mode_pack(g_sysid, g_compid, &m, tgt_sys, base_mode, custom_mode);
  mav_send(m);
  Serial.println(F("[MAV] RTL sent"));
}

float* getFCGPS() {
  static float res[4] = {NAN, NAN, NAN, NAN};  // {lat, lon, alt, hdg}

  while (FC.available()) {
    const uint8_t c = FC.read();
    if (mavlink_parse_char(MAVLINK_COMM_0, c, &rx_msg, &rx_status)) {
      switch (rx_msg.msgid) {

        case MAVLINK_MSG_ID_GLOBAL_POSITION_INT: {
          mavlink_global_position_int_t g;
          mavlink_msg_global_position_int_decode(&rx_msg, &g);
          res[0] = g.lat / 1e7;
          res[1] = g.lon / 1e7;
          res[2] = g.alt / 1000.0f;                            // m AMSL
          res[3] = (g.hdg == UINT16_MAX) ? NAN : (g.hdg / 100.0f);
          return res;
        }

        case MAVLINK_MSG_ID_GPS_RAW_INT: {
          mavlink_gps_raw_int_t r;
          mavlink_msg_gps_raw_int_decode(&rx_msg, &r);
          if (r.fix_type >= 2) {
            res[0] = r.lat / 1e7;
            res[1] = r.lon / 1e7;
            res[2] = r.alt / 1000.0f;
            res[3] = NAN; // heading not provided
            return res;
          }
        } break;

        default:
          break;
      }
    }
  }
  return res; // unchanged {NAN,NAN,NAN,NAN} if nothing seen
}

static void mav_send(const mavlink_message_t &m) {
  uint8_t buf[MAVLINK_MAX_PACKET_LEN];
  const uint16_t n = mavlink_msg_to_send_buffer(buf, &m);
  FC.write(buf, n);
}

static void mav_cmd_long(uint16_t command,
                         float p1,float p2,float p3,float p4,
                         float p5,float p6,float p7) {
  mavlink_message_t m;
  mavlink_msg_command_long_pack(
    g_sysid, g_compid, &m,
    tgt_sys, tgt_comp, command, 0,
    p1,p2,p3,p4,p5,p6,p7);
  mav_send(m);
}


/*==============================
          FSM FUNCTIONS
===============================*/
const char* getStateName(State s) {
  switch (s) {
    case IDLE:  return "IDLE";
    case FULL:  return "FULL";
    case MID:   return "MID";
    case SLEEP: return "SLEEP";
    case CRIT:  return "CRIT";
    default:    return "UNKNOWN";
  }
}

void enterState(State s) {
  state = s;
  Serial.printf("[FSM] Entering State: %s\n", getStateName(s));
  switch (state){
    case FULL:
      // entering full
      // ensure all systems on
      relayPiOn();
      relayFCOn();
      relayModemOn();
      break;

    case MID:
      // entering mid
      // ensure all on except for FC
      // must disarm and force fc shutdown first
      relayPiOn();
      relayModemOn();
      relayFCOff();
      break;

    case SLEEP:
      // entering sleep
      // ensure all off 
      // need to let pi know to shutdown
      relayFCOff();
      relayModemOff();
      relayPiOff();
      break;

    case CRIT:
      // entering crit
      // ensure all off
      // turn FC on
      // arm FC
      // force RTL
      relayModemOff();
      relayPiOff();
      relayFCOn();
      mavArmFC();
      mavForceRTL();
      break;
    case IDLE:
      // entering idle
      relayModemOn();
      relayPiOff();
      relayFCOff();
      break;
  }
}

void doFull(){
  // pretty much just monitor and report
  cmdUpdate();
}

void doMid(){
  // pretty much just monitor and report
  // update gps every so often
  cmdUpdate();
  // if (millis() - tGPS >= TIME_GPS) {
  //   relayFCOn(); // ensure FC is on
  //   //sendGPS();
  //   relayFCOff(); // turn FC off again
  //   tGPS = millis();
  // }
}

void doSleep(){
  // everything is off
  // deep sleep for period of time
  // wake up, check voltage and report
  // keep modem on for 10 or so minutes to allow for commands
  // go back to sleep
}

void doCrit(){
  // rtl!
}

void doIdle(){
  // idle behaviour here
  // entered from user command (pause)
  // everything on?
  cmdUpdate();
}


/*==============================
            SETUP
===============================*/
void setup() {
  // init adc
  analogReadResolution(ADC_RES); // 12-bit
  analogSetAttenuation(ADC_11db); // Full-scale ~3.3–3.6 V

  // determine state from battery voltage
  State s = IDLE; // default
  float v_batt = readBattVoltage();
  if (v_batt >= V_MID_BOUNDARY) s = FULL;
  else if (v_batt >= V_SLEEP_BOUNDARY) s = MID;
  else if (v_batt >= V_CRIT_BOUNDARY) s = SLEEP;
  else s = CRIT;

  // init rest of system
  Serial.begin(115200);
  FC.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);
  setupPins();
  
  setupWiFi();
  setupMQTT();

  enterState(s);
}

/*==============================
            LOOP
===============================*/
void loop() {
  float v_batt = readBattVoltage();

  switch (state) {
    case FULL:
      wifiEnsureConnected();
      mqttEnsureConnected();
      client.loop();
      if (millis() - tFull >= TIME_FULL){
        doFull(); tFull = millis();
      }
      if (v_batt < V_MID_BOUNDARY) enterState(MID);
      break;

    case MID:
      wifiEnsureConnected();
      mqttEnsureConnected();
      client.loop();
      if (millis() - tMid >= TIME_MID){
        doMid(); tMid = millis();
      }
      if (v_batt >= V_MID_BOUNDARY + V_HYSTERESIS) enterState(FULL);
      if (v_batt < V_SLEEP_BOUNDARY) enterState(SLEEP);
      break;

    case SLEEP:
      if (millis() - tSleep >= TIME_SLEEP){
        doSleep(); tSleep = millis();
      }
      if (v_batt >= V_SLEEP_BOUNDARY + V_HYSTERESIS) enterState(MID);
      if (v_batt < V_CRIT_BOUNDARY) enterState(CRIT);
      break;
    
    case CRIT:
      if (millis() - tCrit >= TIME_SLEEP){
        doCrit(); tCrit = millis();
      }
      break;

    case IDLE:
      wifiEnsureConnected();
      mqttEnsureConnected();
      client.loop();
      if (millis() - tIdle >= TIME_IDLE){
        doIdle(); tIdle = millis();
      }
      break;
  }
  delay(1000);
}
