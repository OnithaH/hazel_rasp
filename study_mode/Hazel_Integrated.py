import cv2, pygame, serial, time, os, sys, signal
from picamera2 import Picamera2
import Focus_Tracking, Active_user_tracking, Phone_Detection

# Get the directory where THIS script (Hazel_Integrated.py) is actually stored
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- SIGNAL HANDLER FOR CLEAN EXIT ---
def signal_handler(sig, frame):
    """Triggers the 'finally' block when the Master Controller sends SIGINT."""
    print("\n[INFO] Study Mode stop signal received. Cleaning up...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

def main():
    # --- INITIALIZE SERIAL FOR ESP1 (BASE STATION) ---
    try:
        # Use a short timeout so the AI loop doesn't hang
        esp1 = serial.Serial('/dev/ttyAMA0', 115200, timeout=0.01)
        print("✅ Connected to ESP1 Base Station")
    except Exception as e:
        print(f"❌ Serial Error: {e}. Check wiring or permissions.")
        esp1 = None

    # --- CAMERA SETUP ---
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={'size': (640, 480)})
    picam2.configure(config)
    picam2.start()
    
    # --- AUDIO SETUP (Fixed Paths) ---
    pygame.mixer.init()
    
    # Construct absolute paths to the MP3 files
    ft_alarm_path = os.path.join(SCRIPT_DIR, "Alarm_Sound_FT.mp3")
    pd_alarm_path = os.path.join(SCRIPT_DIR, "Alarm_Sound_PD.mp3")

    try:
        pygame.mixer.music.load(ft_alarm_path)
        music_loaded = True
        print(f"✅ Loaded: {ft_alarm_path}")
    except Exception as e:
        print(f"⚠️ Warning: {ft_alarm_path} not found. Error: {e}")
        music_loaded = False 
        
    try:
        pd_sound = pygame.mixer.Sound(pd_alarm_path)
        print(f"✅ Loaded: {pd_alarm_path}")
    except Exception as e:
        print(f"⚠️ Warning: {pd_alarm_path} not found. Error: {e}")
        pd_sound = None 

    print("🚀 Hazel Integrated Sentinel is running (HEADLESS MODE)...")

    try:
        while True:
            # Check for quit signal from ESP32 via Serial
            if esp1 and esp1.in_waiting > 0:
                data = esp1.read(esp1.in_waiting).decode('utf-8', errors='ignore')
                if 'q' in data:
                    break

            frame_raw = picam2.capture_array()
            if frame_raw is None: continue
            
            # Convert XBGR to BGR
            frame = cv2.cvtColor(frame_raw, cv2.COLOR_BGRA2BGR)
            
            # 1. Focus Tracking (Eyes/Head Pose)
            frame = Focus_Tracking.process_frame(frame, music_loaded)
            
            # 2. Active User Tracking (Movement via ESP1)
            # Re-enabled: Removing imshow reduces lag for smoother motor control
            #frame = Active_user_tracking.process_frame(frame, esp1)
            
            # 3. Phone Detection (YOLO)
            frame = Phone_Detection.process_frame(frame, pd_sound)
            
            # --- DISPLAY DISABLED FOR SPEED ---
            # cv2.imshow("Hazel Integrated Sentinel", frame)
            
            # Keep the 1ms overhead for internal OpenCV maintenance
            cv2.waitKey(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Crucial for releasing hardware
        print("Releasing Study Mode hardware...")
        if esp1: 
            try:
                esp1.write(b'S') # Stop motor before closing
                esp1.close()
            except: pass
        picam2.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
