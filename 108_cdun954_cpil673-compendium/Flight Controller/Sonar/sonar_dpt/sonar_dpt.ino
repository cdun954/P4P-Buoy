#include <SoftwareSerial.h>
#include <string.h>

#define COM 0x55

// Define variables
uint8_t buffer_RTT[4];
uint8_t CS;
int Distance = 0;
SoftwareSerial mySerial(8,7);

void setup() {
  Serial.begin(115200);
  mySerial.begin(115200);
}

void loop() {
  mySerial.write(COM);
  delay(200);
  if (mySerial.available() > 0) {
    delay(4);
    if (mySerial.read() == 0xFF) {
      buffer_RTT[0] = 0xFF;
      for (int i = 1; i < 4; i++) {
        buffer_RTT[i] = mySerial.read();
      }
      CS = buffer_RTT[0] + buffer_RTT[1] + buffer_RTT[2];
      if (buffer_RTT[3] == CS) {
        Distance = (buffer_RTT[1] << 8) + buffer_RTT[2];
      }
    }
  }

  char payload[48];
  int meters_whole = Distance / 1000;           // whole metres
  int meters_frac  = (Distance % 1000) / 10;    // two decimals
  int n = snprintf(payload, sizeof(payload), "SDDPT,%d.%02d,,", meters_whole, meters_frac);
  uint8_t cs = 0;
  for (int i = 0; i < n; ++i) cs ^= (uint8_t)payload[i];

  char sentence[64];
  int m = snprintf(sentence, sizeof(sentence), "$%s*%02X\r\n", payload, cs);

  // Send to FC UART
  Serial.print("NMEA out: ");
  Serial.write((const uint8_t*)sentence, m);
}