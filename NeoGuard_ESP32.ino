#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Preferences.h>
#include <math.h>

// =====================================================
// NEOGUARD 303 - WI-FI LIVE ESP32 NODE + THRESHOLD FAN
// =====================================================
// DHT22   DATA -> GPIO 4   (ambient temp + humidity)
// NTC     DO   -> GPIO 34  (digital fever signal, LOW = fever)
// MPU6050 SDA/SCL -> GPIO 21 / 22
// RED LED -> GPIO 25
// BUZZER  -> GPIO 27
// FAN     -> GPIO 26  (via relay / MOSFET driver, NOT directly)
//
// FAN LOGIC (runs locally on the ESP32, works without Wi-Fi):
//   ON  when DHT22 temperature >= fan_on_temp
//   OFF when DHT22 temperature <= fan_on_temp - FAN_HYSTERESIS
// fan_on_temp is set on the dashboard (Settings -> "Fan turns ON at")
// and is returned to the ESP32 in every server reply. The last value
// received is saved in flash, so the fan keeps using the customer's
// threshold after a reboot or Wi-Fi loss.
// =====================================================

// ---------------- WIFI ----------------
const char* WIFI_SSID = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ---------------- SERVER ----------------
// Use the laptop's CURRENT LAN IP (it changes between networks).
const char* SERVER_URL = "http://192.168.1.5:5001/api/sensor-data";

// ---------------- PINS ----------------
#define DHT_PIN 4
#define DHT_TYPE DHT22
#define NTC_PIN 34
#define LED_PIN 25
#define BUZZER_PIN 27
#define FAN_PIN 26
#define MPU_SDA 21
#define MPU_SCL 22

// Set to false if your relay/driver module is active-LOW.
const bool FAN_ACTIVE_HIGH = true;

// ---------------- FAN SETTINGS ----------------
const float DEFAULT_FAN_ON_TEMP = 28.0;  // used until the dashboard value arrives
const float FAN_HYSTERESIS = 1.0;        // fan turns off at (threshold - 1.0 C)

float fanOnTemp = DEFAULT_FAN_ON_TEMP;
bool fanOn = false;
Preferences prefs;

// ---------------- MPU SETTINGS ----------------
// Continuous 100 Hz sampling. Vibration is measured as acceleration that
// changes faster than the gravity baseline, rather than max/min total
// acceleration across a short batch (which often misses brief vibrations).
const float MOTION_THRESHOLD = 1.2;       // m/s^2 from gravity magnitude
const float VIBRATION_THRESHOLD = 0.35;   // m/s^2 dynamic acceleration peak
const float GRAVITY_BASELINE_ALPHA = 0.02; // slow baseline follows orientation
const unsigned long MPU_SAMPLE_INTERVAL = 10; // 100 Hz
const unsigned long MOTION_HOLD_MS = 1000;
const unsigned long VIBRATION_HOLD_MS = 3500; // spans at least one 2.5 s upload

// ---------------- TIMING ----------------
const unsigned long SEND_INTERVAL = 2500;
const unsigned long WIFI_RETRY_INTERVAL = 15000;
unsigned long lastSendTime = 0;

// ---------------- FEVER LATCH ----------------
// The NTC module's DO pin can flicker or pulse briefly. Without a hold, the
// LED/buzzer blinked off instantly and the dashboard (which only hears from
// the ESP32 every SEND_INTERVAL) never saw the short pulse.
// Now: any LOW reading keeps the alert ON for at least FEVER_HOLD_MS after
// the signal was last seen, and the SAME latched state is sent to the dashboard.
const unsigned long FEVER_HOLD_MS = 10000;
unsigned long feverLastSeen = 0;
bool feverLatched = false;
bool lastReportedFever = false;
float lastGoodTemp = NAN, lastGoodHum = NAN;
unsigned long lastWifiAttempt = 0;

// ---------------- OBJECTS ----------------
DHT dht(DHT_PIN, DHT_TYPE);
Adafruit_MPU6050 mpu;
bool mpuAvailable = false;
float gravityX = 0.0f, gravityY = 0.0f, gravityZ = 0.0f;
bool gravityBaselineReady = false;
unsigned long lastMPUSample = 0;
unsigned long motionDetectedUntil = 0;
unsigned long vibrationDetectedUntil = 0;
int latestMotionState = 0;
int latestVibrationState = 0;

// =====================================================
// WIFI (non-blocking retries so safety logic never stalls)
// =====================================================
void startWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  lastWifiAttempt = millis();
}

bool connectWiFiBlocking() {
  Serial.println("\nNEOGUARD WIFI: connecting");
  startWiFi();
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi connected! ESP32 IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Signal RSSI: ");
    Serial.println(WiFi.RSSI());
    return true;
  }
  Serial.println("Wi-Fi connection failed (will keep retrying; local safety still active).");
  return false;
}

bool ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  if (millis() - lastWifiAttempt >= WIFI_RETRY_INTERVAL) {
    Serial.println("Wi-Fi lost - retrying...");
    WiFi.disconnect();
    startWiFi();
  }
  return false;
}

// =====================================================
// MPU6050
// =====================================================
void initializeMPU() {
  Wire.begin(MPU_SDA, MPU_SCL);
  if (mpu.begin()) {
    mpuAvailable = true;
    Serial.println("MPU6050 detected.");
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    // Wider bandwidth preserves more of the vibration signal.
    mpu.setFilterBandwidth(MPU6050_BAND_44_HZ);
    gravityBaselineReady = false;
    lastMPUSample = 0;
  } else {
    mpuAvailable = false;
    Serial.println("MPU6050 NOT detected.");
  }
}

void updateMPUContinuous() {
  if (!mpuAvailable) {
    latestMotionState = 0;
    latestVibrationState = 0;
    return;
  }

  const unsigned long now = millis();
  if (now - lastMPUSample < MPU_SAMPLE_INTERVAL) {
    latestMotionState = (now < motionDetectedUntil) ? 1 : 0;
    latestVibrationState = (now < vibrationDetectedUntil) ? 1 : 0;
    return;
  }
  lastMPUSample = now;

  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  const float ax = a.acceleration.x;
  const float ay = a.acceleration.y;
  const float az = a.acceleration.z;

  // Establish the gravity vector before looking for dynamic acceleration.
  if (!gravityBaselineReady) {
    gravityX = ax;
    gravityY = ay;
    gravityZ = az;
    gravityBaselineReady = true;
    return;
  }

  // Difference from the slowly-following gravity/orientation baseline is the
  // high-frequency component. This is much more useful for vibration than
  // comparing only the total acceleration magnitude's min/max values.
  const float dx = ax - gravityX;
  const float dy = ay - gravityY;
  const float dz = az - gravityZ;
  const float dynamicAcceleration = sqrt(dx * dx + dy * dy + dz * dz);
  const float totalMagnitude = sqrt(ax * ax + ay * ay + az * az);

  if (fabs(totalMagnitude - 9.81f) > MOTION_THRESHOLD) {
    motionDetectedUntil = now + MOTION_HOLD_MS;
  }
  if (dynamicAcceleration >= VIBRATION_THRESHOLD) {
    vibrationDetectedUntil = now + VIBRATION_HOLD_MS;
  }

  // Update baseline after measuring the current dynamic component.
  gravityX += GRAVITY_BASELINE_ALPHA * dx;
  gravityY += GRAVITY_BASELINE_ALPHA * dy;
  gravityZ += GRAVITY_BASELINE_ALPHA * dz;

  latestMotionState = (now < motionDetectedUntil) ? 1 : 0;
  latestVibrationState = (now < vibrationDetectedUntil) ? 1 : 0;
}


// =====================================================
// LOCAL SAFETY: fever -> LED + buzzer
// =====================================================
void updateActuators(bool fever) {
  digitalWrite(LED_PIN, fever ? HIGH : LOW);
  digitalWrite(BUZZER_PIN, fever ? HIGH : LOW);
}

// =====================================================
// FAN CONTROL (threshold + hysteresis, DHT22 driven)
// =====================================================
void setFan(bool on) {
  fanOn = on;
  digitalWrite(FAN_PIN, (on == FAN_ACTIVE_HIGH) ? HIGH : LOW);
}

void updateFan(float ambientTemperature) {
  bool previous = fanOn;
  if (!fanOn && ambientTemperature >= fanOnTemp) {
    setFan(true);
  } else if (fanOn && ambientTemperature <= (fanOnTemp - FAN_HYSTERESIS)) {
    setFan(false);
  }
  if (fanOn != previous) {
    Serial.print("FAN -> ");
    Serial.print(fanOn ? "ON" : "OFF");
    Serial.print("  (temp ");
    Serial.print(ambientTemperature, 1);
    Serial.print(" C, threshold ");
    Serial.print(fanOnTemp, 1);
    Serial.println(" C)");
  }
}

// Read "fan_on_temp":<number> from the server's JSON reply.
void applyServerConfig(const String &response) {
  int key = response.indexOf("\"fan_on_temp\"");
  if (key < 0) return;
  int colon = response.indexOf(':', key);
  if (colon < 0) return;
  float value = response.substring(colon + 1).toFloat();
  // Sanity range so a bad reply can't disable the fan permanently.
  if (value < 5.0 || value > 60.0) return;
  if (fabs(value - fanOnTemp) > 0.01) {
    fanOnTemp = value;
    prefs.putFloat("fanOn", fanOnTemp);
    Serial.print("Fan threshold updated from dashboard: ");
    Serial.print(fanOnTemp, 1);
    Serial.println(" C");
  }
}

// =====================================================
// SEND DATA
// =====================================================
bool sendSensorData(float ambientTemperature, float humidity,
                    int motion, int vibration, bool fever) {
  if (WiFi.status() != WL_CONNECTED) return false;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  // NTC is a digital fever flag only; NTC field kept as 0 for compatibility.
  String json = "{";
  json += "\"NTC\":0";
  json += ",\"DHT_TEMP\":" + String(ambientTemperature, 2);
  json += ",\"DHT11\":" + String(humidity, 2);
  json += ",\"ITG_MPU\":" + String(motion);
  json += ",\"MPU_VIBRATION\":" + String(vibration);
  json += ",\"FEVER\":" + String(fever ? 1 : 0);
  json += ",\"FAN\":" + String(fanOn ? 1 : 0);
  json += "}";

  Serial.println("\nSending to NeoGuard:");
  Serial.println(json);

  int code = http.POST(json);
  Serial.print("HTTP POST: ");
  Serial.println(code);

  if (code > 0) {
    String response = http.getString();
    Serial.print("NeoGuard Server: ");
    Serial.println(response);
    if (code >= 200 && code < 300) applyServerConfig(response);
  } else {
    Serial.print("HTTP Error: ");
    Serial.println(http.errorToString(code));
  }
  http.end();
  return (code >= 200 && code < 300);
}

// =====================================================
// SETUP
// =====================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n========================================");
  Serial.println("        NEOGUARD 303");
  Serial.println("  ESP32 SENSOR + SAFETY + FAN NODE");
  Serial.println("========================================");

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  setFan(false);
  pinMode(NTC_PIN, INPUT);

  // Restore the customer's last fan threshold (survives reboot / no Wi-Fi).
  prefs.begin("neoguard", false);
  fanOnTemp = prefs.getFloat("fanOn", DEFAULT_FAN_ON_TEMP);
  Serial.print("Fan threshold: ");
  Serial.print(fanOnTemp, 1);
  Serial.println(" C");

  dht.begin();
  Serial.println("DHT22 initialized.");

  initializeMPU();
  connectWiFiBlocking();

  Serial.println("\nNeoGuard initialization complete.\n");
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  unsigned long now = millis();

  // NTC: HIGH = no fever, LOW = fever. Local safety runs every loop.
  if (digitalRead(NTC_PIN) == LOW) {
    feverLastSeen = now;
    feverLatched = true;
  } else if (feverLatched && (now - feverLastSeen >= FEVER_HOLD_MS)) {
    feverLatched = false;
  }
  bool fever = feverLatched;
  updateActuators(fever);

  ensureWiFi();

  // Keep sampling the MPU6050 continuously, including between cloud uploads.
  // This prevents short vibration events from being missed by the 2.5 s
  // sensor-upload interval.
  updateMPUContinuous();

  // Send on schedule, and IMMEDIATELY when the fever state changes so the
  // dashboard LED / buzzer / emergency cards switch together with the hardware.
  if ((now - lastSendTime >= SEND_INTERVAL) || (fever != lastReportedFever)) {
    lastSendTime = now;
    lastReportedFever = fever;

    float ambientTemperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (isnan(ambientTemperature) || isnan(humidity)) {
      Serial.println("DHT22 reading failed - using last good values.");
      // Still report fever/LED/buzzer state if we have ever had a good reading.
      ambientTemperature = lastGoodTemp;
      humidity = lastGoodHum;
    } else {
      lastGoodTemp = ambientTemperature;
      lastGoodHum = humidity;
    }

    if (isnan(ambientTemperature) || isnan(humidity)) {
      Serial.println("No DHT22 data yet; nothing to send.");
    } else {
      // Fan decision happens locally, BEFORE any network call.
      updateFan(ambientTemperature);

      const int motion = latestMotionState;
      const int vibration = latestVibrationState;
      Serial.print("MPU Motion: ");
      Serial.println(motion ? "DETECTED" : "NONE");
      Serial.print("MPU Vibration: ");
      Serial.println(vibration ? "DETECTED" : "NONE");

      Serial.println("\n--------------------------------");
      Serial.print("Ambient temperature: ");
      Serial.print(ambientTemperature, 2);
      Serial.println(" C");
      Serial.print("Humidity: ");
      Serial.print(humidity, 2);
      Serial.println(" %");
      Serial.print("NTC Fever: ");
      Serial.println(fever ? "YES" : "NO");
      Serial.print("LED/Buzzer: ");
      Serial.println(fever ? "ON" : "OFF");
      Serial.print("Fan: ");
      Serial.print(fanOn ? "ON" : "OFF");
      Serial.print(" (ON at ");
      Serial.print(fanOnTemp, 1);
      Serial.println(" C)");

      sendSensorData(ambientTemperature, humidity, motion, vibration, fever);
    }
  }

  delay(20);
}
