import serial
import subprocess
import time
import os
import json
import signal
import sys
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
ser2 = None  # ESP2 Light Controller (/dev/ttyAMA3)
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
    os.system(f"espeak -ven+f3 -s120 -p50 {shlex.quote(text)} 2>/dev/null &")

# --- 3. PROCESS MANAGEMENT ---
def run_program(script_path, venv_path, needs_face=True, needs_convo=False, mode_name="General"):
    global active_process, face_process, ser, ser2
    
    # A. Voice Announcement
    speak(f"Now you are in {mode_name} mode")
    
    # Update current mode state
    try:
        with open("/tmp/hazel_current_mode.txt", "w") as f:
            f.write(mode_name)
    except: pass

    # B. Stop existing mode
    if active_process:
        print(f"🛑 Stopping current process: {active_process.pid}")
        active_process.send_signal(signal.SIGINT)
        try:
            active_process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            active_process.kill()
        active_process = None
        time.sleep(2.0)

    # C. Face Persistence
    if needs_face:
        if not face_process:
            print("😊 Opening Hazel Face...")
            face_script = f"{BASE_PATH}/hazel_face/face.py"
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            face_process = subprocess.Popen([ENV_FACE, face_script], env=env, stdout=sys.stdout, stderr=sys.stderr)
    else:
        if face_process:
            print("😴 Closing Hazel Face...")
            face_process.send_signal(signal.SIGINT)
            face_process = None

    # D. Handle Live Conversation
    if needs_convo:
        os.system(f"pm2 start {CONVO_NAME}")
    else:
        os.system(f"pm2 stop {CONVO_NAME}")

    if ser: ser.reset_input_buffer()
    
    # E. ESP2 Light Hand-off
    if mode_name == "Study" and ser2:
        print("💡 Releasing Light Controller to Study Mode...")
        try:
            ser2.close()
            ser2 = None
        except: pass
    elif mode_name != "Study" and not ser2:
        try:
            ser2 = serial.Serial('/dev/ttyAMA3', 115200, timeout=1)
            print("💡 Light Controller Reclaimed")
        except: pass

    # F. Send Mode Light Command
    if ser2:
        mode_map = {"General": b'g', "Game": b'x', "Music": b'm', "Study": b's'}
        cmd = mode_map.get(mode_name, b'g')
        try:
            ser2.write(cmd)
        except: pass

    # G. Launch Mode
    full_path = f"{BASE_PATH}/{script_path}"
    print(f"🚀 Launching {mode_name} Mode...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    active_process = subprocess.Popen([venv_path, full_path], env=env, stdout=sys.stdout, stderr=sys.stderr)

# --- 4. INITIALIZATION ---
try:
    # 1. ESP1 (Base Station)
    ser = serial.Serial('/dev/ttyAMA0', 115200, timeout=1)
    time.sleep(2) 
    ser.write(b'1') # Trigger JBL Power ON
    print("✅ ESP1 Base Station Connected")

    # 2. ESP2 (Light Controller)
    try:
        ser2 = serial.Serial('/dev/ttyAMA3', 115200, timeout=1)
        ser2.write(b'g') # Default to General (White)
        print("✅ ESP2 Light Controller Connected")
    except Exception as e2:
        print(f"⚠️ Light Controller (ESP2) skipped: {e2}")

    print("✅ Hardware Ready")
except Exception as e:
    print(f"❌ Hardware Initialization Error: {e}")

# Initial Start
with open("/tmp/hazel_current_mode.txt", "w") as f:
    f.write("General")
run_program("general_mode/general_mode.py", ENV_GENERAL, needs_face=False, needs_convo=True, mode_name="General")

# --- 5. MAIN LOOP ---
current_active_mode = "General"
last_mode_change_time = 0
last_vol_change_time = 0
MODE_SWITCH_COOLDOWN = 3.0
VOL_CHANGE_COOLDOWN = 0.3

try:
    last_sync = 0
    last_dht_request = 0
    while True:
        now = time.time()
        current_v = get_voltage()
        
        # Poll DHT every 30s
        if now - last_dht_request > 30:
            if ser: ser.write(b'd') 
            last_dht_request = now

        if 0.1 < current_v < 6.4:
            if ser: ser.write(b'0')
            os.system("sudo shutdown now")

        # Remote Web Commands
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
                    run_program("general_mode/general_mode.py", ENV_GENERAL, True, True, "General")
                    current_active_mode = "General"
                    last_mode_change_time = now
                elif cmd == "MODE_GAME" and current_active_mode != "Game":
                    run_program("game_mode/main.py", ENV_GAME, False, False, "Game")
                    current_active_mode = "Game"
                    last_mode_change_time = now
                elif cmd == "MODE_MUSIC" and current_active_mode != "Music":
                    run_program("music_mode/gesture_music_bridge.py", ENV_MUSIC, True, False, "Music")
                    current_active_mode = "Music"
                    last_mode_change_time = now
            except Exception as e:
                print(f"⚠️ Remote Cmd Error: {e}")

        # Physical Inputs
        if ser and ser.in_waiting > 0:
            raw = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            if "Vol up" in raw and (now - last_vol_change_time > VOL_CHANGE_COOLDOWN):     
                os.system("amixer set Master 5%+")
                last_vol_change_time = now
            elif "Vol down" in raw and (now - last_vol_change_time > VOL_CHANGE_COOLDOWN):
                os.system("amixer set Master 5%-")
                last_vol_change_time = now
            elif "T:" in raw:
                try:
                    parts = raw.split()
                    temp = float(parts[0].replace("T:", ""))
                    humid = float(parts[1].replace("H:", ""))
                    data = {"temperature": temp, "humidity": humid}
                    with open("/tmp/hazel_sensor_data.json", "w") as f:
                        json.dump(data, f)
                except: pass

        time.sleep(0.01)

except KeyboardInterrupt:
    if active_process: active_process.kill()
    if face_process: face_process.kill()
