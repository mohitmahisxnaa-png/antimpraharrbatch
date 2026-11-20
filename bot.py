"""
============================================================
  🎯 1st DECEMBER BATCH ENROLLMENT BOT (MONGODB INTEGRATED)
  - Members click 'Enroll Now' button
  - Details automatically saved in MongoDB
  - Admin gets full list via /inrolllist command
============================================================
"""

import io
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

# MongoDB instance
db = DatabaseManager(mongo_uri=config.MONGO_URI, db_name=config.MONGO_DB_NAME)


def get_enroll_post_text():
    return (
        f"🔥 **SPECIAL ANNOUNCEMENT: NEW BATCH LAUNCH!** 🔥\n\n"
        f"🎯 **Target Batch:** {config.BATCH_NAME}\n"
        f"📅 **Start Date:** {config.BATCH_START_DATE}\n\n"
        f"Aap sabhi ki demand par **{config.BATCH_START_DATE}** se special preparation batch shuru hone ja raha hai! 🚀\n\n"
        f"✨ **Batch Features:**\n"
        f"✅ Daily Important Notes & Revision PDFs\n"
        f"✅ Topic-wise Practice Quizzes & Solutions\n"
        f"✅ Group Discussion & Doubt Solving Support\n"
        f"✅ Targeted Guidance for Exam Success\n\n"
        f"👉 **Is batch mein enroll karne ke liye niche diye gaye button par click karein:**"
    )

def get_enroll_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Enroll Now / इनरोल करें", callback_data="btn_enroll")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Namaste **{user.first_name}**!\n\n"
        f"{get_enroll_post_text()}"
    )
    await update.message.reply_text(
        text,
        reply_markup=get_enroll_keyboard(),
        parse_mode="Markdown"
    )


# Jab koi Enroll button dabaye -> MongoDB me save
async def enroll_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    success, is_new = db.enroll_student(
        user_id=user.id,
        full_name=user.full_name,
        username=user.username,
        batch_name=config.BATCH_NAME
    )

    if not success:
        await query.answer("❌ Error aaya. Kripya dobara prayas karein.", show_alert=True)
        return

    if is_new:
        alert_msg = f"🎉 Mubarak ho {user.first_name}! Aapka 1st December Batch me enrollment confirm ho gaya hai!"
        await query.answer(alert_msg, show_alert=True)
        logger.info(f"New enrollment: {user.full_name} ({user.id})")
        
        if query.message.chat.type == "private":
            await query.message.reply_text(
                f"✅ **Aapka Enrollment Confirm Ho Chuka Hai!**\n\n"
                f"👤 Name: **{user.full_name}**\n"
                f"📅 Batch: **{config.BATCH_NAME}**\n"
                f"🚀 Start Date: **{config.BATCH_START_DATE}**\n\n"
                f"Jald hi aapko batch group link aur update mil jayega! 👍",
                parse_mode="Markdown"
            )
    else:
        await query.answer("ℹ️ Aap pehle se hi is batch mein Enroll ho chuke hain!", show_alert=True)


# Admin command: /inrolllist ya /enrolllist
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

    header = f"📋 **{config.BATCH_NAME} - ENROLLMENT LIST**\n👥 **Total Students:** {total}\n"
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
        summary_text = f"📋 **{config.BATCH_NAME} - ENROLLMENT LIST**\n👥 **Total Enrolled:** {total}\n\nPoori list text file mein attach kar di gayi hai:"
        await update.message.reply_text(summary_text, parse_mode="Markdown")

        file_content = f"BATCH: {config.BATCH_NAME}\nTOTAL ENROLLED: {total}\n" + "="*50 + "\n\n"
        for idx, s in enumerate(students, start=1):
            file_content += f"{idx}. {s.get('full_name')} | Username: {s.get('username')} | ID: {s.get('user_id')} | Time: {s.get('enrolled_at')}\n"

        bio = io.BytesIO(file_content.encode('utf-8'))
        bio.name = "enrolled_students.txt"
        bio.seek(0)
        await update.message.reply_document(document=bio, caption=f"📄 Enrolled Students ({total})")


# Admin command: Group me post bhejne ke liye /sendpost
async def send_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai!")
        return

    target_chat = config.GROUP_ID or update.effective_chat.id

    try:
        await context.bot.send_message(
            chat_id=target_chat,
            text=get_enroll_post_text(),
            reply_markup=get_enroll_keyboard(),
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Enrollment Post group ({target_chat}) mein bhej di gayi hai!")
    except Exception as e:
        await update.message.reply_text(f"❌ Post bhejne mein error aaya: {e}")


def main():
    print("=" * 60)
    print("🚀 Starting Batch Enrollment Bot...")
    print(f"📌 Admin ID: {config.ADMIN_ID}")
    print("=" * 60)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(enroll_button_handler, pattern="^btn_enroll$"))
    app.add_handler(CommandHandler("inrolllist", inroll_list_command))
    app.add_handler(CommandHandler("enrolllist", inroll_list_command))
    app.add_handler(CommandHandler("sendpost", send_post_command))

    print("✅ Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
