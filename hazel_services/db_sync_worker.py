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

def sync():
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

        # 3. WEB-COMMAND POLLING (Check for active Study sessions every 10s)
        if time.time() - last_session_check > 10:
            active_session = db.get_active_session()
            if active_session:
                print(f"📡 Web-Initiated Session Detected: {active_session['id']}")
                # Signal main_controller to switch to STUDY mode
                with open("/tmp/hazel_mode_cmd", "w") as f:
                    f.write("MODE_STUDY")
            else:
                # If no session found, ensure we switch back to GENERAL if we were in STUDY
                # The main_controller is smart enough not to loop if it's already in General
                with open("/tmp/hazel_mode_cmd", "w") as f:
                    f.write("MODE_GENERAL")
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
