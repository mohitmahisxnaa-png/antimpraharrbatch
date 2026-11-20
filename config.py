import os

# ============================================================
#  🎯 1st DECEMBER BATCH ENROLLMENT BOT CONFIG
# ============================================================

# 1. Telegram Bot Token (@BotFather se)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8944237255:AAE3SqXZyukH-HpazVhkMJryIFD2BJK6zTM")

# 2. Admin Telegram User ID (Sirf aap /inrolllist dekh sakenge)
ADMIN_ID = int(os.getenv("ADMIN_ID", "6416451659"))

# 3. Batch Details
BATCH_NAME = os.getenv("BATCH_NAME", "1st December Special Study Batch")
BATCH_START_DATE = os.getenv("BATCH_START_DATE", "1 December 2026")

# 4. Group Chat ID (Jahan post bhejni hai)
GROUP_ID = os.getenv("GROUP_ID", "-1003493006883")

# 5. MongoDB Atlas Connection URI
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = "antim_prahar_batch"
