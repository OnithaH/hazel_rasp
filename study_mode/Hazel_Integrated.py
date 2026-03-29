import cv2, pygame, serial, time, os, sys, signal, json
from picamera2 import Picamera2
import Focus_Tracking, Phone_Detection

# Add parent directory to path so we can import from hazel_services
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hazel_services'))
from db_manager import DBManager

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_CONFIG = "/tmp/hazel_study_config.json"
BREAK_TRIGGER = "/tmp/hazel_break_trigger.json"

# Initialize Database Manager
db = DBManager()
current_session_id = None

# --- SIGNAL HANDLER FOR CLEAN EXIT ---
def signal_handler(sig, frame):
    global current_session_id
    print("\n[INFO] Study Mode stop signal received. Cleaning up...")
    if current_session_id:
        db.end_study_session(current_session_id)
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def main():
    global current_session_id
    
    # --- INITIALIZE SERIAL FOR ESP1 (BASE STATION) ---
    try:
        esp1 = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.01)
        print("✅ Connected to ESP1 Base Station")
    except Exception as e:
        print(f"❌ Serial Error: {e}")
        esp1 = None

    # --- CAMERA SETUP ---
    picam2 = Picamera2()
    # Main stream for detection, main stream also needs to be compatible with Picamera2 capture_array 
    config = picam2.create_preview_configuration(main={'size': (640, 480)})
    picam2.configure(config)
    picam2.start()
    
    # --- AUDIO SETUP ---
    pygame.mixer.init()
    ft_alarm_path = os.path.join(SCRIPT_DIR, "Alarm_Sound_FT.mp3")
    pygame.mixer.music.load(ft_alarm_path)

    # --- START SESSION INSTANCE ---
    print("🚦 Initializing Study Instance in Database...")
    current_session_id = db.start_study_session(duration_min=60, focus_goal="Direct DB Focus")

    if not current_session_id:
        print("⚠️ Warning: Failed to create session in DB. Sentinel will continue locally.")

    print(f"🚀 Hazel Sentinel ACTIVE. (Session UUID: {current_session_id})")

    # Tracking
    last_ui_update = 0
    distraction_cooldown = 0 

    try:
        while True:
            # 1. READ CLOUD CONFIG (Mailbox - potentially still updated by DB sync worker)
            # The UI logic (T:XX) remains in the main_controller or sync worker
            
            # 2. COMPUTER VISION DETECTION (YOLO & MediaPipe)
            frame_raw = picam2.capture_array()
            if frame_raw is None: continue
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            
            # 4a. Focus/Drowsiness Tracking
            drowsy = Focus_Tracking.is_drowsy(frame)
            
            # 4b. Phone Detection
            phone = Phone_Detection.detect_phone(frame)

            # 3. DISTRACTION ALERT & DB LOGGING
            if (drowsy or phone) and time.time() > distraction_cooldown:
                print(f"⚠️ Distraction Trace: Drowsy={drowsy}, Phone={phone}")
                if esp1: esp1.write(b"A:1\n") # Red LEDs + Peppermint
                # play alarm
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play()
                
                # DIRECT DB INSERT (No API headache)
                if current_session_id:
                    d_type = "PHONE" if phone else "DROWSINESS"
                    db.log_distraction(current_session_id, d_type)
                
                distraction_cooldown = time.time() + 30
            elif not (drowsy or phone) and time.time() < (distraction_cooldown - 28):
                # Reset alarm after at least 2 seconds of good behavior
                if esp1: esp1.write(b"A:0\n")
                pygame.mixer.music.stop()

            # OpenCV waitKey is needed for internal processing
            cv2.waitKey(1)
            
    except Exception as e:
        print(f"\n❌ Sentinel Error: {e}")
    finally:
        print("Releasing Study Mode hardware...")
        if current_session_id:
            db.end_study_session(current_session_id)
        if esp1: 
            try:
                esp1.write(b"A:0\n")
                esp1.write(b"T:0\n")
                esp1.close()
            except: pass
        picam2.stop()

if __name__ == "__main__":
    main()
