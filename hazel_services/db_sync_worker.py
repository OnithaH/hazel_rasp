import requests
import time
import os
import json

# --- CONFIGURATION ---
# Use your Vercel URL for global access
API_BASE_URL = "https://hazel-ten-psi.vercel.app/api" 
ROBOT_SECRET = "4aba04ec-2ff1-4ac9-a987-62bf6a25d905" # Sync-ed to your NEW Hazel Master Robot
CHECK_INTERVAL = 5  # Polling every 5s is safe for Vercel limits

HEADERS = {
    "Content-Type": "application/json",
    "x-robot-secret": ROBOT_SECRET
}

CMD_FILE    = "/tmp/hazel_web_cmd.txt"       # Mailbox for Web -> Robot
STATUS_FILE = "/tmp/hazel_sensor_data.json"  # Mailbox for Robot -> Web

def sync():
    try:
        # 1. SEND TELEMETRY (Robot -> Web)
        # Uploads Battery/Temp data to Vercel so you see it on the dashboard
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                payload = json.load(f)
            
            # Post to: /api/environment/log
            requests.post(f"{API_BASE_URL}/environment/log", 
                          json=payload, headers=HEADERS, timeout=5)

        # 2. GET COMMANDS (Web -> Robot)
        # Checks: /api/aroma
        response = requests.get(f"{API_BASE_URL}/aroma", headers=HEADERS, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # If the API returns a list, find the active one
            for aroma in data:
                if aroma.get("isActive"):
                    # FIXED: Use 'scent_name' to match Prisma Schema
                    scent = aroma.get("scent_name", "DEFAULT").upper()
                    with open(CMD_FILE, "w") as f:
                        f.write(f"AROMA_{scent}")
                    break

    except Exception as e:
        print(f"📡 Sync Error: {e}")

if __name__ == "__main__":
    print(f"🚀 Hazel DB Sync Worker Active (Secret: {ROBOT_SECRET[:8]}...)")
    while True:
        sync()
        time.sleep(CHECK_INTERVAL)
