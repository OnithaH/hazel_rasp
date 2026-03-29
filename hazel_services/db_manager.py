import psycopg2
from psycopg2.extras import RealDictCursor
import time
import uuid
import os

# --- SECURE CONFIGURATION LOADING ---
# We load these from a local .env file on the Pi that is NEVER pushed to GitHub.
DATABASE_URL = None
ROBOT_SECRET = None

def load_local_env():
    """Simple .env loader for the Raspberry Pi environment."""
    global DATABASE_URL, ROBOT_SECRET
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    try:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"').strip("'")
                        if key == 'DATABASE_URL': DATABASE_URL = value
                        if key == 'ROBOT_SECRET': ROBOT_SECRET = value
            print("🔐 Secrets loaded from local .env successfully.")
    except Exception as e:
        print(f"⚠️ Failed to load local .env: {e}")

# Initial load
load_local_env()

class DBManager:
    def __init__(self):
        self.conn = None
        self.robot_id = None
        if not DATABASE_URL:
            # Final fallback to os.environ for cloud environments
            self.db_url = os.getenv('DATABASE_URL')
            self.secret = os.getenv('ROBOT_SECRET')
        else:
            self.db_url = DATABASE_URL
            self.secret = ROBOT_SECRET
            
        self._connect()

    def _connect(self):
        """Establishes connection to Aiven PostgreSQL."""
        if not self.db_url:
            print("❌ DB ERROR: No DATABASE_URL found in .env or OS ENVIRONMENT.")
            return

        try:
            self.conn = psycopg2.connect(self.db_url)
            self.conn.autocommit = True
            print("🔋 Direct DB Connection: SUCCESS")
        except Exception as e:
            print(f"❌ DB Connection Failed: {e}")

    def get_robot_id(self):
        """Lookup the UUID of this robot based on its secret key."""
        if self.robot_id: return self.robot_id
        if not self.secret: return None
        
        try:
            if not self.conn or self.conn.closed:
                self._connect()

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT id FROM "Robot" WHERE secret_key = %s', (self.secret,))
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
        """Creates a new instance of a study session."""
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

    def get_active_session(self):
        """Find any study session currently running for this robot."""
        rid = self.get_robot_id()
        if not rid: return None
        
        try:
            if not self.conn or self.conn.closed: self._connect()
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    'SELECT id, focus_goal, scheduled_duration, phone_detection_enabled, break_activity '
                    'FROM "StudySession" WHERE robot_id = %s AND end_time IS NULL '
                    'ORDER BY start_time DESC LIMIT 1',
                    (rid,)
                )
                return cur.fetchone()
        except Exception as e:
            print(f"⚠️ get_active_session Error: {e}")
        return None

    def get_revision_questions(self, material_id):
        """Fetch all questions for a specific material."""
        try:
            if not self.conn or self.conn.closed: self._connect()
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    'SELECT question, answer FROM "RevisionQuestion" '
                    'WHERE material_id = %s',
                    (material_id,)
                )
                return cur.fetchall()
        except Exception as e:
            print(f"⚠️ get_revision_questions Error: {e}")
        return []

    def poll_aroma_commands(self):
        """Checks for active Aroma configurations from the dashboard."""
        rid = self.get_robot_id()
        if not rid: return None
        
        try:
            if not self.conn or self.conn.closed: self._connect()
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

    def get_robot_mode(self):
        """Fetch the currently active operating mode from the Robot table."""
        rid = self.get_robot_id()
        if not rid: return "GENERAL"
        
        try:
            if not self.conn or self.conn.closed: self._connect()
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute('SELECT mode FROM "Robot" WHERE id = %s', (rid,))
                res = cur.fetchone()
                return res['mode'] if res else "GENERAL"
        except Exception as e:
            print(f"⚠️ get_robot_mode Error: {e}")
        return "GENERAL"

if __name__ == "__main__":
    # Diagnostic connectivity test
    mgr = DBManager()
    rid = mgr.get_robot_id()
    if rid:
        print(f"✅ Diagnostic OK. Connected as Robot: {rid}")
        print(f"📡 Aroma Check: {mgr.poll_aroma_commands()}")
        print(f"📚 Active Session: {mgr.get_active_session()}")
    else:
        print("❌ Diagnostic FAILED. Check credentials.")
