import os
import certifi
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

# IST Timezone (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

class DatabaseManager:
    def __init__(self, mongo_uri=None, db_name="antim_prahar_batch"):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client = None
        self.collection = None
        self.settings_col = None
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
                self.settings_col = db["bot_settings"]
                # Duplicate entry rokne ke liye unique index
                self.collection.create_index("user_id", unique=True)
                self.is_mongo = True
                print("✅ Connected to MongoDB Atlas successfully!")
                return
            except Exception as e:
                print(f"⚠️ MongoDB connection failed: {e}. Falling back to SQLite.")

        # Fallback to local SQLite if MongoDB is offline
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
                    batch_name TEXT,
                    status TEXT DEFAULT 'YES_ENROLLED'
                )
            """)
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    val TEXT
                )
            """)
        self.is_mongo = False
        print("📁 Using Local Database (enrollments_backup.db).")

    def enroll_student(self, user_id, full_name, username, batch_name="अंतिम प्रहार महाबैच"):
        """
        Enrolls a student with YES.
        Agar pehle se enrolled hai toh duplicate entry nahi karega (is_new = False).
        """
        enrolled_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
        uname = f"@{username}" if username else "N/A"

        if self.is_mongo:
            try:
                res = self.collection.find_one({"user_id": user_id})
                if res:
                    return True, False, res.get("enrolled_at", enrolled_time)
                
                self.collection.insert_one({
                    "user_id": user_id,
                    "full_name": full_name or "Unknown",
                    "username": uname,
                    "enrolled_at": enrolled_time,
                    "batch_name": batch_name,
                    "status": "YES_ENROLLED"
                })
                return True, True, enrolled_time
            except Exception as e:
                print(f"Error enrolling in MongoDB: {e}")
                return False, False, ""
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT user_id, enrolled_at FROM enrolled_students WHERE user_id = ?", (user_id,))
                row = cur.fetchone()
                if row:
                    return True, False, row["enrolled_at"]
                
                with self.sqlite_conn:
                    self.sqlite_conn.execute("""
                        INSERT INTO enrolled_students (user_id, full_name, username, enrolled_at, batch_name, status)
                        VALUES (?, ?, ?, ?, ?, 'YES_ENROLLED')
                    """, (user_id, full_name or "Unknown", uname, enrolled_time, batch_name))
                return True, True, enrolled_time
            except Exception as e:
                print(f"Error enrolling in SQLite: {e}")
                return False, False, ""

    def remove_student(self, identifier):
        """
        Student ko remove karta hai taaki wo dobara enroll kar sake.
        Accepts: user_id (int or str), username (with or without @), or full_name regex.
        Returns: (success: bool, removed_student_dict or None)
        """
        search_str = str(identifier).strip()
        clean_uname = search_str.lstrip("@").strip()
        
        # Build flexible query
        or_conditions = [
            {"username": f"@{clean_uname}"},
            {"username": clean_uname},
            {"full_name": {"$regex": f"^{search_str}$", "$options": "i"}}
        ]
        
        if search_str.isdigit():
            or_conditions.append({"user_id": int(search_str)})
            or_conditions.append({"user_id": search_str})
        elif isinstance(identifier, int):
            or_conditions.append({"user_id": identifier})
            or_conditions.append({"user_id": str(identifier)})

        if self.is_mongo:
            try:
                # Pehle student record dhoondo taaki pata chale kaun tha
                found = self.collection.find_one({"$or": or_conditions})
                if not found:
                    return False, None
                
                # Delete using exact _id
                res = self.collection.delete_one({"_id": found["_id"]})
                if res.deleted_count > 0:
                    return True, found
                return False, None
            except Exception as e:
                print(f"Error removing from MongoDB: {e}")
                return False, None
        else:
            try:
                cur = self.sqlite_conn.cursor()
                # Check by user_id or username or full_name
                cur.execute("""
                    SELECT user_id, full_name, username, enrolled_at, batch_name 
                    FROM enrolled_students 
                    WHERE user_id = ? OR username = ? OR username = ? OR full_name = ?
                """, (search_str, f"@{clean_uname}", clean_uname, search_str))
                row = cur.fetchone()
                if not row:
                    return False, None
                
                found_dict = dict(row)
                with self.sqlite_conn:
                    self.sqlite_conn.execute("DELETE FROM enrolled_students WHERE user_id = ?", (found_dict["user_id"],))
                return True, found_dict
            except Exception as e:
                print(f"Error removing from SQLite: {e}")
                return False, None

    def save_post_id(self, message_id):
        """Group post message id save karta hai taaki baad me delete kar sakein"""
        if self.is_mongo:
            try:
                self.settings_col.update_one({"key": "group_post_id"}, {"$set": {"val": str(message_id)}}, upsert=True)
            except Exception:
                pass
        else:
            try:
                with self.sqlite_conn:
                    self.sqlite_conn.execute("INSERT OR REPLACE INTO bot_settings (key, val) VALUES ('group_post_id', ?)", (str(message_id),))
            except Exception:
                pass

    def get_post_id(self):
        if self.is_mongo:
            try:
                doc = self.settings_col.find_one({"key": "group_post_id"})
                return int(doc["val"]) if doc else None
            except Exception:
                return None
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT val FROM bot_settings WHERE key = 'group_post_id'")
                row = cur.fetchone()
                return int(row["val"]) if row else None
            except Exception:
                return None

    def clear_post_id(self):
        if self.is_mongo:
            try:
                self.settings_col.delete_one({"key": "group_post_id"})
            except Exception:
                pass
        else:
            try:
                with self.sqlite_conn:
                    self.sqlite_conn.execute("DELETE FROM bot_settings WHERE key = 'group_post_id'")
            except Exception:
                pass

    def get_enrolled_list(self):
        if self.is_mongo:
            try:
                return list(self.collection.find({"status": "YES_ENROLLED"}, {"_id": 0}).sort("enrolled_at", 1))
            except Exception as e:
                print(f"Error fetching from MongoDB: {e}")
                return []
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT user_id, full_name, username, enrolled_at, batch_name FROM enrolled_students WHERE status = 'YES_ENROLLED'")
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                print(f"Error fetching from SQLite: {e}")
                return []
