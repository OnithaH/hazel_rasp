import cv2, serial, time, signal, sys
import mediapipe as mp
from picamera2 import Picamera2
from collections import deque

# --- SIGNAL HANDLER FOR CLEAN EXIT ---
def signal_handler(sig, frame):
    """Triggers when the master controller sends SIGINT or SIGTERM."""
    print("\n[INFO] Termination signal received. Cleaning up...")
    sys.exit(0) # This forces the code into the 'finally' block

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# 1. SERIAL SETUP
try:
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

# 3. AI POSE SETUP
mp_pose = mp.solutions.pose
# complexity=0 is faster for Raspberry Pi
pose = mp_pose.Pose(static_image_mode=False, model_complexity=0) 
history = deque(maxlen=5)

print("🚀 Starting High-Speed User Tracking...")

try:
    while True:
        # A. Check for 'q' (Quit) command from the Master Controller via Serial
        if esp1.in_waiting:
            data = esp1.readline().decode('utf-8', errors='replace').strip()
            if 'q' in data: 
                print("[INFO] Master requested quit. Exiting...")
                break # Jump to finally block

        # B. AI Processing
        frame_raw = picam2.capture_array()
        if frame_raw is None: continue
        
        frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
        results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if results.pose_landmarks:
            lms = results.pose_landmarks.landmark
            current_x = (lms[11].x + lms[12].x) / 2
            history.append(current_x)
            smoothed_x = sum(history) / len(history)

            # Movement Logic
            if smoothed_x < 0.35:
                status = "USER LEFT -> Rotating Base LEFT"
                esp1.write(b'L')
            elif smoothed_x > 0.65:
                status = "USER RIGHT -> Rotating Base RIGHT"
                esp1.write(b'R')
            else:
                status = "USER CENTERED -> Stopping"
                esp1.write(b'S')

            # Visual Feedback
            cv2.putText(frame, status, (10, 30), 0, 0.7, (0, 255, 0), 2)
        else:
            esp1.write(b'S') # Stop if user lost

        #cv2.imshow("Hazel Solo Tracking", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    # --- CRITICAL CLEANUP ---
    # Without this, the next mode will get "Camera Busy" errors
    print("Shutting down General Mode hardware...")
    try:
        esp1.write(b'S') # Stop motors
        esp1.close()
        picam2.stop()    # Release Camera
        cv2.destroyAllWindows()
    except Exception as e:
        print(f"Cleanup error: {e}")
    print("✅ General Mode Cleaned Up Successfully")
