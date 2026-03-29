import requests
import time
import os
import json

# --- CONFIGURATION ---
API_BASE_URL = "https://hazel-ten-psi.vercel.app/api" 
ROBOT_SECRET = "2a81692c-ccab-4deb-954c-63c6c0c7b08c" 
CHECK_INTERVAL = 5  # Seconds between checks

HEADERS = {
    "Content-Type": "application/json",
    "x-robot-secret": ROBOT_SECRET
}

CMD_FILE    = "/tmp/hazel_web_cmd.txt"       # Where we drop commands
STATUS_FILE = "/tmp/hazel_sensor_data.json"  # Where we read telemetry

def sync():
    try:
        # --- 1. SEND TELEMETRY (PAUSED) ---
        # The telemetry upload logic is temporarily disabled.
        """
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                payload = json.load(f)
            
            response = requests.post(f"{API_BASE_URL}/environment/log", 
                                     json=payload, headers=HEADERS, timeout=5)
            
            if response.status_code == 201:
                print("✅ [TELEMETRY] Successfully saved to Aiven Database.")
            else:
                print(f"❌ [TELEMETRY ERROR] {response.status_code}: {response.text}")
        """

        # --- 2. GET COMMANDS (PAUSED) ---
        # The aroma command polling logic is temporarily disabled.
        """
        response = requests.get(f"{API_BASE_URL}/aroma", headers=HEADERS, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            for aroma in data:
                if aroma.get("isActive"):
                    scent = aroma.get("name", "DEFAULT").upper()
                    print(f"🔔 [WEB COMMAND] User activated {scent}")
                    with open(CMD_FILE, "w") as f:
                        f.write(f"AROMA_{scent}")
                    break
        elif response.status_code != 200:
            print(f"📡 [COMMAND ERROR] {response.status_code}")
        """
        
        print("⏸️  API Sync is currently paused. To resume, uncomment the logic in sync().")

    except Exception as e:
        print(f"📡 [NETWORK ERROR] {e}")

if __name__ == "__main__":
    print(f"🚀 Hazel Sync Worker Started (Paused Mode)...")
    print(f"🔑 Secret: {ROBOT_SECRET[:8]}...")
    while True:
        sync()
        time.sleep(CHECK_INTERVAL)