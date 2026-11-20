"""
============================================================
  🎯 अंतिम प्रहार महाबैच - EXACT BANNER + BLOCKQUOTE BOT
  - Exact User-Requested Design (Photo + Blockquote Text + Buttons)
  - Blockquote styling: विशेष पुस्तकें & कीमत मात्र ₹99
  - [✅ YES Enroll Now] & [❌ Not Interested] Buttons
  - Real-time MongoDB Saving (No Data Loss & Duplicate Lock)
  - Instant Admin Private Alerts
  - Admin Panel with Remove Post & Student Re-enroll
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

# Path to Banner Image (Local + Online CDN Fallback)
BANNER_PATH = os.path.join(os.path.dirname(__file__), "banner.jpg")
BANNER_URL = "https://files.catbox.moe/pycwyv.jpg"

# States for admin input
WAITING_FOR_BROADCAST = set()
WAITING_FOR_REMOVE_STUDENT = set()


# ────────────────────────────────────────────────────────────
# 1. EXACT USER-REQUESTED CAPTION & KEYBOARDS
# ────────────────────────────────────────────────────────────

def get_post_text():
    """Exact styling requested by user with Blockquote"""
    return (
        "🔥 <b>अंतिम प्रहार महाबैच</b> 🔥\n\n"
        "<blockquote>विशेष पुस्तकें - FATMAN , रसगुल्ला करेंट , सुदर्शन चक्र\n"
        "💰 कीमत – मात्र ₹99</blockquote>\n\n"
        "🚀 <b>बैच जल्द आ रहा है!</b>\n"
        "📝 <b>आज ही रजिस्ट्रेशन करें!</b>"
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
            f"👑 <b>ADMIN CONTROL PANEL</b>\n"
            f"🎯 Batch: <b>{config.BATCH_NAME}</b>\n\n"
            f"👥 <b>Total Enrolled Students:</b> <code>{len(students)}</code>\n"
            f"💰 <b>Batch Fee:</b> <code>₹{config.BATCH_FEE}</code>\n\n"
            f"Niche diye gaye <b>Buttons</b> se poora bot control karein 👇"
        )
        await update.message.reply_text(
            admin_text,
            reply_markup=get_admin_dashboard_keyboard(),
            parse_mode="HTML"
        )
        return

    # AGAR GROUP HAI YA STUDENT HAI -> Photo + Caption + Buttons
    keyboard = get_group_enroll_keyboard() if chat.type != "private" else get_student_dm_keyboard()
    try:
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo,
                    caption=get_post_text(),
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            await update.message.reply_photo(
                photo=BANNER_URL,
                caption=get_post_text(),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception:
        await update.message.reply_text(
            get_post_text(),
            reply_markup=keyboard,
            parse_mode="HTML"
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
        uname_text = f"@{user.username}" if user.username else "N/A"
        admin_alert = (
            f"🔔 <b>NAYA BATCH ENROLLMENT!</b> 🔥\n\n"
            f"👤 <b>Student Name:</b> {user.full_name}\n"
            f"🏷️ <b>Username:</b> {uname_text}\n"
            f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
            f"📚 <b>Batch:</b> {config.BATCH_NAME}\n"
            f"🕒 <b>Time:</b> <code>{enrolled_time}</code>\n"
            f"─────────────────────\n"
            f"✅ <i>Data MongoDB me successfully save ho gaya hai.</i>"
        )

        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=admin_alert,
                parse_mode="HTML"
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
        f"📖 <b>{config.BATCH_NAME} - Complete Information</b>\n\n"
        f"🔹 <b>3 Books Coverage:</b> Parmar SSC Fatman + Rasgulla Book (Kumar Gaurav Sir) + Sudarshan Chakra\n"
        f"🔹 <b>Daily Practice:</b> Topic-wise quizes directly based on these books\n"
        f"🔹 <b>Target:</b> High Score in General Studies & Current Affairs\n"
        f"💰 <b>Fee:</b> ₹{config.BATCH_FEE}\n\n"
        f"Enroll karne ke liye niche button dabayein 👇"
    )
    await query.edit_message_caption(
        caption=info_text,
        reply_markup=get_student_dm_keyboard(),
        parse_mode="HTML"
    )


async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"📞 <b>Help & Support</b>\n\n"
        f"Kisi bhi query ya help ke liye aap Admin se contact kar sakte hain:\n"
        f"Admin ID: <code>{config.ADMIN_ID}</code>"
    )
    await query.edit_message_caption(
        caption=text,
        reply_markup=get_student_dm_keyboard(),
        parse_mode="HTML"
    )


# ────────────────────────────────────────────────────────────
# 4. ADMIN BUTTON HANDLERS (Photo + Blockquote + Buttons)
# ────────────────────────────────────────────────────────────

# 1. Post Lagayein
async def admin_sendpost_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("📢 Group me post bheji ja rahi hai...")

    target_chat = config.GROUP_ID
    try:
        # Photo + User's exact Blockquote caption + Buttons
        if os.path.exists(BANNER_PATH):
            with open(BANNER_PATH, "rb") as photo:
                sent_msg = await context.bot.send_photo(
                    chat_id=target_chat,
                    photo=photo,
                    caption=get_post_text(),
                    reply_markup=get_group_enroll_keyboard(),
                    parse_mode="HTML"
                )
        else:
            sent_msg = await context.bot.send_photo(
                chat_id=target_chat,
                photo=BANNER_URL,
                caption=get_post_text(),
                reply_markup=get_group_enroll_keyboard(),
                parse_mode="HTML"
            )
        
        # Save post ID so it can be deleted later
        db.save_post_id(sent_msg.message_id)
        await query.message.reply_text(
            f"✅ <b>Success!</b> अंतिम प्रहार महाबैच पोस्ट Group ({target_chat}) mein lag gayi hai!\n\n"
            f"Jab bhi hatani ho, aap <b>'🗑️ Group se Post Hatayein'</b> button daba sakte hain.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in sendpost: {e}")
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
            "✅ <b>Post Successfully Removed!</b>\n\n"
            "Group se enrollment post hata di gayi hai. "
            "Jab dobara lagani ho toh <b>'📢 Group me Post Lagayein'</b> button daba dein!",
            parse_mode="HTML"
        )
    except Exception as e:
        db.clear_post_id()
        await query.message.reply_text(f"⚠️ Post delete karne mein dikkat aayi: {e}")


# 3. Student List Dekhein
async def admin_list_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    students = db.get_enrolled_list()
    total = len(students)

    if total == 0:
        await query.message.reply_text(f"ℹ️ <b>{config.BATCH_NAME}</b> ke liye abhi tak koi enrollment nahi hua hai.", parse_mode="HTML")
        return

    header = f"📋 <b>{config.BATCH_NAME} - ENROLLED STUDENTS</b>\n👥 <b>Total Enrolled:</b> {total}\n"
    divider = "─" * 35 + "\n\n"

    lines = []
    for idx, s in enumerate(students, start=1):
        name = s.get('full_name', 'Unknown')
        uname = s.get('username', 'N/A')
        uid = s.get('user_id', '')
        time_str = s.get('enrolled_at', '')
        lines.append(f"<b>{idx}.</b> {name} ({uname})\n   🆔 <code>{uid}</code> | 🕒 <code>{time_str}</code>")

    full_text = header + divider + "\n\n".join(lines)

    if len(full_text) < 4000:
        await query.message.reply_text(full_text, parse_mode="HTML")
    else:
        summary_text = f"📋 <b>{config.BATCH_NAME} - ENROLLMENT LIST</b>\n👥 <b>Total Enrolled:</b> {total}\n\nList text file mein attach ki gayi hai:"
        await query.message.reply_text(summary_text, parse_mode="HTML")

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
        "❌ <b>Kis Student ko Remove karna chahte hain?</b>\n\n"
        "Us student ka <b>Telegram User ID</b> yahan type karke bhejein.\n"
        "<i>(User ID aapko '📋 Enrolled Students List' mein mil jayegi)</i>\n\n"
        "Remove karne ke baad wo student <b>dobara enroll kar sakega</b>!",
        reply_markup=cancel_btn,
        parse_mode="HTML"
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
        "📝 <b>Aap sabhi Enrolled Students ko kya message ya payment link bhejna chahte hain?</b>\n\n"
        "Apna poora message yahan type karke send kar dein. (Bot use sabhi ke inbox me deliver kar dega!)\n\n"
        "Agar abhi nahi bhejna toh niche Cancel dabayein:",
        reply_markup=cancel_btn,
        parse_mode="HTML"
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
        f"👑 <b>ADMIN CONTROL PANEL</b>\n"
        f"🎯 Batch: <b>{config.BATCH_NAME}</b>\n\n"
        f"👥 <b>Total Enrolled Students:</b> <code>{len(students)}</code>\n"
        f"💰 <b>Batch Fee:</b> <code>₹{config.BATCH_FEE}</code>\n\n"
        f"Niche diye gaye <b>Buttons</b> se poora bot control karein 👇"
    )
    await query.edit_message_text(
        admin_text,
        reply_markup=get_admin_dashboard_keyboard(),
        parse_mode="HTML"
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
                f"✅ <b>Student Successfully Removed!</b>\n\n"
                f"User ID: <code>{target_uid}</code> ko database se hata diya gaya hai. "
                f"Ab yeh student chahe toh <b>dobara enroll kar sakta hai</b>!",
                parse_mode="HTML"
            )
        else:
            await update.message.reply_text(f"❌ User ID <code>{target_uid}</code> enrollment list mein nahi mili.", parse_mode="HTML")
        return

    # 2. Handling Broadcast
    if user_id in WAITING_FOR_BROADCAST and user_id == config.ADMIN_ID:
        WAITING_FOR_BROADCAST.discard(user_id)
        message_to_send = text
        students = db.get_enrolled_list()

        if not students:
            await update.message.reply_text("ℹ️ Koi student enrolled nahi hai.")
            return

        status_msg = await update.message.reply_text(f"⏳ <b>Broadcasting to {len(students)} students...</b>", parse_mode="HTML")
        sent = 0
        failed = 0

        for s in students:
            target_uid = s.get("user_id")
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=message_to_send
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        await status_msg.edit_text(
            f"✅ <b>Broadcast Completed!</b>\n\n"
            f"📨 Successfully Sent: {sent}/{len(students)}\n"
            f"❌ Blocked/Failed: {failed}",
            parse_mode="HTML"
        )


# Command se bhi remove kar sakein: /remove <user_id>
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Format: <code>/remove &lt;user_id&gt;</code>\nExample: <code>/remove 12345678</code>", parse_mode="HTML")
        return

    target_uid = int(context.args[0])
    success = db.remove_student(target_uid)
    if success:
        await update.message.reply_text(f"✅ User ID <code>{target_uid}</code> successfully removed! Wo ab dobara enroll kar sakta hai.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ User ID <code>{target_uid}</code> list mein nahi mili.", parse_mode="HTML")


# ────────────────────────────────────────────────────────────
# 6. MAIN FUNCTION
# ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 Starting Antim Prahar Bot with Exact Blockquote & Buttons...")
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
