"""
Real-time Hand Gesture Control for Robotic Hand
===============================================

Uses MediaPipe Hands to detect one hand and map gestures to serial commands
that control a physical robotic hand (Arduino + servos).

Controls:
- Wrist rotation     → based on index ↔ pinky x-position (hand tilt)
- Thumb opposition   → thumb tip x relative to thumb base + hand spread check
- Index & Middle     → fingertip y above base = closed
- Ring + Pinky       → both fingertips above base = both closed (shared servo)

Note:
- Ring and pinky fingers are mechanically linked → controlled by ONE servo (finger 3)
- Commands sent as two-character strings: "01", "11", "20", "41", etc.
- Matches the command format expected by the Arduino sketch

Hardware assumptions:
- Serial port: COM7 @ 9600 baud (change as needed)
- Webcam: default camera (index 0)
"""

import cv2
import mediapipe as mp
import serial
import time

# ───────────────────────────────────────────────
#  MediaPipe Initialization
# ───────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# We only track one hand for simplicity and performance
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

# Landmark indices for fingertips and PIP joints
FINGERTIP_IDS = [4, 8, 12, 16, 20]   # thumb, index, middle, ring, pinky
PIP_BASE_IDS  = [2, 6, 10, 14, 18]

# State tracking to avoid sending repeated commands
is_closed = [False, False, False, False]   # thumb, index, middle, ring/pinky
is_rotated = False

# ───────────────────────────────────────────────
#  Serial Communication Setup
# ───────────────────────────────────────────────
# Change 'COM7' → '/dev/ttyUSB0', 'COM3', etc. depending on your system
ser = serial.Serial('COM7', 9600, timeout=1)
time.sleep(2.0)  # important: give Arduino time to reset after opening port

print("Serial port opened. Waiting for hand gestures...\n")

# ───────────────────────────────────────────────
#  Video Capture
# ───────────────────────────────────────────────
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

while cap.isOpened():
    success, image = cap.read()
    if not success:
        print("Warning: Empty camera frame.")
        continue

    # Flip horizontally for selfie-view and convert to RGB for MediaPipe
    image = cv2.flip(image, 1)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    # Process hand landmarks
    results = hands.process(image_rgb)

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Draw landmarks & connections on the image
            mp_drawing.draw_landmarks(
                image,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=4),
                mp_drawing.DrawingSpec(color=(0, 128, 255), thickness=2)
            )

            lm = hand_landmarks.landmark  # shortcut

            # ───── Wrist rotation (hand tilt) ─────
            # We use index fingertip x vs pinky MCP x as a simple tilt detector
            if lm[FINGERTIP_IDS[0]].x < lm[PIP_BASE_IDS[4]].x:   # thumb tip left of pinky base
                if not is_rotated:
                    print("→ Wrist rotate FORWARD")
                    ser.write(b'41')
                    is_rotated = True
                    time.sleep(0.6)
            else:
                if is_rotated:
                    print("→ Wrist rotate BACK")
                    ser.write(b'40')
                    is_rotated = False
                    time.sleep(0.6)

            # ───── Thumb (special logic because of opposition) ─────
            # We adjust logic depending on whether hand is rotated
            thumb_tip_x = lm[FINGERTIP_IDS[0]].x
            thumb_pip_x = lm[PIP_BASE_IDS[0]].x

            # Also require some hand spread to avoid false triggers
            hand_width = abs(lm[PIP_BASE_IDS[1]].x - lm[PIP_BASE_IDS[4]].x)

            if is_rotated:
                should_close_thumb = (thumb_tip_x > thumb_pip_x)
            else:
                should_close_thumb = (thumb_tip_x < thumb_pip_x)

            if should_close_thumb and not is_closed[0] and hand_width > 0.1:
                print("→ Closing THUMB")
                ser.write(b'01')
                is_closed[0] = True
                time.sleep(0.6)

            elif not should_close_thumb and is_closed[0] and hand_width > 0.1:
                print("→ Opening THUMB")
                ser.write(b'00')
                is_closed[0] = False
                time.sleep(0.6)

            # ───── Index & Middle fingers (independent) ─────
            for i in range(1, 3):  # index=1, middle=2
                tip_y = lm[FINGERTIP_IDS[i]].y
                pip_y = lm[PIP_BASE_IDS[i]].y

                if tip_y > pip_y + 0.02:   # small threshold to reduce jitter
                    if not is_closed[i]:
                        print(f"→ Closing finger {i}")
                        ser.write(f"{i}1".encode())
                        is_closed[i] = True
                        time.sleep(0.5)
                else:
                    if is_closed[i]:
                        print(f"→ Opening finger {i}")
                        ser.write(f"{i}0".encode())
                        is_closed[i] = False
                        time.sleep(0.5)

            # ───── Ring + Pinky (linked — one servo) ─────
            ring_tip_y  = lm[FINGERTIP_IDS[3]].y
            pinky_tip_y = lm[FINGERTIP_IDS[4]].y
            ring_pip_y  = lm[PIP_BASE_IDS[3]].y

            both_closed = (ring_tip_y > ring_pip_y + 0.02) and (pinky_tip_y > ring_pip_y + 0.02)

            if both_closed and not is_closed[3]:
                print("→ Closing RING + PINKY")
                ser.write(b'31')
                is_closed[3] = True
                time.sleep(0.5)

            elif not both_closed and is_closed[3]:
                print("→ Opening RING + PINKY")
                ser.write(b'30')
                is_closed[3] = False
                time.sleep(0.5)

    # Show the result
    cv2.imshow('Hand Gesture → Robotic Hand', image)

    key = cv2.waitKey(5) & 0xFF
    if key == 27:          # ESC
        break
    if key in (13, 10):    # Enter
        if results.multi_hand_landmarks:
            print("\nCurrent landmarks:")
            print(results.multi_hand_landmarks)

print("Closing camera and serial port...")
cap.release()
ser.close()
cv2.destroyAllWindows()