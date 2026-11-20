import os
import certifi
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

# IST Timezone (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

class DatabaseManager:
    def __init__(self, mongo_uri=None, db_name="batch_enrollments"):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client = None
        self.collection = None
        self.is_mongo = False
        
        self._connect()

    def _connect(self):
        if self.mongo_uri and self.mongo_uri.startswith("mongodb"):
            try:
                self.client = MongoClient(
                    self.mongo_uri,
                    tlsCAFile=certifi.where(),
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000
                )
                self.client.admin.command('ping')
                db = self.client[self.db_name]
                self.collection = db["enrolled_students"]
                self.collection.create_index("user_id", unique=True)
                self.is_mongo = True
                print("✅ Connected to MongoDB Atlas successfully!")
                return
            except Exception as e:
                print(f"⚠️ MongoDB connection failed: {e}. Falling back to SQLite.")

        # Fallback to local SQLite if MongoDB is offline/not given
        import sqlite3
        db_file = os.path.join(os.path.dirname(__file__), "enrollments_backup.db")
        self.sqlite_conn = sqlite3.connect(db_file, check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row
        with self.sqlite_conn:
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS enrolled_students (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    enrolled_at TEXT,
                    batch_name TEXT
                )
            """)
        self.is_mongo = False
        print("📁 Using Local Database (enrollments_backup.db).")

    def enroll_student(self, user_id, full_name, username, batch_name="1st December Batch"):
        enrolled_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
        uname = f"@{username}" if username else "N/A"

        if self.is_mongo:
            try:
                res = self.collection.find_one({"user_id": user_id})
                if res:
                    return True, False  # Pehle se enrolled hai
                self.collection.insert_one({
                    "user_id": user_id,
                    "full_name": full_name or "Unknown",
                    "username": uname,
                    "enrolled_at": enrolled_time,
                    "batch_name": batch_name
                })
                return True, True  # Naya enrollment
            except Exception as e:
                print(f"Error enrolling in MongoDB: {e}")
                return False, False
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT user_id FROM enrolled_students WHERE user_id = ?", (user_id,))
                if cur.fetchone():
                    return True, False
                with self.sqlite_conn:
                    self.sqlite_conn.execute("""
                        INSERT INTO enrolled_students (user_id, full_name, username, enrolled_at, batch_name)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, full_name or "Unknown", uname, enrolled_time, batch_name))
                return True, True
            except Exception as e:
                print(f"Error enrolling in SQLite: {e}")
                return False, False

    def get_enrolled_list(self):
        if self.is_mongo:
            try:
                return list(self.collection.find({}, {"_id": 0}).sort("enrolled_at", 1))
            except Exception as e:
                print(f"Error fetching from MongoDB: {e}")
                return []
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT user_id, full_name, username, enrolled_at, batch_name FROM enrolled_students")
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                print(f"Error fetching from SQLite: {e}")
                return []
