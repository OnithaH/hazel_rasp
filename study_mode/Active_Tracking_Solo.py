import cv2, serial, time
import mediapipe as mp
from picamera2 import Picamera2
from collections import deque

# 1. SERIAL SETUP (GPIO Pins 8 & 10)
try:
    # Use timeout=0.01 to keep AI loop fast
    esp1 = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.01)
    print("✅ Hazel Base Station Connected")
except Exception as e:
    print(f"❌ Serial Error: {e}")
    exit()

# 2. CAMERA SETUP
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={'size': (640, 480)})
picam2.configure(config)
picam2.start()

# 3. AI POSE SETUP (Lite for speed)
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, model_complexity=0) 
history = deque(maxlen=5)

print("🚀 Starting High-Speed User Tracking...")

try:
    while True:
        # --- RECEIVE FEEDBACK (Mode/Vol Display) ---
        if esp1.in_waiting:
            # Catch messages like "Vol up" or "Mode: STUDY"
            data = esp1.readline().decode('utf-8', errors='replace').strip()
            if data: print(f"[ESP 1]: {data}")

        # --- PROCESS AI ---
        frame_raw = picam2.capture_array()
        if frame_raw is None: continue
        
        frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
        results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if results.pose_landmarks:
            lms = results.pose_landmarks.landmark
            # Tracking midpoint between shoulders
            current_x = (lms[11].x + lms[12].x) / 2
            history.append(current_x)
            smoothed_x = sum(history) / len(history)

            # Determine Movement Status
            if smoothed_x < 0.40:
                status = "USER LEFT -> Rotating Base LEFT"
                esp1.write(b'L')
            elif smoothed_x > 0.60:
                status = "USER RIGHT -> Rotating Base RIGHT"
                esp1.write(b'R')
            else:
                status = "USER CENTERED -> Stopping"
                esp1.write(b'S')

            # Display exact interface text
            cv2.putText(frame, status, (10, 30), 0, 0.7, (0, 255, 0), 2)
            cv2.line(frame, (int(0.4*640), 0), (int(0.4*640), 480), (255, 255, 255), 1)
            cv2.line(frame, (int(0.6*640), 0), (int(0.6*640), 480), (255, 255, 255), 1)
        else:
            esp1.write(b'S')

        cv2.imshow("Hazel Solo Tracking", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    esp1.write(b'S')
    esp1.close()
    picam2.stop()
    cv2.destroyAllWindows()
