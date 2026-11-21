import os

# ============================================================
#  🎯 अंतिम प्रहार महाबैच & करेंट अफेयर्स - CONFIGURATION
# ============================================================

# 1. Telegram Bot Token (@BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8944237255:AAE3SqXZyukH-HpazVhkMJryIFD2BJK6zTM")

# 2. Admin Telegram User ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "6416451659"))

# 3. Batch 1 Details (अंतिम प्रहार महाबैच)
BATCH_1_NAME = os.getenv("BATCH_NAME", "अंतिम प्रहार महाबैच")
BATCH_1_FEE = 99
BATCH_NAME = BATCH_1_NAME  # Backward compatibility
BATCH_FEE = BATCH_1_FEE

# 4. Batch 2 Details (करेंट अफेयर्स स्पेशल बैच)
BATCH_2_NAME = os.getenv("BATCH_2_NAME", "करेंट अफेयर्स स्पेशल बैच")
BATCH_2_FEE = 49

# 5. Group Chat IDs
# Group 1: Primary Study Group
GROUP_1_ID = os.getenv("GROUP_ID", "-1003493006883")
GROUP_ID = GROUP_1_ID  # Backward compatibility

# Group 2: Second Group (Can be set via env or from Telegram /setgroup2)
GROUP_2_ID = os.getenv("GROUP_2_ID", "")

# 6. MongoDB Atlas Connection URI
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://mohitmahisxnaa_db_user:DiuHqbtjQPA5HoUc@cluster0.shdzjh4.mongodb.net/?retryWrites=true&w=majority"
)
MONGO_DB_NAME = "antim_prahar_batch"
