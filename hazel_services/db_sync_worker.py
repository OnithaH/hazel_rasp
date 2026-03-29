import time
import os
import json
from db_manager import DBManager

# --- CONFIGURATION ---
CHECK_INTERVAL = 5  # Polling every 5s
CMD_FILE    = "/tmp/hazel_web_cmd.txt"       # Mailbox for Web -> Robot
STATUS_FILE = "/tmp/hazel_sensor_data.json"  # Mailbox for Robot -> Web

# Initialize the Direct Database Manager
db = DBManager()
last_session_check = 0 
last_known_session_id = None # Memory for state-change detection
last_known_mode = "GENERAL"  # Memory for global state-change detection

def sync():
    global last_session_check, last_known_session_id, last_known_mode
    try:
        # 1. SEND TELEMETRY (Robot -> DB)
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                payload = json.load(f)
            
            # Extract temp/humid from the mailbox file
            temp = payload.get("temperature", 0.0)
            humid = payload.get("humidity", 0.0)
            
            # Direct SQL Insert
            db.log_environment(temp, humid)
            print(f"🌡️  TELEMETRY SYNCED: {temp}°C, {humid}% (Uploaded to Database)")

        # 2. GET COMMANDS (DB -> Robot)
        active_scent = db.poll_aroma_commands()
        
        if active_scent:
            scent_cmd = f"AROMA_{active_scent.upper()}"
            with open(CMD_FILE, "w") as f:
                f.write(scent_cmd)
            print(f"🔔 [DB COMMAND] User activated {active_scent}")
        else:
            # Clear command file if no active aroma
            if os.path.exists(CMD_FILE):
                os.remove(CMD_FILE)

        # 3. WEB-COMMAND POLLING (Check for active Study sessions & Global Mode every 10s)
        if time.time() - last_session_check > 10:
            # A. Check for specific active Study sessions (Higher Priority)
            active_session = db.get_active_session()
            current_id = active_session['id'] if active_session else None
            
            # B. Check for Website-wide Global Mode (Study, Music, Games, General)
            current_mode = db.get_robot_mode() # Fetches 'GENERAL', 'STUDY', 'GAME', 'MUSIC'
            
            # 1. Handle Study Session Transitions (Standard Study Mode start/end)
            if current_id != last_known_session_id:
                if current_id:
                    print(f"📡 Web-Initiated Session Detected: {current_id}")
                    with open("/tmp/hazel_mode_cmd", "w") as f: f.write("MODE_STUDY")
                else:
                    print(f"📡 Web-Initiated Session ENDED. Reverting to {current_mode}.")
                    cmd = f"MODE_{current_mode.upper()}"
                    with open("/tmp/hazel_mode_cmd", "w") as f: f.write(cmd)
                
                last_known_session_id = current_id # Update memory
                last_known_mode = current_mode # Also update mode memory

            # 2. Handle Global Mode Transitions (Header Switches in Web UI)
            elif current_mode != last_known_mode:
                print(f"📡 Web-Requested Global Mode Change: {current_mode}")
                cmd = f"MODE_{current_mode.upper()}"
                with open("/tmp/hazel_mode_cmd", "w") as f: f.write(cmd)
                last_known_mode = current_mode

            last_session_check = time.time()

    except Exception as e:
        print(f"📡 Sync Error: {e}")

if __name__ == "__main__":
    print("-" * 50)
    print("🚀 HAZEL DIRECT-DB SYNC WORKER ACTIVE")
    print("-" * 50)
    
    while True:
        sync()
        time.sleep(CHECK_INTERVAL)
