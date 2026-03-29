import serial
import subprocess
import time
import os
import json
import signal
import shlex  # Safely handles strings for system commands

# Try to import smbus2 for UPS HAT B
try:
    import smbus2
except ImportError:
    
    print("⚠️ smbus2 not found. Run: pip install smbus2")

# --- 1. CONFIGURATION & PATHS ---
BASE_PATH   = "/home/hazel123/Documents/hazel_rasp"
ENV_FACE    = f"{BASE_PATH}/hazel_face/venv/bin/python3"
ENV_GENERAL = f"{BASE_PATH}/general_mode/venv/bin/python" 
ENV_STUDY   = f"{BASE_PATH}/study_mode/venv/bin/python"
ENV_GAME    = f"{BASE_PATH}/game_mode/venv/bin/python"
ENV_MUSIC   = f"{BASE_PATH}/music_mode/venv/bin/python"

# Communication Files
CONVO_NAME  = "hazel-live-convo"

# Hardware Settings
UPS_ADDR = 0x42 
bus = None
ser = None
active_process = None
face_process   = None 

# --- 2. HARDWARE HELPERS ---
try:
    bus = smbus2.SMBus(1)
except Exception as e:
    print(f"❌ I2C Error: {e}")

def get_voltage():
    if not bus: return 0.0
    try:
        read = bus.read_word_data(UPS_ADDR, 0x02)
        swapped = ((read << 8) & 0xFF00) | ((read >> 8) & 0x00FF)
        voltage = (swapped >> 3) * 0.004 
        return round(voltage, 2)
    except: return 0.0

def speak(text):
    """Uses espeak to announce mode changes in the background."""
    print(f"🔊 HAZEL: {text}")
    # The '&' at the end ensures the Pi doesn't wait for the voice to finish before switching modes
    os.system(f"espeak -ven+f3 -s120 -p50 {shlex.quote(text)} 2>/dev/null &")

# --- 3. PROCESS MANAGEMENT ---
def run_program(script_path, venv_path, needs_face=True, needs_convo=False, mode_name="General"):
    global active_process, face_process, ser
    
    # A. Voice Announcement
    speak(f"Now you are in {mode_name} mode")

    # B. Stop existing mode cleanly to release Camera hardware
    if active_process:
        print(f"🛑 Stopping current process: {active_process.pid}")
        active_process.send_signal(signal.SIGINT) # Triggers 'finally' cleanup in scripts
        try:
            active_process.wait(timeout=2.0) # Give it time to run cleanup
        except subprocess.TimeoutExpired:
            active_process.kill() # Force kill if it hangs
        active_process = None
        time.sleep(0.5) # Critical delay to allow GPU/Camera reset

    # C. Face Persistence
    if needs_face:
        if not face_process:
            print("😊 Opening Hazel Face...")
            face_script = f"{BASE_PATH}/hazel_face/face.py"
            face_process = subprocess.Popen([ENV_FACE, face_script])
    else:
        if face_process:
            print("😴 Closing Hazel Face...")
            face_process.send_signal(signal.SIGINT)
            face_process = None

    # D. Handle Live Conversation (Managed via PM2)
    if needs_convo:
        os.system(f"pm2 start {CONVO_NAME}")
    else:
        os.system(f"pm2 stop {CONVO_NAME}")

    if ser: ser.reset_input_buffer()
    
    # E. Launch Mode
    full_path = f"{BASE_PATH}/{script_path}"
    print(f"🚀 Launching {mode_name} Mode...")
    active_process = subprocess.Popen([venv_path, full_path])


# --- 4. INITIALIZATION ---
try:
    ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
    time.sleep(2) 
    ser.write(b'1') # Trigger JBL Power ON
    print("✅ Hardware Ready")
except Exception as e:
    print(f"❌ Serial Error: {e}")

# Initial Mode Start
run_program("general_mode/general_mode.py", ENV_GENERAL, needs_face=False, needs_convo=False, mode_name="General")

# --- 5. MAIN LOOP ---
current_active_mode = "General"
try:
    last_sync = 0
    last_dht_request = 0
    while True:
        # A. Telemetry & Battery Safety (Every 10s)
        current_v = get_voltage()
        
        # Poll DHT every 30s
        if time.time() - last_dht_request > 30:
            if ser: ser.write(b'd') 
            last_dht_request = time.time()

        if 0.1 < current_v < 6.4: # Shutdown for 2S Li-ion
            if ser: ser.write(b'0') # JBL OFF
            os.system("sudo shutdown now")

        # B. Check Remote Web Commands (From db_sync_worker)
        if os.path.exists("/tmp/hazel_mode_cmd") and (now - last_mode_change_time > MODE_SWITCH_COOLDOWN):
            try:
                with open("/tmp/hazel_mode_cmd", "r") as f:
                    cmd = f.read().strip()
                os.remove("/tmp/hazel_mode_cmd")
                
                if cmd == "MODE_STUDY" and current_active_mode != "Study":
                    run_program("study_mode/Hazel_Integrated.py", ENV_STUDY, True, False, "Study")
                    current_active_mode = "Study"
                    last_mode_change_time = now
                elif cmd == "MODE_GENERAL" and current_active_mode != "General":
                    run_program("general_mode/general_mode.py", ENV_GENERAL, True, False, "General")
                    current_active_mode = "General"
                    last_mode_change_time = now
            except Exception as e:
                print(f"⚠️ Remote Cmd Error: {e}")

        # C. Check Physical Inputs (ESP32 UART)
        if ser and ser.in_waiting > 0:
            raw = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            
            # --- MODE BUTTONS DISABLED PER USER REQUEST ---
            # (Stops ghost-switch interference/yapping loops)
            if "Vol up" in raw:     
                os.system("amixer set Master 5%+")
            
            elif "Vol down" in raw:   
                os.system("amixer set Master 5%-")
            
            # C. Parse DHT Telemetry (Keep active for health monitoring)
            elif "T:" in raw:
                try:
                    # Example: T:24.5 H:60.2
                    parts = raw.split()
                    temp = float(parts[0].replace("T:", ""))
                    humid = float(parts[1].replace("H:", ""))
                    
                    # Store in Mailbox for DB Sync Worker
                    data = {"temperature": temp, "humidity": humid}
                    with open("/tmp/hazel_sensor_data.json", "w") as f:
                        json.dump(data, f)
                except Exception as e:
                    print(f"⚠️ Telemetry Parse Error: {e}")

        time.sleep(0.01)

except KeyboardInterrupt:
    if active_process: active_process.kill()
    if face_process: face_process.kill()
