import os, sys
# Add parent directory to path so we can import from hazel_services
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'hazel_services'))
from db_manager import DBManager

def main():
    db = DBManager()
    rid = db.get_robot_id()
    if not rid:
        print("❌ FAILED: Could not identify robot ID. Check .env")
        return

    print(f"🧹 Starting Database Cleanup for Robot: {rid}")
    
    try:
        if not db.conn or db.conn.closed: db._connect()
        with db.conn.cursor() as cur:
            # 1. Identify Junk Sessions
            cur.execute(
                'SELECT id FROM "StudySession" WHERE robot_id = %s AND focus_goal = %s',
                (rid, "Local Focus Session")
            )
            junk_ids = [row[0] for row in cur.fetchall()]
            
            if not junk_ids:
                print("✨ No junk 'Local Focus Session' records found. Database is clean!")
                return

            print(f"🔍 Found {len(junk_ids)} redundant session records. Cleaning up...")
            
            # 2. Delete Junk Sessions (DistractionLogs will cascade delete due to Prisma schema definition)
            cur.execute(
                'DELETE FROM "StudySession" WHERE id IN %s',
                (tuple(junk_ids),)
            )
            print(f"✅ SUCCESSFULLY deleted {len(junk_ids)} redundant records.")
            
    except Exception as e:
        print(f"❌ CLEANUP FAILED: {e}")

if __name__ == "__main__":
    main()
