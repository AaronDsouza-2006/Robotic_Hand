/*
 * Robotic Hand Control - Serial Command Driven
 * =============================================
 * Controls a 5-finger robotic hand using hobby servos
 * 
 * Servos used:
 *   - 4× finger flexion servos (index, middle, ring, pinky)
 *   - 1× thumb opposition / CMC joint servo
 *   - 1× wrist rotation / pronation-supination servo
 * 
 * Serial commands (single line, no newline required):
 *   "01"  → close thumb + opposition
 *   "00"  → open thumb + opposition
 *   "11"  → close index
 *   "10"  → open index
 *   "21"  → close middle
 *   "20"  → open middle
 *   "31"  → close ring
 *   "30"  → open ring
 *   "41"  → rotate wrist one way
 *   "40"  → rotate wrist back
 * 
 * Hardware notes:
 *   - Made for MG99R 360 - speed controlled (finger flexion and wrist rotation)
 *   - Opposition uses MG90s - Position controlled
 *   - Finger closing uses higher PWM values (stall torque position)
 *   - Finger opening uses low PWM values
 *   - The degrees are not position; they are speed. 
 *   - 0 degrees- clockwise highest speed; 90 degrees- stall; 180 degrees- anticlockwise highest speed
 */

#include <Servo.h>

// ───────────────────────────────────────────────
//  Servo Objects
// ───────────────────────────────────────────────
Servo fingerServo[4];       // 0=thumb, 1=index, 2=middle, 3=ring/pinky
Servo rotateServo;          // wrist rotation / forearm pronation
Servo thumbOppServo;        // thumb opposition (CMC joint)
Servo OnPin;              // always-on test servo (debug/monitoring)
Servo OffPin;             // always-off test servo (debug/monitoring)

// ───────────────────────────────────────────────
//  Pin Assignments (change for your build)
// ───────────────────────────────────────────────
static const int fingerPins[4]   = {8,  9, 10, 11};   // thumb, index, middle, ring/pinky
static const int rotatePin       = 7;
static const int thumbOppPin     = 6;
static const int onPin           = 12;   // debug: constantly driven servo
static const int offPin          = 2;    // debug: constantly driven servo (opposite)

// Logical finger indices (used in commands)
static const int THUMB  = 0;
static const int INDEX  = 1;
static const int MIDDLE = 2;
static const int RING   = 3;

// ───────────────────────────────────────────────
//  Servo Calibration / Tuning Values
// ───────────────────────────────────────────────
// These were found through trial and error — tune per your build!
static const int Duration[4]     = {800, 920, 1050, 850};   // ms — how long to apply torque
static const int CloseTorque[4]  = {160, 165, 175, 170};    // Speed value to close
static const int OpenTorque[4]   = { 35,  25,  20,  30};    // Speed Value to open fully

// ───────────────────────────────────────────────
//  State Tracking
// ───────────────────────────────────────────────
bool is_closed[4]   = {false, false, false, false};  // per-finger closed state
bool is_rotated     = false;                         // wrist rotation state

void setup() {
  Serial.begin(9600);
  while (!Serial) delay(10);  // Wait for serial

  Serial.println(F("Robotic Hand Controller"));
  Serial.println(F("--------------------------------"));
  Serial.println(F("Commands: XX where X=finger(0-3), second digit 0=open 1=close"));
  Serial.println(F("  Special: 41 = rotate forward, 40 = rotate back"));
  Serial.println(F("Ready.\n"));

  // Attach and center all finger servos
  for (int i = 0; i < 4; i++) {
    fingerServo[i].attach(fingerPins[i]);
    fingerServo[i].write(90);
    delay(50);
  }

  rotateServo.attach(rotatePin);
  rotateServo.write(90);

  thumbOppServo.attach(thumbOppPin);
  thumbOppServo.write(90);

  // Debug servos (always driven)
  OnPin.attach(onPin);
  OnPin.write(0);     // one extreme

  OffPin.attach(offPin);
  OffPin.write(180);  // other extreme
}

void loop() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    // Expect at least 2 characters
    if (input.length() < 2) return;

    char fingerChar = input[0];
    char actionChar = input[1];

    if (fingerChar < '0' || fingerChar > '4' || 
        (actionChar != '0' && actionChar != '1')) {
      Serial.println(F("Invalid command. Use format: D A  (D=0..4, A=0 or 1)"));
      return;
    }

    int finger = fingerChar - '0';
    bool shouldClose = (actionChar == '1');

    // ────────────────
    //  Thumb special handling (opposition)
    // ────────────────
    if (finger == THUMB) {
      if (shouldClose) {
        thumbOppServo.write(0);   // full opposition
        delay(50);
      } else {
        thumbOppServo.write(90);  // neutral / reset opposition
        delay(50);
      }
    }

    // ────────────────
    //  Finger open / close
    // ────────────────
    if (finger <= RING) {   // 0–3 = fingers
      if (shouldClose && !is_closed[finger]) {
        Serial.print(F("Closing finger "));
        Serial.println(finger);

        fingerServo[finger].write(CloseTorque[finger]);
        delay(Duration[finger]);
        fingerServo[finger].write(90);          // return to neutral

        is_closed[finger] = true;
      }
      else if (!shouldClose && is_closed[finger]) {
        Serial.print(F("Opening finger "));
        Serial.println(finger);

        fingerServo[finger].write(OpenTorque[finger]);
        delay(700);                             // longer open time usually needed
        fingerServo[finger].write(90);

        is_closed[finger] = false;
      }
    }

    // ────────────────
    //  Wrist rotation (special command 4x)
    // ────────────────
    if (finger == 4) {
      if (shouldClose && !is_rotated) {
        Serial.println(F("Rotating wrist forward"));
        rotateServo.write(0);
        delay(600);
        rotateServo.write(90);
        is_rotated = true;
      }
      else if (!shouldClose && is_rotated) {
        Serial.println(F("Rotating wrist back"));
        rotateServo.write(180);
        delay(550);
        rotateServo.write(90);
        is_rotated = false;
      }
    }

    delay(100); //simple debounce
  }
}