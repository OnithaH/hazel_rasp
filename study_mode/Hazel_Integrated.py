import cv2, pygame, serial, time, os, sys, signal, json, shlex, subprocess
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

def speak(text):
    """Voice output via espeak."""
    print(f"🔊 HAZEL: {text}")
    os.system(f"espeak -ven+f3 -s120 -p50 {shlex.quote(text)} 2>/dev/null")

def run_interactive_revision(material_id):
    """Fetches and recites questions for a revision session."""
    speak("Entering Interactive Revise Mode. I will read your questions one by one. Take your time to think or answer out loud.")
    time.sleep(2)
    
    questions = db.get_revision_questions(material_id)
    if not questions:
        speak("I couldn't find any questions for this material. Please check your upload on the website.")
        return

    for idx, q in enumerate(questions):
        speak(f"Question {idx + 1}: {q['question']}")
        print(f"[REVISE] Waiting 10s for response to: {q['question'][:30]}...")
        time.sleep(10) # 10 second interactive delay
        speak(f"The correct answer is: {q['answer']}")
        time.sleep(2) # Short pause before next question
    
    speak("That was the last question. Well done on your revision session.")

def main():
    global current_session_id
    
    # Give a small 1s buffer for DB/Sync consistency
    time.sleep(1)

    # 1. IDENTIFY SESSION & CONFIG
    print("🚦 Fetching Session Details from Database...")
    session = None
    for _ in range(3): # Retry 3 times
        session = db.get_active_session()
        if session: break
        time.sleep(1)
    
    if not session:
        print("❌ No active Web Session found. The robot will not start a session.")
        speak("I don't see an active session on the website yet. Please start one from your dashboard.")
        return # Exit without creating any session records
    else:
        current_session_id = session['id']
        print(f"✅ Synced with Web Session: {current_session_id}")

    is_revise = False
    material_id = None
    if session.get('focus_goal') and session['focus_goal'].startswith("REVISE:"):
        is_revise = True
        material_id = session['focus_goal'].replace("REVISE:", "").strip()

    # --- INITIALIZE SERIAL FOR ESP1 (BASE STATION) ---
    try:
        esp1 = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.01)
        print("✅ Connected to ESP1 Base Station")
    except Exception as e:
        print(f"❌ Serial Error: {e}")
        esp1 = None

    # --- BRANCH LOGIC ---
    if is_revise:
        # PATH A: INTERACTIVE REVISION (Oral Tutoring)
        run_interactive_revision(material_id)
    else:
        # PATH B: STANDARD STUDY (Focus Tracking)
        # --- CAMERA SETUP ---
        picam2 = None
        for _ in range(5): # Camera hardware can be slow to release
            try:
                picam2 = Picamera2()
                config = picam2.create_preview_configuration(main={'size': (640, 480)})
                picam2.configure(config)
                picam2.start()
                break
            except Exception as e:
                print(f"📷 Camera Init Retry... {e}")
                time.sleep(1.5)
        
        if not picam2:
            print("❌ TOTAL CAMERA FAILURE")
            speak("Hardware error. I cannot access the camera.")
            return
        
        # --- AUDIO SETUP ---
        pygame.mixer.init()
        # Separate channels for different alerts if needed, but simple music/channel is fine
        ft_alarm_path = os.path.join(SCRIPT_DIR, "Alarm_Sound_FT.mp3")
        pd_alarm_path = os.path.join(SCRIPT_DIR, "Alarm_Sound_PD.mp3")
        
        # Load sounds as objects instead of just music for better control
        ft_sound = pygame.mixer.Sound(ft_alarm_path)
        pd_sound = pygame.mixer.Sound(pd_alarm_path)

        print(f"🚀 Hazel Sentinel ACTIVE (Phone Detection: {session['phone_detection_enabled']})")
        
        frame_count = 0
        last_db_log_time = 0
        current_alert_type = None # None, "FT", "PD"
        try:
            while True:
                frame_raw = picam2.capture_array()
                if frame_raw is None: continue
                frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
                frame_count += 1
                
                # OPTIMIZATION: Check for drowsiness/phone every few frames to prevent lag
                # This keeps the motion fluid and the robot responsive
                drowsy = False
                phone = False
                
                # Check Drowsiness (Every 2nd frame)
                if frame_count % 2 == 0:
                    drowsy = Focus_Tracking.is_drowsy(frame)
                
                # Check Phone (Every 3rd frame, if enabled)
                if session['phone_detection_enabled'] and frame_count % 3 == 0:
                    phone = Phone_Detection.detect_phone(frame)

                # --- ALERT LOGIC ---
                now = time.time()
                
                # Priority 1: Phone Detection
                if phone:
                    if current_alert_type != "PD":
                        pygame.mixer.stop() # Stop any current sound
                        pd_sound.play(-1)
                        current_alert_type = "PD"
                        if esp1: esp1.write(b"A:1\n")
                        
                    # Log to DB (Throttle to once every 30s)
                    if now - last_db_log_time > 30:
                        db.log_distraction(current_session_id, "PHONE")
                        last_db_log_time = now
                
                # Priority 2: Drowsiness
                elif drowsy:
                    if current_alert_type != "FT":
                        pygame.mixer.stop()
                        ft_sound.play(-1)
                        current_alert_type = "FT"
                        if esp1: esp1.write(b"A:1\n")
                        
                    if now - last_db_log_time > 30:
                        db.log_distraction(current_session_id, "DROWSINESS")
                        last_db_log_time = now
                
                # Clear Alerts
                elif not (phone or drowsy):
                    if current_alert_type is not None:
                        pygame.mixer.stop()
                        current_alert_type = None
                        if esp1: esp1.write(b"A:0\n")

                cv2.waitKey(1)
        except Exception as e:
            print(f"\n❌ Sentinel Error: {e}")
        finally:
            picam2.stop()

    # --- FINAL CLEANUP ---
    print("Releasing Study Mode hardware...")
    if current_session_id:
        db.end_study_session(current_session_id)
    if esp1: 
        try:
            esp1.write(b"A:0\n")
            esp1.write(b"T:0\n")
            esp1.close()
        except: pass

if __name__ == "__main__":
    import shlex
    main()
