/*
 * ESP32 Minimal MAVLink “GPS + Arm/Disarm/RTL”
 * - UART2 @ 9600 to FC (TELEM3)
 * - Parses HEARTBEAT (to learn tgt sys/comp) + GLOBAL_POSITION_INT (GPS)
 * - Serial console commands: arm | disarm | rtl
 */

#include <HardwareSerial.h>

// ===== MAVLink (minimal) =====
#include <MAVLink.h>

// ===== UART to FC (TELEM3) =====
#define FC_RX_PIN 16    // ESP32 RX2 (GPIO16)  <- FC TX
#define FC_TX_PIN 17    // ESP32 TX2 (GPIO17)  -> FC RX
#define FC_BAUD   57600
HardwareSerial FC(2);

// Our component identity (pick a sysid not used by FC/GCS)
static uint8_t g_sysid  = 245;
static uint8_t g_compid = MAV_COMP_ID_ONBOARD_COMPUTER;

// Target (learned from first heartbeat)
static uint8_t tgt_sys  = 1;
static uint8_t tgt_comp = MAV_COMP_ID_AUTOPILOT1;

// RX parser state
static mavlink_message_t rx_msg;
static mavlink_status_t  rx_status;

// --- Helpers to send MAVLink ------------------------------------------------
static void mav_send(const mavlink_message_t &m) {
  uint8_t buf[MAVLINK_MAX_PACKET_LEN];
  const uint16_t n = mavlink_msg_to_send_buffer(buf, &m);
  FC.write(buf, n);
}

static void mav_cmd_long(uint16_t command,
                         float p1=0,float p2=0,float p3=0,float p4=0,
                         float p5=0,float p6=0,float p7=0) {
  mavlink_message_t m;
  mavlink_msg_command_long_pack(
    g_sysid, g_compid, &m,
    tgt_sys, tgt_comp, command, 0,
    p1,p2,p3,p4,p5,p6,p7);
  mav_send(m);
}

static void mav_send_heartbeat_once() {
  mavlink_message_t m;
  mavlink_msg_heartbeat_pack(
    g_sysid, g_compid, &m,
    MAV_TYPE_ONBOARD_CONTROLLER,
    MAV_AUTOPILOT_INVALID,
    0, 0, MAV_STATE_ACTIVE);
  mav_send(m);
}

// --- Public commands --------------------------------------------------------
static void mav_arm(bool arm) {
  mav_cmd_long(MAV_CMD_COMPONENT_ARM_DISARM, arm ? 1.0f : 0.0f);
  Serial.println(arm ? F("[MAV] ARM sent") : F("[MAV] DISARM sent"));
}

static void mav_rtl() {
  // Copter RTL via SET_MODE (base_mode=custom, custom_mode=6)
  mavlink_message_t m;
  const uint8_t  base_mode   = MAV_MODE_FLAG_CUSTOM_MODE_ENABLED;
  const uint32_t custom_mode = 6; // Copter RTL
  mavlink_msg_set_mode_pack(g_sysid, g_compid, &m, tgt_sys, base_mode, custom_mode);
  mav_send(m);
  Serial.println(F("[MAV] RTL sent"));
}

// --- Parser: read HEARTBEAT + GPS only -------------------------------------
static void mav_poll_parse() {
  while (FC.available()) {
    const uint8_t c = FC.read();
    if (mavlink_parse_char(MAVLINK_COMM_0, c, &rx_msg, &rx_status)) {
      switch (rx_msg.msgid) {

        case MAVLINK_MSG_ID_HEARTBEAT: {
          // Learn target IDs from FC’s heartbeat
          tgt_sys  = rx_msg.sysid;
          tgt_comp = rx_msg.compid;
          // Optional: print once
          static bool printed = false;
          if (!printed) {
            printed = true;
            Serial.printf("[MAV] Heartbeat from sys=%u comp=%u\n", tgt_sys, tgt_comp);
          }
        } break;

        case MAVLINK_MSG_ID_GLOBAL_POSITION_INT: {
          mavlink_global_position_int_t g;
          mavlink_msg_global_position_int_decode(&rx_msg, &g);
          const double lat = g.lat / 1e7;
          const double lon = g.lon / 1e7;
          const float  alt = g.alt / 1000.0f;  // m AMSL
          const float  hdg = (g.hdg == UINT16_MAX) ? NAN : (g.hdg / 100.0f); // deg

          Serial.printf("[GPS] lat=%.7f lon=%.7f alt=%.2f m hdg=%s%.1f deg\n",
                        lat, lon, alt, isnan(hdg) ? "NaN" : "", hdg);
        } break;

        // If your FC doesn’t emit GLOBAL_POSITION_INT, you can instead use:
        // case MAVLINK_MSG_ID_GPS_RAW_INT: {
        //   mavlink_gps_raw_int_t r;
        //   mavlink_msg_gps_raw_int_decode(&rx_msg, &r);
        //   if (r.fix_type >= 2) {
        //     Serial.printf("[GPS_RAW] lat=%.7f lon=%.7f alt=%.2f m\n",
        //                   r.lat/1e7, r.lon/1e7, r.alt/1000.0f);
        //   }
        // } break;

        default:
          // ignore everything else
          break;
      }
    }
  }
}

// --- Simple serial command line --------------------------------------------
static void handle_console() {
  static char line[64];
  static uint8_t idx = 0;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {            // end of line
      line[idx] = '\0';
      idx = 0;

      if      (strcasecmp(line, "arm")    == 0) mav_arm(true);
      else if (strcasecmp(line, "disarm") == 0) mav_arm(false);
      else if (strcasecmp(line, "rtl")    == 0) mav_rtl();
      else if (strcasecmp(line, "hb")     == 0) mav_send_heartbeat_once();
      else if (line[0] != '\0') Serial.println(F("[CMD] unknown (arm|disarm|rtl|hb)"));
    } else if (idx < sizeof(line)-1) {
      line[idx++] = c;
    }
  }
}

// --- Arduino entry points ---------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println(F("\nESP32 MAVLink mini @9600 (FC on UART2 16/17)"));
  Serial.println(F("Type: arm | disarm | rtl | hb"));

  FC.begin(FC_BAUD, SERIAL_8N1, FC_RX_PIN, FC_TX_PIN);
  delay(50);

  // Optional: announce once so FC logs see us
  mav_send_heartbeat_once();
}

void loop() {
  mav_poll_parse();   // read MAVLink from FC
  handle_console();   // check for serial commands
  // small idle
  delay(2);
}
