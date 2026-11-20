"""
============================================================
  🎯 अंतिम प्रहार महाबैच - BATCH LAUNCH BOT
  - Group me Banner Photo + YES Enroll & Not Interested Buttons
  - Real-time MongoDB Saving
  - Instant Admin Private Notification on every Enrollment
  - Admin /inrolllist command for complete list
  - Admin /broadcast command for Launch & Purchase Notification
============================================================
"""

import os
import io
import asyncio
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

import config
from mongo_db import DatabaseManager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize MongoDB
db = DatabaseManager(mongo_uri=config.MONGO_URI, db_name=config.MONGO_DB_NAME)

# Path to Banner Image
BANNER_PATH = os.path.join(os.path.dirname(__file__), "banner.jpg")


def get_banner_caption():
    return (
        f"🔥 **{config.BATCH_NAME}** 🔥\n"
        f"**तैयारी आज की, जीत कल की !**\n\n"
        f"📚 **इन्हीं 3 किताबों से पूरी तैयारी:**\n"
        f"1️⃣ **Fatman** — Parmar SSC GK/GS Theory Book\n"
        f"2️⃣ **Rasgulla Book** — Current Affairs 2024-25 (कुमार गौरव सर)\n"
        f"3️⃣ **सुदर्शन चक्र** — GK/GS अति महत्वपूर्ण टॉपिक (कुमार गौरव सर)\n\n"
        f"✨ **तीन किताबों से टॉपिक-वाइज़ क्विज़, सीधे और सरल रूप में!**\n"
        f"📅 **शुरुआत:** {config.BATCH_START_DATE}\n"
        f"💰 **फीस:** सिर्फ़ ₹{config.BATCH_FEE}\n\n"
        f"👇 **क्या आप इस बैच में Enroll करना चाहते हैं?**"
    )

def get_enroll_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ YES Enroll Now", callback_data="btn_yes_enroll")],
        [InlineKeyboardButton("❌ Not Interested", callback_data="btn_not_interested")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ────────────────────────────────────────────────────────────
# 1. /start COMMAND
# ────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=get_banner_caption(),
                reply_markup=get_enroll_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            get_banner_caption(),
            reply_markup=get_enroll_keyboard(),
            parse_mode="Markdown"
        )


# ────────────────────────────────────────────────────────────
# 2. YES ENROLL BUTTON HANDLER (MongoDB + Admin Alert)
# ────────────────────────────────────────────────────────────

async def yes_enroll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    # 1. Save to MongoDB
    success, is_new, enrolled_time = db.enroll_student(
        user_id=user.id,
        full_name=user.full_name,
        username=user.username,
        batch_name=config.BATCH_NAME
    )

    if not success:
        await query.answer("❌ Error aaya. Kripya dobara prayas karein.", show_alert=True)
        return

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    if is_new:
        # Popup for Student with guidance to start the bot
        alert_msg = (
            f"🎉 बधाई हो {user.first_name}!\n\n"
            f"आपका अंतिम प्रहार महाबैच में Enrollment दर्ज हो गया है!\n\n"
            f"⚠️ बैच लॉन्च होते ही पेमेंट व परचेज लिंक सीधे इनबॉक्स में पाने के लिए @{bot_username} को एक बार Start जरूर कर लें!"
        )
        await query.answer(alert_msg, show_alert=True)
        logger.info(f"New Enrollment: {user.full_name} ({user.id})")

        # 2. Instant Private Notification to ADMIN
        admin_alert = (
            f"🔔 **NAYA BATCH ENROLLMENT!** 🔥\n\n"
            f"👤 **Student Name:** {user.full_name}\n"
            f"🏷️ **Username:** " + (f"@{user.username}" if user.username else "N/A") + "\n"
            f"🆔 **Telegram ID:** `{user.id}`\n"
            f"📚 **Batch:** {config.BATCH_NAME}\n"
            f"🕒 **Time:** `{enrolled_time}`\n"
            f"─────────────────────\n"
            f"✅ *Data MongoDB me successfully save ho gaya hai.*"
        )

        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=admin_alert,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")

    else:
        # Already enrolled popup
        await query.answer("ℹ️ आप पहले से ही अंतिम प्रहार महाबैच में Enroll हो चुके हैं!", show_alert=True)


# ────────────────────────────────────────────────────────────
# 3. NOT INTERESTED BUTTON HANDLER
# ────────────────────────────────────────────────────────────

async def not_interested_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("👍 कोई बात नहीं! आपकी आगामी परीक्षा और तैयारी के लिए All the Best!", show_alert=True)


# ────────────────────────────────────────────────────────────
# 4. ADMIN COMMAND: /sendpost (Group me Banner + Buttons bhejna)
# ────────────────────────────────────────────────────────────

async def send_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai!")
        return

    target_chat = config.GROUP_ID or update.effective_chat.id

    try:
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=target_chat,
                    photo=photo,
                    caption=get_banner_caption(),
                    reply_markup=get_enroll_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            await context.bot.send_message(
                chat_id=target_chat,
                text=get_banner_caption(),
                reply_markup=get_enroll_keyboard(),
                parse_mode="Markdown"
            )
        await update.message.reply_text(f"✅ अंतिम प्रहार महाबैच का पोस्ट Group ({target_chat}) mein bhej diya gaya hai!")
    except Exception as e:
        await update.message.reply_text(f"❌ Post bhejne mein error aaya: {e}")


# ────────────────────────────────────────────────────────────
# 5. ADMIN COMMAND: /inrolllist & /enrolllist
# ────────────────────────────────────────────────────────────

async def inroll_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai!")
        return

    students = db.get_enrolled_list()
    total = len(students)

    if total == 0:
        await update.message.reply_text(
            f"ℹ️ **{config.BATCH_NAME}** ke liye abhi tak koi enrollment nahi hua hai.",
            parse_mode="Markdown"
        )
        return

    header = f"📋 **{config.BATCH_NAME} - ENROLLED STUDENTS**\n👥 **Total Enrolled:** {total}\n"
    divider = "─" * 35 + "\n\n"

    lines = []
    for idx, s in enumerate(students, start=1):
        name = s.get('full_name', 'Unknown')
        uname = s.get('username', 'N/A')
        time_str = s.get('enrolled_at', '')
        lines.append(f"**{idx}.** {name} ({uname})\n   🕒 `{time_str}`")

    full_text = header + divider + "\n\n".join(lines)

    if len(full_text) < 4000:
        await update.message.reply_text(full_text, parse_mode="Markdown")
    else:
        summary_text = f"📋 **{config.BATCH_NAME} - ENROLLMENT LIST**\n👥 **Total Enrolled:** {total}\n\nPoori list text file mein attach ki gayi hai:"
        await update.message.reply_text(summary_text, parse_mode="Markdown")

        file_content = f"BATCH: {config.BATCH_NAME}\nTOTAL ENROLLED: {total}\n" + "="*50 + "\n\n"
        for idx, s in enumerate(students, start=1):
            file_content += f"{idx}. {s.get('full_name')} | Username: {s.get('username')} | ID: {s.get('user_id')} | Time: {s.get('enrolled_at')}\n"

        bio = io.BytesIO(file_content.encode('utf-8'))
        bio.name = "enrolled_students.txt"
        bio.seek(0)
        await update.message.reply_document(document=bio, caption=f"📄 Enrolled Students ({total})")


# ────────────────────────────────────────────────────────────
# 6. ADMIN COMMAND: /broadcast (Payment & Purchase Link to Enrolled)
# ────────────────────────────────────────────────────────────

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai!")
        return

    if not context.args:
        help_msg = (
            "⚠️ **Broadcast Message Format:**\n\n"
            "`/broadcast <Aapka Message/Payment Link>`\n\n"
            "**Example:**\n"
            "`/broadcast 🎉 अंतिम प्रहार महाबैच शुरू हो चुका है! अपना बैच परचेज करने के लिए यहाँ क्लिक करें: https://...`"
        )
        await update.message.reply_text(help_msg, parse_mode="Markdown")
        return

    message_to_send = " ".join(context.args)
    students = db.get_enrolled_list()

    if not students:
        await update.message.reply_text("ℹ️ MongoDB me abhi tak koi student enrolled nahi hai.")
        return

    status_msg = await update.message.reply_text(
        f"⏳ **Broadcasting to {len(students)} enrolled students...**\nKripya thoda intezaar karein."
    )

    success_count = 0
    fail_count = 0

    for s in students:
        target_uid = s.get("user_id")
        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text=message_to_send,
                parse_mode="Markdown"
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Could not send to {target_uid}: {e}")
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **Batch Launch Broadcast Complete!**\n\n"
        f"👥 Total Enrolled: {len(students)}\n"
        f"📨 Successfully Sent: {success_count}\n"
        f"❌ Failed (Bot Blocked/Inactive): {fail_count}",
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────────────────
# 7. MAIN FUNCTION
# ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 Starting Antim Prahar Maha Batch Bot...")
    print(f"📌 Admin ID: {config.ADMIN_ID}")
    print(f"📌 Batch: {config.BATCH_NAME} (₹{config.BATCH_FEE})")
    print("=" * 60)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(yes_enroll_handler, pattern="^btn_yes_enroll$"))
    app.add_handler(CallbackQueryHandler(not_interested_handler, pattern="^btn_not_interested$"))
    app.add_handler(CommandHandler("inrolllist", inroll_list_command))
    app.add_handler(CommandHandler("enrolllist", inroll_list_command))
    app.add_handler(CommandHandler("sendpost", send_post_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    print("✅ Bot is running! Waiting for group enrollments...")
    app.run_polling()

if __name__ == "__main__":
    main()
