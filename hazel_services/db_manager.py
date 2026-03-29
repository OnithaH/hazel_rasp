import psycopg2
from psycopg2.extras import RealDictCursor
import time
import uuid

# --- CONFIGURATION (Direct from Prisma .env) ---
# For security/portability, the Pi should ideally load this from a .env file locally.
DATABASE_URL = "postgres://avnadmin:AVNS_gpl60Nmxd.com:28516/hazeldb?sslmode=require"
ROBOT_SECRET = "4aba04ec-2ff1-4ac9-a987-62bf6a25d905"

class DBManager:
    def __init__(self):
        self.conn = None
        self.robot_id = None
        self._connect()

    def _connect(self):
        """Establishes connection to Aiven PostgreSQL."""
        try:
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = True
            print("🔋 Direct DB Connection: SUCCESS")
        except Exception as e:
            print(f"❌ DB Connection Failed: {e}")

    def get_robot_id(self):
        """Lookup the UUID of this robot based on its secret key."""
        if self.robot_id: return self.robot_id
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT id FROM "Robot" WHERE secret_key = %s', (ROBOT_SECRET,))
                res = cur.fetchone()
                if res:
                    self.robot_id = res['id']
                    return self.robot_id
        except Exception as e:
            print(f"⚠️ get_robot_id Error: {e}")
            self._connect() # Retry connection
        return None

    def log_environment(self, temp, humid):
        """Insert a row into EnvironmentLog (Telelmtery)."""
        rid = self.get_robot_id()
        if not rid: return
        
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO "EnvironmentLog" (id, robot_id, temperature, humidity, recorded_at) '
                    'VALUES (%s, %s, %s, %s, NOW())',
                    (str(uuid.uuid4()), rid, temp, humid)
                )
        except Exception as e:
                print(f"⚠️ log_environment Error: {e}")

    def start_study_session(self, duration_min=60, focus_goal=None):
        """Creates a new instance of a study session (The 'Instance' you asked about)."""
        rid = self.get_robot_id()
        if not rid: return None
        
        session_id = str(uuid.uuid4())
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO "StudySession" (id, robot_id, start_time, scheduled_duration, focus_goal) '
                    'VALUES (%s, %s, NOW(), %s, %s)',
                    (session_id, rid, duration_min, focus_goal)
                )
            print(f"📚 Session Instance Created: {session_id}")
            return session_id
        except Exception as e:
            print(f"⚠️ start_study_session Error: {e}")
        return None

    def end_study_session(self, session_id):
        """Closes the session by setting the end_time."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    'UPDATE "StudySession" SET end_time = NOW() WHERE id = %s',
                    (session_id,)
                )
            print(f"✅ Session Instance Closed: {session_id}")
        except Exception as e:
            print(f"⚠️ end_study_session Error: {e}")

    def log_distraction(self, session_id, d_type):
        """Logs phone or drowsiness events during a session."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO "DistractionLog" (id, session_id, type, timestamp) '
                    'VALUES (%s, %s, %s, NOW())',
                    (str(uuid.uuid4()), session_id, d_type)
                )
            print(f"⚠️ Distraction Logged: {d_type}")
        except Exception as e:
            print(f"⚠️ log_distraction Error: {e}")

    def poll_aroma_commands(self):
        """Checks for active Aroma configurations from the dashboard."""
        rid = self.get_robot_id()
        if not rid: return None
        
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    'SELECT scent_name FROM "AromaConfiguration" '
                    'WHERE robot_id = %s AND "isActive" = TRUE LIMIT 1',
                    (rid,)
                )
                res = cur.fetchone()
                return res['scent_name'] if res else None
        except Exception as e:
            print(f"⚠️ poll_aroma Error: {e}")
        return None

if __name__ == "__main__":
    # Diagnostic connectivity test
    mgr = DBManager()
    rid = mgr.get_robot_id()
    if rid:
        print(f"✅ Diagnostic OK. Connected as Robot: {rid}")
        print(f"📡 Aroma Check: {mgr.poll_aroma_commands()}")
    else:
        print("❌ Diagnostic FAILED. Check credentials.")
