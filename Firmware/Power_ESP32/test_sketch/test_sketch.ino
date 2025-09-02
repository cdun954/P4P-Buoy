#define ADC_X_PIN 5

// voltage thresholds
#define HYSTERESIS 0.3
#define MID_BOUNDARY 14.8
#define LOW_BOUNDARY 14
#define CRIT_BOUNDARY 13.2

float batteryVoltage;

enum State {
  INIT,
  FULL,
  MID,
  LOW,
  CRIT
};

State state = INIT;

void enterState(State s) {
  state = s;
  Serial.print("Entering state: ");
  Serial.println(s);
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

void setup() {
  Serial.begin(115200);
  enterState(INIT);
}

void loop() {
  switch (state) {
    case INIT:
      // Do setup work
      enterState(FULL);
      break;

    case FULL:
      doFull();
      if (batteryVoltage < MID_BOUNDARY) enterState(MID);
      break;

    case MID:
      doMid();
      if (batteryVoltage >= MID_BOUNDARY + HYSTERESIS) enterState(FULL);
      if (batteryVoltage < LOW_BOUNDARY) enterState(LOW);
      break;

    case LOW:
      doLow();
      if (batteryVoltage >= LOW_BOUNDARY + HYSTERESIS) enterState(MID);
      if (batteryVoltage < CRIT_BOUNDARY) enterState(CRIT);
      break;

    case CRIT:
      doCrit();
      break;
  }
}
