import os

# ============================================================
#  🎯 अंतिम प्रहार महाबैच - CONFIGURATION
# ============================================================

# 1. Telegram Bot Token (@BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8944237255:AAE3SqXZyukH-HpazVhkMJryIFD2BJK6zTM")

# 2. Admin Telegram User ID (Notification & List dekhne ke liye)
ADMIN_ID = int(os.getenv("ADMIN_ID", "6416451659"))

# 3. Batch Details (Flexible Start Date)
BATCH_NAME = os.getenv("BATCH_NAME", "अंतिम प्रहार महाबैच")
BATCH_START_DATE = os.getenv("BATCH_START_DATE", "जल्द ही (Coming Soon)")
BATCH_FEE = 99  # ₹99

# 4. Group Chat ID (Jahan photo aur buttons bhejni hain)
GROUP_ID = os.getenv("GROUP_ID", "-1003493006883")

# 5. MongoDB Atlas Connection URI
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://mohitmahisxnaa_db_user:DiuHqbtjQPA5HoUc@cluster0.shdzjh4.mongodb.net/?retryWrites=true&w=majority"
)
MONGO_DB_NAME = "antim_prahar_batch"
