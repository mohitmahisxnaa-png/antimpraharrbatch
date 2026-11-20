"""
============================================================
  🎯 अंतिम प्रहार महाबैच - 100% BUTTON-DRIVEN BOT
  - Admin Panel with 1-Click Interactive Buttons
  - Group Post [Lagayein] & [Hatayein / Remove Post] Buttons
  - Student [Remove / Un-enroll] feature so they can enroll again
  - Real-time MongoDB Saving (No Data Loss & Duplicate Lock)
  - Instant Admin Private Alerts
  - 1-Click List & Broadcast Buttons
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
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
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

# States for admin input
WAITING_FOR_BROADCAST = set()
WAITING_FOR_REMOVE_STUDENT = set()


# ────────────────────────────────────────────────────────────
# 1. CAPTIONS & KEYBOARDS
# ────────────────────────────────────────────────────────────

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

def get_group_enroll_keyboard():
    """Group me dikhne wale buttons"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES Enroll Now", callback_data="btn_yes_enroll")],
        [InlineKeyboardButton("❌ Not Interested", callback_data="btn_not_interested")]
    ])

def get_admin_dashboard_keyboard():
    """Admin ke liye 1-Click Control Buttons"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Group me Post Lagayein", callback_data="adm_sendpost"),
            InlineKeyboardButton("🗑️ Group se Post Hatayein", callback_data="adm_deletepost")
        ],
        [
            InlineKeyboardButton("📋 Enrolled Students List", callback_data="adm_list"),
            InlineKeyboardButton("📊 Total Stats", callback_data="adm_stats")
        ],
        [
            InlineKeyboardButton("❌ Student Remove Karein", callback_data="adm_ask_remove"),
            InlineKeyboardButton("📨 Payment Link Bhejein", callback_data="adm_ask_broadcast")
        ],
        [InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="adm_refresh")]
    ])

def get_student_dm_keyboard():
    """Student jab bot ko DM me kholega"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 YES Enroll Now", callback_data="btn_yes_enroll")],
        [InlineKeyboardButton("📖 Batch Details", callback_data="btn_batch_info")],
        [InlineKeyboardButton("📞 Support / Contact", callback_data="btn_support")]
    ])


# ────────────────────────────────────────────────────────────
# 2. /start & /admin COMMAND
# ────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # AGAR ADMIN HAI -> Admin Dashboard with Buttons
    if user.id == config.ADMIN_ID and chat.type == "private":
        students = db.get_enrolled_list()
        admin_text = (
            f"👑 **ADMIN CONTROL PANEL**\n"
            f"🎯 Batch: **{config.BATCH_NAME}**\n\n"
            f"👥 **Total Enrolled Students:** `{len(students)}`\n"
            f"💰 **Batch Fee:** `₹{config.BATCH_FEE}`\n\n"
            f"Niche diye gaye **Buttons** se poora bot control karein 👇"
        )
        await update.message.reply_text(
            admin_text,
            reply_markup=get_admin_dashboard_keyboard(),
            parse_mode="Markdown"
        )
        return

    # AGAR GROUP HAI YA STUDENT HAI
    if os.path.exists(BANNER_PATH):
        with open(BANNER_PATH, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=get_banner_caption(),
                reply_markup=get_group_enroll_keyboard() if chat.type != "private" else get_student_dm_keyboard(),
                parse_mode="Markdown"
            )
    else:
        await update.message.reply_text(
            get_banner_caption(),
            reply_markup=get_group_enroll_keyboard() if chat.type != "private" else get_student_dm_keyboard(),
            parse_mode="Markdown"
        )


# ────────────────────────────────────────────────────────────
# 3. YES ENROLL & NOT INTERESTED BUTTONS
# ────────────────────────────────────────────────────────────

async def yes_enroll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    # 1. Save to MongoDB (No Duplicate, No Data Loss)
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
        alert_msg = (
            f"🎉 बधाई हो {user.first_name}!\n\n"
            f"आपका अंतिम प्रहार महाबैच में Enrollment दर्ज हो गया है!\n\n"
            f"⚠️ बैच लॉन्च होते ही पेमेंट व परचेज लिंक सीधे इनबॉक्स में पाने के लिए @{bot_username} को एक बार Start जरूर कर लें!"
        )
        await query.answer(alert_msg, show_alert=True)
        logger.info(f"New Enrollment: {user.full_name} ({user.id})")

        # 2. Instant Private Alert to ADMIN
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
        # Purane member ke dobara click karne par alert
        await query.answer("ℹ️ आप पहले से ही अंतिम प्रहार महाबैच में Enroll हो चुके हैं!", show_alert=True)


async def not_interested_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("👍 कोई बात नहीं! आपकी आगामी परीक्षा और तैयारी के लिए All the Best!", show_alert=True)


async def batch_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    info_text = (
        f"📖 **{config.BATCH_NAME} - Complete Information**\n\n"
        f"🔹 **3 Books Coverage:** Parmar SSC Fatman + Rasgulla Book (Kumar Gaurav Sir) + Sudarshan Chakra\n"
        f"🔹 **Daily Practice:** Topic-wise quizes directly based on these books\n"
        f"🔹 **Target:** High Score in General Studies & Current Affairs\n"
        f"💰 **Fee:** ₹{config.BATCH_FEE}\n\n"
        f"Enroll karne ke liye niche button dabayein 👇"
    )
    await query.edit_message_caption(
        caption=info_text,
        reply_markup=get_student_dm_keyboard(),
        parse_mode="Markdown"
    )


async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"📞 **Help & Support**\n\n"
        f"Kisi bhi query ya help ke liye aap Admin se contact kar sakte hain:\n"
        f"Admin ID: `{config.ADMIN_ID}`"
    )
    await query.edit_message_caption(
        caption=text,
        reply_markup=get_student_dm_keyboard(),
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────────────────
# 4. ADMIN BUTTON HANDLERS (Post Lagayein, Hatayein, Remove Student)
# ────────────────────────────────────────────────────────────

# 1. Post Lagayein
async def admin_sendpost_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📢 Group me post bheji ja rahi hai...")

    target_chat = config.GROUP_ID
    try:
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, "rb") as photo:
                sent_msg = await context.bot.send_photo(
                    chat_id=target_chat,
                    photo=photo,
                    caption=get_banner_caption(),
                    reply_markup=get_group_enroll_keyboard(),
                    parse_mode="Markdown"
                )
        else:
            sent_msg = await context.bot.send_message(
                chat_id=target_chat,
                text=get_banner_caption(),
                reply_markup=get_group_enroll_keyboard(),
                parse_mode="Markdown"
            )
        
        # Save post ID so it can be deleted later
        db.save_post_id(sent_msg.message_id)
        await query.message.reply_text(
            f"✅ **Success!** अंतिम प्रहार महाबैच पोस्ट Group ({target_chat}) mein lag gayi hai!\n\n"
            f"Jab bhi hatani ho, aap **'🗑️ Group se Post Hatayein'** button daba sakte hain."
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Post lagane mein error aaya: {e}")


# 2. Post Hatayein / Delete Karein
async def admin_deletepost_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🗑️ Post hatayi ja rahi hai...")

    post_id = db.get_post_id()
    if not post_id:
        await query.message.reply_text("ℹ️ Group mein abhi koi active enrollment post nahi mili.")
        return

    try:
        await context.bot.delete_message(chat_id=config.GROUP_ID, message_id=post_id)
        db.clear_post_id()
        await query.message.reply_text(
            "✅ **Post Successfully Removed!**\n\n"
            "Group se enrollment post hata di gayi hai. "
            "Jab dobara lagani ho toh **'📢 Group me Post Lagayein'** button daba dein!"
        )
    except Exception as e:
        db.clear_post_id()
        await query.message.reply_text(f"⚠️ Post delete karne mein dikkat aayi (ho sakta hai pehle hi manually delete ho gayi ho): {e}")


# 3. Student List Dekhein
async def admin_list_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    students = db.get_enrolled_list()
    total = len(students)

    if total == 0:
        await query.message.reply_text(f"ℹ️ **{config.BATCH_NAME}** ke liye abhi tak koi enrollment nahi hua hai.")
        return

    header = f"📋 **{config.BATCH_NAME} - ENROLLED STUDENTS**\n👥 **Total Enrolled:** {total}\n"
    divider = "─" * 35 + "\n\n"

    lines = []
    for idx, s in enumerate(students, start=1):
        name = s.get('full_name', 'Unknown')
        uname = s.get('username', 'N/A')
        uid = s.get('user_id', '')
        time_str = s.get('enrolled_at', '')
        lines.append(f"**{idx}.** {name} ({uname})\n   🆔 `{uid}` | 🕒 `{time_str}`")

    full_text = header + divider + "\n\n".join(lines)

    if len(full_text) < 4000:
        await query.message.reply_text(full_text, parse_mode="Markdown")
    else:
        summary_text = f"📋 **{config.BATCH_NAME} - ENROLLMENT LIST**\n👥 **Total Enrolled:** {total}\n\nList text file mein attach ki gayi hai:"
        await query.message.reply_text(summary_text, parse_mode="Markdown")

        file_content = f"BATCH: {config.BATCH_NAME}\nTOTAL ENROLLED: {total}\n" + "="*50 + "\n\n"
        for idx, s in enumerate(students, start=1):
            file_content += f"{idx}. {s.get('full_name')} | Username: {s.get('username')} | ID: {s.get('user_id')} | Time: {s.get('enrolled_at')}\n"

        bio = io.BytesIO(file_content.encode('utf-8'))
        bio.name = "enrolled_students.txt"
        bio.seek(0)
        await update.message.reply_document(document=bio, caption=f"📄 Enrolled Students ({total})")


# 4. Total Stats
async def admin_stats_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    students = db.get_enrolled_list()
    total = len(students)
    await query.answer(f"📊 Total Enrolled: {total} Students", show_alert=True)


# 5. Student Remove / Un-enroll flow
async def admin_ask_remove_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_REMOVE_STUDENT.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_remove")]])

    await query.message.reply_text(
        "❌ **Kis Student ko Remove karna chahte hain?**\n\n"
        "Us student ka **Telegram User ID** yahan type karke bhejein.\n"
        "*(User ID aapko '📋 Enrolled Students List' mein mil jayegi)*\n\n"
        "Remove karne ke baad wo student **dobara enroll kar sakega**!",
        reply_markup=cancel_btn,
        parse_mode="Markdown"
    )


async def admin_cancel_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    WAITING_FOR_REMOVE_STUDENT.discard(query.from_user.id)
    await query.edit_message_text("❌ Remove cancel kar diya gaya.")


# 6. Broadcast flow
async def admin_ask_broadcast_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_BROADCAST.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_broadcast")]])

    await query.message.reply_text(
        "📝 **Aap sabhi Enrolled Students ko kya message ya payment link bhejna chahte hain?**\n\n"
        "Apna poora message yahan type karke send kar dein. (Bot use sabhi ke inbox me deliver kar dega!)\n\n"
        "Agar abhi nahi bhejna toh niche Cancel dabayein:",
        reply_markup=cancel_btn,
        parse_mode="Markdown"
    )


async def admin_cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    WAITING_FOR_BROADCAST.discard(query.from_user.id)
    await query.edit_message_text("❌ Broadcast cancel kar diya gaya.")


# 7. Refresh
async def admin_refresh_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Refreshing...")

    students = db.get_enrolled_list()
    admin_text = (
        f"👑 **ADMIN CONTROL PANEL**\n"
        f"🎯 Batch: **{config.BATCH_NAME}**\n\n"
        f"👥 **Total Enrolled Students:** `{len(students)}`\n"
        f"💰 **Batch Fee:** `₹{config.BATCH_FEE}`\n\n"
        f"Niche diye gaye **Buttons** se poora bot control karein 👇"
    )
    await query.edit_message_text(
        admin_text,
        reply_markup=get_admin_dashboard_keyboard(),
        parse_mode="Markdown"
    )


# ────────────────────────────────────────────────────────────
# 5. TEXT HANDLER (Broadcast Message & Student Remove ID)
# ────────────────────────────────────────────────────────────

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1. Handling Student Removal
    if user_id in WAITING_FOR_REMOVE_STUDENT and user_id == config.ADMIN_ID:
        WAITING_FOR_REMOVE_STUDENT.discard(user_id)
        if not text.isdigit():
            await update.message.reply_text("⚠️ User ID sirf numbers mein hoti hai. Kripya sahi User ID bhejein.")
            return

        target_uid = int(text)
        success = db.remove_student(target_uid)

        if success:
            await update.message.reply_text(
                f"✅ **Student Successfully Removed!**\n\n"
                f"User ID: `{target_uid}` ko database se hata diya gaya hai. "
                f"Ab yeh student chahe toh **dobara enroll kar sakta hai**!",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ User ID `{target_uid}` enrollment list mein nahi mili.", parse_mode="Markdown")
        return

    # 2. Handling Broadcast
    if user_id in WAITING_FOR_BROADCAST and user_id == config.ADMIN_ID:
        WAITING_FOR_BROADCAST.discard(user_id)
        message_to_send = text
        students = db.get_enrolled_list()

        if not students:
            await update.message.reply_text("ℹ️ Koi student enrolled nahi hai.")
            return

        status_msg = await update.message.reply_text(f"⏳ **Broadcasting to {len(students)} students...**")
        sent = 0
        failed = 0

        for s in students:
            target_uid = s.get("user_id")
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=message_to_send,
                    parse_mode="Markdown"
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await status_msg.edit_text(
            f"✅ **Broadcast Completed!**\n\n"
            f"📨 Successfully Sent: {sent}/{len(students)}\n"
            f"❌ Blocked/Failed: {failed}",
            parse_mode="Markdown"
        )


# Command se bhi remove kar sakein: /remove <user_id>
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Format: `/remove <user_id>`\nExample: `/remove 12345678`", parse_mode="Markdown")
        return

    target_uid = int(context.args[0])
    success = db.remove_student(target_uid)
    if success:
        await update.message.reply_text(f"✅ User ID `{target_uid}` successfully removed! Wo ab dobara enroll kar sakta hai.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ User ID `{target_uid}` list mein nahi mili.", parse_mode="Markdown")


# ────────────────────────────────────────────────────────────
# 6. MAIN FUNCTION
# ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 Starting Antim Prahar Bot with Remove & Re-enroll...")
    print(f"📌 Admin ID: {config.ADMIN_ID}")
    print("=" * 60)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", start_command))
    app.add_handler(CommandHandler("remove", remove_command))

    # Student Buttons
    app.add_handler(CallbackQueryHandler(yes_enroll_handler, pattern="^btn_yes_enroll$"))
    app.add_handler(CallbackQueryHandler(not_interested_handler, pattern="^btn_not_interested$"))
    app.add_handler(CallbackQueryHandler(batch_info_handler, pattern="^btn_batch_info$"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^btn_support$"))

    # Admin Dashboard Buttons
    app.add_handler(CallbackQueryHandler(admin_sendpost_btn, pattern="^adm_sendpost$"))
    app.add_handler(CallbackQueryHandler(admin_deletepost_btn, pattern="^adm_deletepost$"))
    app.add_handler(CallbackQueryHandler(admin_list_btn, pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(admin_stats_btn, pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(admin_ask_remove_btn, pattern="^adm_ask_remove$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_remove, pattern="^adm_cancel_remove$"))
    app.add_handler(CallbackQueryHandler(admin_ask_broadcast_btn, pattern="^adm_ask_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_broadcast, pattern="^adm_cancel_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_refresh_btn, pattern="^adm_refresh$"))

    # Text Input (Broadcast & Student Remove ID)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    print("✅ Bot is running! Waiting for clicks...")
    app.run_polling()

if __name__ == "__main__":
    main()
