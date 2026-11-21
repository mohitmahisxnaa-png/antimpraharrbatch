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
        self.groups_col = None
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
                self.groups_col = db["registered_groups"]
                
                # Compound index on user_id + batch_name so student can enroll in Batch 1 AND Batch 2
                # while preventing duplicate clicks on the same batch!
                try:
                    self.collection.drop_index("user_id_1")
                except Exception:
                    pass
                try:
                    self.collection.create_index([("user_id", 1), ("batch_name", 1)], unique=True)
                except Exception:
                    pass

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
                    user_id INTEGER,
                    full_name TEXT,
                    username TEXT,
                    enrolled_at TEXT,
                    batch_name TEXT,
                    status TEXT DEFAULT 'YES_ENROLLED',
                    PRIMARY KEY (user_id, batch_name)
                )
            """)
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    val TEXT
                )
            """)
            self.sqlite_conn.execute("""
                CREATE TABLE IF NOT EXISTS registered_groups (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    slot TEXT,
                    updated_at TEXT
                )
            """)
        self.is_mongo = False
        print("📁 Using Local Database (enrollments_backup.db).")

    # ────────────────────────────────────────────────────────────
    # 1. ENROLLMENT & UN-ENROLLMENT
    # ────────────────────────────────────────────────────────────

    def enroll_student(self, user_id, full_name, username, batch_name="अंतिम प्रहार महाबैच"):
        """
        Enrolls a student for a specific batch.
        If already enrolled in that batch, returns is_new = False.
        """
        enrolled_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")
        uname = f"@{username}" if username else "N/A"

        if self.is_mongo:
            try:
                res = self.collection.find_one({"user_id": user_id, "batch_name": batch_name})
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
                cur.execute("SELECT user_id, enrolled_at FROM enrolled_students WHERE user_id = ? AND batch_name = ?", (user_id, batch_name))
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

    def mark_not_interested(self, user_id, batch_name=None):
        """
        Student Not Interested click karta hai toh us batch ki list se hata deta hai.
        """
        success, _ = self.remove_student(user_id, batch_name=batch_name)
        return success

    def remove_student(self, identifier, batch_name=None):
        """
        Student ko remove karta hai taaki wo dobara enroll kar sake.
        Accepts: user_id (int or str), username (with or without @), or full_name regex.
        Returns: (success: bool, removed_student_dict or None)
        """
        search_str = str(identifier).strip()
        clean_uname = search_str.lstrip("@").strip()
        
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

        main_query = {"$or": or_conditions}
        if batch_name:
            main_query["batch_name"] = batch_name

        if self.is_mongo:
            try:
                found = self.collection.find_one(main_query)
                if not found:
                    return False, None
                
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
                if batch_name:
                    cur.execute("""
                        SELECT user_id, full_name, username, enrolled_at, batch_name 
                        FROM enrolled_students 
                        WHERE (user_id = ? OR username = ? OR username = ? OR full_name = ?)
                          AND batch_name = ?
                    """, (search_str, f"@{clean_uname}", clean_uname, search_str, batch_name))
                else:
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
                    if batch_name:
                        self.sqlite_conn.execute("DELETE FROM enrolled_students WHERE user_id = ? AND batch_name = ?", (found_dict["user_id"], batch_name))
                    else:
                        self.sqlite_conn.execute("DELETE FROM enrolled_students WHERE user_id = ?", (found_dict["user_id"],))
                return True, found_dict
            except Exception as e:
                print(f"Error removing from SQLite: {e}")
                return False, None

    def get_enrolled_list(self, batch_name=None):
        """Returns enrolled students list, optionally filtered by batch."""
        query = {"status": "YES_ENROLLED"}
        if batch_name:
            query["batch_name"] = batch_name

        if self.is_mongo:
            try:
                return list(self.collection.find(query, {"_id": 0}).sort("enrolled_at", 1))
            except Exception as e:
                print(f"Error fetching from MongoDB: {e}")
                return []
        else:
            try:
                cur = self.sqlite_conn.cursor()
                if batch_name:
                    cur.execute("SELECT user_id, full_name, username, enrolled_at, batch_name FROM enrolled_students WHERE status = 'YES_ENROLLED' AND batch_name = ? ORDER BY enrolled_at ASC", (batch_name,))
                else:
                    cur.execute("SELECT user_id, full_name, username, enrolled_at, batch_name FROM enrolled_students WHERE status = 'YES_ENROLLED' ORDER BY enrolled_at ASC")
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                print(f"Error fetching from SQLite: {e}")
                return []

    # ────────────────────────────────────────────────────────────
    # 2. GROUP MANAGEMENT (Group 1 & Group 2)
    # ────────────────────────────────────────────────────────────

    def save_group(self, chat_id, title=None, slot=None):
        """
        Saves or updates group info.
        slot: 'group_1' or 'group_2'
        """
        chat_id = int(chat_id)
        now_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
        title = title or f"Group ({chat_id})"

        if self.is_mongo:
            try:
                doc = {
                    "chat_id": chat_id,
                    "title": title,
                    "updated_at": now_time
                }
                if slot:
                    doc["slot"] = slot
                    self.settings_col.update_one({"key": f"slot_{slot}"}, {"$set": {"val": str(chat_id)}}, upsert=True)

                self.groups_col.update_one({"chat_id": chat_id}, {"$set": doc}, upsert=True)
                return True
            except Exception as e:
                print(f"Error saving group in MongoDB: {e}")
                return False
        else:
            try:
                with self.sqlite_conn:
                    self.sqlite_conn.execute("""
                        INSERT OR REPLACE INTO registered_groups (chat_id, title, slot, updated_at)
                        VALUES (?, ?, ?, ?)
                    """, (chat_id, title, slot or "", now_time))
                    if slot:
                        self.sqlite_conn.execute("INSERT OR REPLACE INTO bot_settings (key, val) VALUES (?, ?)", (f"slot_{slot}", str(chat_id)))
                return True
            except Exception as e:
                print(f"Error saving group in SQLite: {e}")
                return False

    def get_registered_groups(self, default_g1=None, default_g2=None):
        """
        Returns structured groups dictionary:
        {
            "group_1": {"chat_id": int, "title": str},
            "group_2": {"chat_id": int, "title": str}
        }
        """
        g1_id = None
        g2_id = None

        if self.is_mongo:
            try:
                d1 = self.settings_col.find_one({"key": "slot_group_1"})
                if d1 and d1.get("val"):
                    g1_id = int(d1["val"])
                d2 = self.settings_col.find_one({"key": "slot_group_2"})
                if d2 and d2.get("val"):
                    g2_id = int(d2["val"])
            except Exception:
                pass
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT val FROM bot_settings WHERE key = 'slot_group_1'")
                r1 = cur.fetchone()
                if r1: g1_id = int(r1["val"])
                cur.execute("SELECT val FROM bot_settings WHERE key = 'slot_group_2'")
                r2 = cur.fetchone()
                if r2: g2_id = int(r2["val"])
            except Exception:
                pass

        if not g1_id and default_g1:
            try: g1_id = int(default_g1)
            except Exception: pass

        if not g2_id and default_g2:
            try: g2_id = int(default_g2)
            except Exception: pass

        result = {}

        for key, gid, default_label in [("group_1", g1_id, "Group 1 (Main Study Group)"), ("group_2", g2_id, "Group 2")]:
            if gid:
                title = default_label
                if self.is_mongo:
                    gdoc = self.groups_col.find_one({"chat_id": gid})
                    if gdoc and gdoc.get("title"):
                        title = gdoc["title"]
                else:
                    cur = self.sqlite_conn.cursor()
                    cur.execute("SELECT title FROM registered_groups WHERE chat_id = ?", (gid,))
                    grow = cur.fetchone()
                    if grow and grow["title"]:
                        title = grow["title"]
                result[key] = {"chat_id": gid, "title": title}
            else:
                result[key] = None

        return result

    # ────────────────────────────────────────────────────────────
    # 3. GROUP POST TRACKING (Delete/Clean)
    # ────────────────────────────────────────────────────────────

    def save_post_id(self, message_id, chat_id=None):
        if self.is_mongo:
            try:
                if chat_id:
                    self.settings_col.update_one({"key": f"group_post_id_{chat_id}"}, {"$set": {"val": str(message_id)}}, upsert=True)
                self.settings_col.update_one({"key": "group_post_id"}, {"$set": {"val": str(message_id)}}, upsert=True)
            except Exception:
                pass
        else:
            try:
                with self.sqlite_conn:
                    if chat_id:
                        self.sqlite_conn.execute("INSERT OR REPLACE INTO bot_settings (key, val) VALUES (?, ?)", (f"group_post_id_{chat_id}", str(message_id)))
                    self.sqlite_conn.execute("INSERT OR REPLACE INTO bot_settings (key, val) VALUES ('group_post_id', ?)", (str(message_id),))
            except Exception:
                pass

    def get_post_id(self, chat_id=None):
        if self.is_mongo:
            try:
                if chat_id:
                    doc = self.settings_col.find_one({"key": f"group_post_id_{chat_id}"})
                    if doc:
                        return int(doc["val"])
                doc = self.settings_col.find_one({"key": "group_post_id"})
                return int(doc["val"]) if doc else None
            except Exception:
                return None
        else:
            try:
                cur = self.sqlite_conn.cursor()
                if chat_id:
                    cur.execute("SELECT val FROM bot_settings WHERE key = ?", (f"group_post_id_{chat_id}",))
                    row = cur.fetchone()
                    if row:
                        return int(row["val"])
                cur.execute("SELECT val FROM bot_settings WHERE key = 'group_post_id'")
                row = cur.fetchone()
                return int(row["val"]) if row else None
            except Exception:
                return None

    def clear_post_id(self, chat_id=None):
        if self.is_mongo:
            try:
                if chat_id:
                    self.settings_col.delete_one({"key": f"group_post_id_{chat_id}"})
                self.settings_col.delete_one({"key": "group_post_id"})
            except Exception:
                pass
        else:
            try:
                with self.sqlite_conn:
                    if chat_id:
                        self.sqlite_conn.execute("DELETE FROM bot_settings WHERE key = ?", (f"group_post_id_{chat_id}",))
                    self.sqlite_conn.execute("DELETE FROM bot_settings WHERE key = 'group_post_id'")
            except Exception:
                pass

    # ────────────────────────────────────────────────────────────
    # 4. CUSTOM BANNER STORAGE (No Code Needed)
    # ────────────────────────────────────────────────────────────

    def save_banner_file_id(self, file_id):
        if self.is_mongo:
            try:
                self.settings_col.update_one({"key": "custom_banner_file_id"}, {"$set": {"val": str(file_id)}}, upsert=True)
                return True
            except Exception as e:
                print(f"Error saving banner file_id: {e}")
                return False
        else:
            try:
                with self.sqlite_conn:
                    self.sqlite_conn.execute("INSERT OR REPLACE INTO bot_settings (key, val) VALUES ('custom_banner_file_id', ?)", (str(file_id),))
                return True
            except Exception:
                return False

    def get_banner_file_id(self):
        if self.is_mongo:
            try:
                doc = self.settings_col.find_one({"key": "custom_banner_file_id"})
                return doc["val"] if doc else None
            except Exception:
                return None
        else:
            try:
                cur = self.sqlite_conn.cursor()
                cur.execute("SELECT val FROM bot_settings WHERE key = 'custom_banner_file_id'")
                row = cur.fetchone()
                return row["val"] if row else None
            except Exception:
                return None
