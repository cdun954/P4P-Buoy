/*==============================
          CONSTANTS
===============================*/ 

// ======== ADC ==========
#define ADC_I_PI_PIN 36
#define ADC_I_FC_PIN 39
#define ADC_I_MODEM_PIN 34
#define ADC_I_ESP_PIN 35
#define ADC_V_BATT_PIN 32

const float ADC_VREF      = 3.3;      // ESP32 ADC reference (Volts)
const float ADC_RES       = 12;       // 12-bit ADC
const float ADC_MAX       = 4095;     // 12-bit ADC
const float ADC_I_CONV    = 69;       // current sensor conversion factor
const float ADC_V_CONV    = 69;       // voltage battery conversion factor

// ======== Voltage Thresholds ==========
const float V_HYSTERESIS    = 0.3;
const float V_MID_BOUNDARY  = 14.8;
const float V_LOW_BOUNDARY  = 14;
const float V_CRIT_BOUNDARY = 13.2;

/*==============================
            GLOBALS
===============================*/
enum State {
  FULL,
  MID,
  LOW,
  CRIT
};
State state;

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
          FSM FUNCTIONS
===============================*/
void enterState(State s) {
  state = s;
  switch (state){
    case FULL:
      // entering full
      break;

    case MID:
      // entering mid
      break;

    case LOW:
      // entering low
      break;

    case CRIT:
      // entering crit
      break;
  }
}

void doFull(){
  // full behaviour here
}

void doMid(){
  // mid behaviour here
}

void doLow(){
  // low behaviour here
}

void doCrit(){
  // crit behaviour here
  // likely RTL
}


/*==============================
            SETUP
===============================*/
void setup() {
  // init adc
  analogReadResolution(ADC_RES); // 12-bit
  analogSetAttenuation(ADC_11db); // Full-scale ~3.3–3.6 V
  
  // init rest of system
  Serial.begin(115200);

  // determine state from battery voltage
  float v_batt = readBattVoltage();
  if (v_batt >= V_MID_BOUNDARY) enterState(FULL);
  else if (v_batt >= V_LOW_BOUNDARY) enterState(MID);
  else if (v_batt >= V_CRIT_BOUNDARY) enterState(LOW);
  else enterState(CRIT);
}

/*==============================
            LOOP
===============================*/
void loop() {
  float v_batt = readBattVoltage();

  switch (state) {
    case FULL:
      doFull();
      if (v_batt < MID_BOUNDARY) enterState(MID);
      break;

    case MID:
      doMid();
      if (v_batt >= MID_BOUNDARY + HYSTERESIS) enterState(FULL);
      if (v_batt < LOW_BOUNDARY) enterState(LOW);
      break;

    case LOW:
      doLow();
      if (v_batt >= LOW_BOUNDARY + HYSTERESIS) enterState(MID);
      if (v_batt < CRIT_BOUNDARY) enterState(CRIT);
      break;

    case CRIT:
      doCrit();
      break;
  }
}
