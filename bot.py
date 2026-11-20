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

    try:
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

        bot_username = context.bot.username or "antimpraharrbatch_bot"

        if is_new:
            # 1. Pop-up alert for user (Screen par instant notice)
            alert_msg = (
                f"🎉 बधाई हो {user.first_name}!\n\n"
                f"आपका अंतिम प्रहार महाबैच में Enrollment सफलतापूर्वक दर्ज हो गया है! ✅\n\n"
                f"⚠️ कन्फर्मेशन व बैच अपडेट्स सीधे इनबॉक्स में पाने के लिए @{bot_username} को एक बार Start जरूर कर लें!"
            )
            await query.answer(alert_msg, show_alert=True)
            logger.info(f"New Enrollment: {user.full_name} ({user.id})")

            # 2. Student ko Personal Private DM bhejo
            dm_sent = False
            try:
                student_dm_text = (
                    f"🎉 <b>बधाई हो {user.full_name}!</b>\n\n"
                    f"आपका <b>{config.BATCH_NAME}</b> में Enrollment सफलतापूर्वक दर्ज हो गया है! 🚀\n\n"
                    f"📖 <b>विशेष पुस्तकें:</b> FATMAN , रसगुल्ला करेंट , सुदर्शन चक्र\n"
                    f"💰 <b>कीमत:</b> मात्र ₹{config.BATCH_FEE}\n\n"
                    f"बैच लॉन्च होते ही पेमेंट व परचेज लिंक आपको सीधे यहीं इनबॉक्स में भेजा जाएगा।\n\n"
                    f"💬 <i>यदि आपका कोई सवाल है तो आप इसी चैट में लिखकर भेज सकते हैं! Admin आपको यहीं Bot से जवाब देंगे।</i>"
                )
                await context.bot.send_message(
                    chat_id=user.id,
                    text=student_dm_text,
                    parse_mode="HTML"
                )
                dm_sent = True
            except Exception as dm_err:
                logger.info(f"Could not send DM to {user.id} (user hasn't pressed start in bot yet): {dm_err}")
                dm_sent = False

            # 3. Instant Private Alert to ADMIN (With DM Status)
            uname_text = f"@{user.username}" if user.username else "N/A"
            if dm_sent:
                dm_status_text = "✅ <b>Personal DM Sent to Student!</b>"
            else:
                dm_status_text = f"⚠️ <i>User ne abhi bot ko DM me /start nahi kiya hai (unhe popup me bol diya gaya hai).</i>"

            admin_alert = (
                f"🔔 <b>NAYA BATCH ENROLLMENT!</b> 🔥\n\n"
                f"👤 <b>Student Name:</b> {user.full_name}\n"
                f"🏷️ <b>Username:</b> {uname_text}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
                f"📚 <b>Batch:</b> {config.BATCH_NAME}\n"
                f"🕒 <b>Time:</b> <code>{enrolled_time}</code>\n"
                f"📨 <b>Student Message:</b> {dm_status_text}\n"
                f"─────────────────────\n"
                f"✅ <i>Data MongoDB Atlas me successfully save ho gaya hai.</i>"
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
            # Purane member ke dobara click karne par pop-up
            await query.answer(
                f"ℹ️ {user.first_name}, आपका नाम पहले से ही अंतिम प्रहार महाबैच लिस्ट में दर्ज है! ✅",
                show_alert=True
            )
            # Admin ko bhi alert bhej do taaki pata chale ki purane student ne click kiya
            uname_text = f"@{user.username}" if user.username else "N/A"
            try:
                await context.bot.send_message(
                    chat_id=config.ADMIN_ID,
                    text=(
                        f"ℹ️ <b>REPEAT ENROLL CLICK</b>\n\n"
                        f"👤 {user.full_name} ({uname_text})\n"
                        f"🆔 <code>{user.id}</code>\n"
                        f"<i>(Yeh student pehle se MongoDB me enrolled hai)</i>"
                    ),
                    parse_mode="HTML"
                )
            except Exception:
                pass

    except Exception as err:
        logger.error(f"Error in yes_enroll_handler: {err}")
        try:
            await query.answer("✅ आपका Enrollment दर्ज हो गया है!", show_alert=True)
        except Exception:
            pass


async def not_interested_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    try:
        # Check agar yeh student pehle enrolled tha aur ab Not Interested kar raha hai
        was_enrolled = db.mark_not_interested(user.id)

        # 1. User ke liye Pop-up alert
        if was_enrolled:
            alert_text = (
                f"👍 ठीक है {user.first_name}!\n\n"
                f"आपका नाम अंतिम प्रहार बैच लिस्ट से हटा दिया गया है।\n"
                f"अगर बाद में मन बने तो आप दोबारा 'YES Enroll' बटन दबा सकते हैं!"
            )
        else:
            alert_text = f"👍 कोई बात नहीं {user.first_name}! आपकी आगामी परीक्षा और तैयारी के लिए All the Best!"

        await query.answer(alert_text, show_alert=True)

        # 2. Admin ko instant private alert (Group me koi message nahi jayega, seedha aapke inbox me aayega)
        uname_text = f"@{user.username}" if user.username else "N/A"
        current_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")

        if was_enrolled:
            admin_alert = (
                f"❌ <b>STUDENT UN-ENROLLED! (Not Interested)</b>\n\n"
                f"👤 <b>Name:</b> {user.full_name}\n"
                f"🏷️ <b>Username:</b> {uname_text}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
                f"🕒 <b>Time:</b> <code>{current_time}</code>\n"
                f"─────────────────────\n"
                f"⚠️ <i>Yeh student pehle Enrolled tha. Ab Not Interested dabane par database se automatically remove ho gaya hai!</i>"
            )
        else:
            admin_alert = (
                f"❌ <b>NOT INTERESTED CLICK!</b>\n\n"
                f"👤 <b>Name:</b> {user.full_name}\n"
                f"🏷️ <b>Username:</b> {uname_text}\n"
                f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
                f"🕒 <b>Time:</b> <code>{current_time}</code>\n"
                f"─────────────────────\n"
                f"💡 <i>Yeh student abhi interested nahi hai.</i>"
            )

        try:
            await context.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=admin_alert,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send not-interested alert: {e}")

    except Exception as err:
        logger.error(f"Error in not_interested_handler: {err}")
        try:
            await query.answer("👍 आपकी पसंद नोट कर ली गई है!", show_alert=True)
        except Exception:
            pass


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
        await query.message.reply_text(
            f"ℹ️ <b>{config.BATCH_NAME}</b> ke liye abhi tak koi enrollment nahi hua hai.",
            parse_mode="HTML"
        )
        return

    header = f"📋 <b>{config.BATCH_NAME} - ENROLLED STUDENTS</b>\n👥 <b>Total Enrolled:</b> {total}\n"
    divider = "─" * 35 + "\n\n"

    lines = []
    # 1-Click Remove buttons banayein taaki admin bina type kiye seedha button se remove kar sake
    remove_buttons = []
    for idx, s in enumerate(students, start=1):
        name = s.get('full_name', 'Unknown')
        uname = s.get('username', 'N/A')
        uid = s.get('user_id', '')
        time_str = s.get('enrolled_at', '')
        lines.append(f"<b>{idx}.</b> {name} ({uname})\n   🆔 <code>{uid}</code> | 🕒 <code>{time_str}</code>")
        
        # Har student ka 1-click remove button (max 20)
        if idx <= 20:
            btn_label = f"❌ Remove {name[:14]} ({uname[:12]})"
            remove_buttons.append([InlineKeyboardButton(btn_label, callback_data=f"del_std_{uid}")])

    remove_buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_refresh")])
    list_markup = InlineKeyboardMarkup(remove_buttons)

    full_text = header + divider + "\n\n".join(lines)
    full_text += "\n\n💡 <i>Kisi student ko nikalne ke liye niche diye gaye <b>[❌ Remove]</b> button dabayein:</i>"

    if len(full_text) < 4000:
        await query.message.reply_text(full_text, reply_markup=list_markup, parse_mode="HTML")
    else:
        file_content = f"BATCH: {config.BATCH_NAME}\nTOTAL ENROLLED: {total}\n" + "="*50 + "\n\n"
        for idx, s in enumerate(students, start=1):
            file_content += f"{idx}. {s.get('full_name')} | Username: {s.get('username')} | ID: {s.get('user_id')} | Time: {s.get('enrolled_at')}\n"

        bio = io.BytesIO(file_content.encode('utf-8'))
        bio.name = "enrolled_students.txt"
        bio.seek(0)
        await query.message.reply_document(
            document=bio,
            caption=f"📄 Enrolled Students ({total})",
            reply_markup=list_markup
        )


# 1-Click Student Removal Button Callback
async def admin_del_student_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target_id = query.data.replace("del_std_", "")
    
    success, removed = db.remove_student(target_id)
    if success and removed:
        name = removed.get('full_name', 'Student')
        uname = removed.get('username', '')
        await query.answer(f"✅ {name} successfully removed!", show_alert=True)
        await query.message.reply_text(
            f"✅ <b>Student Successfully Removed!</b>\n\n"
            f"👤 <b>Name:</b> {name}\n"
            f"🏷️ <b>Username:</b> {uname}\n"
            f"🆔 <b>User ID:</b> <code>{removed.get('user_id')}</code>\n\n"
            f"Yeh student MongoDB Atlas se remove ho gaya hai aur ab <b>dobara enroll kar sakta hai</b>! 🚀",
            parse_mode="HTML"
        )
    else:
        await query.answer("❌ Student list mein nahi mila ya pehle hi remove ho chuka hai.", show_alert=True)


# 4. Total Stats
async def admin_stats_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    students = db.get_enrolled_list()
    total = len(students)
    await query.answer(f"📊 Total Enrolled: {total} Students", show_alert=True)


# 5. Student Remove / Un-enroll flow (Text Input)
async def admin_ask_remove_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_REMOVE_STUDENT.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_remove")]])

    await query.message.reply_text(
        "❌ <b>Kis Student ko Remove karna chahte hain?</b>\n\n"
        "Aap inme se kuch bhi yahan bhej sakte hain:\n"
        "• <b>Telegram User ID</b> (jaise: <code>8914751355</code>)\n"
        "• <b>Username</b> (jaise: <code>@niistharajput</code> ya <code>niistharajput</code>)\n"
        "• <b>Student ka Name</b>\n\n"
        "<i>(Remove hote hi yeh student dobara enroll kar sakega!)</i>",
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
# 5. MESSAGE HANDLER & 2-WAY SUPPORT CHAT
# ────────────────────────────────────────────────────────────

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = (update.message.text or "").strip()

    # Sirf Private Chats me messages handle karein
    if chat.type != "private":
        return

    # ========================================================
    # CASE A: AGAR ADMIN NE MESSAGE BHEJA HAI
    # ========================================================
    if user.id == config.ADMIN_ID:
        # 1. Check agar Admin kisi Student ke message ko Telegram 'Reply' kar raha hai
        if update.message.reply_to_message:
            rep_msg = update.message.reply_to_message.text or ""
            import re
            m = re.search(r"🆔 (?:Telegram )?ID:\s*<code>(\d+)</code>", rep_msg)
            if m:
                target_student_id = int(m.group(1))
                try:
                    await context.bot.send_message(
                        chat_id=target_student_id,
                        text=(
                            f"💬 <b>अंतिम प्रहार महाबैच - Admin का जवाब:</b>\n\n"
                            f"{text}\n\n"
                            f"─────────────────────\n"
                            f"<i>(यदि आपका कोई और सवाल है तो आप यहीं टाइप करके भेज सकते हैं)</i>"
                        ),
                        parse_mode="HTML"
                    )
                    await update.message.reply_text(
                        f"✅ <b>Reply Successfully Sent!</b>\n\n"
                        f"🆔 <b>Student ID:</b> <code>{target_student_id}</code>\n"
                        f"💬 <b>Aapka Message:</b> {text}",
                        parse_mode="HTML"
                    )
                    return
                except Exception as err:
                    await update.message.reply_text(f"❌ Student ko message bhejne me dikkat aayi: {err}")
                    return

        # 2. Check agar Admin Student Remove ID bhej raha hai
        if user.id in WAITING_FOR_REMOVE_STUDENT:
            WAITING_FOR_REMOVE_STUDENT.discard(user.id)
            success, removed = db.remove_student(text)
            if success and removed:
                name = removed.get('full_name', 'Student')
                uname = removed.get('username', 'N/A')
                uid = removed.get('user_id', '')
                await update.message.reply_text(
                    f"✅ <b>Student Successfully Removed!</b>\n\n"
                    f"👤 <b>Name:</b> {name}\n"
                    f"🏷️ <b>Username:</b> {uname}\n"
                    f"🆔 <b>User ID:</b> <code>{uid}</code>\n\n"
                    f"Yeh student database se remove ho gaya hai aur ab <b>dobara enroll kar sakta hai</b>! 🚀",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    f"❌ <code>{text}</code> enrollment list mein nahi mila.\n"
                    f"Kripya sahi User ID ya @username bhejein.",
                    parse_mode="HTML"
                )
            return

        # 3. Check agar Admin Broadcast Message bhej raha hai
        if user.id in WAITING_FOR_BROADCAST:
            WAITING_FOR_BROADCAST.discard(user.id)
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
                        text=text
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
            return

        # Default Admin prompt
        return

    # ========================================================
    # CASE B: AGAR KISI STUDENT NE BOT KO PRIVATE MESSAGE KIYA HAI
    # ========================================================
    # 1. Student ko confirmation
    await update.message.reply_text(
        "✅ <b>आपका संदेश Admin तक पहुँचा दिया गया है!</b>\n\n"
        "जल्द ही Admin आपको यहीं Bot के माध्यम से उत्तर देंगे। धैर्य रखने के लिए धन्यवाद! 🙏",
        parse_mode="HTML"
    )

    # 2. Admin ko alert bhejo
    uname_str = f"@{user.username}" if user.username else "N/A"
    current_time = datetime.now(IST).strftime("%d-%m-%Y %I:%M %p")
    admin_notif = (
        f"📩 <b>NAYA STUDENT MESSAGE!</b>\n\n"
        f"👤 <b>From:</b> {user.full_name}\n"
        f"🏷️ <b>Username:</b> {uname_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n"
        f"🕒 <b>Time:</b> <code>{current_time}</code>\n"
        f"─────────────────────\n"
        f"💬 <b>Student ka Message:</b>\n"
        f"<blockquote>{text}</blockquote>\n"
        f"─────────────────────\n"
        f"👉 <b>Reply kaise karein:</b>\n"
        f"1️⃣ Is message ko Telegram mein <b>'Reply'</b> karein aur javab likh dein!\n"
        f"2️⃣ Ya command likhein: <code>/reply {user.id} Aapka javab</code>"
    )

    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=admin_notif,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Failed to forward student message to admin: {e}")


# Command: /reply <student_id> <message>
async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ <b>Format:</b> <code>/reply &lt;student_id&gt; &lt;aapka javab&gt;</code>\n\n"
            "Example: <code>/reply 8914751355 Batch jald hi shuru ho raha hai!</code>",
            parse_mode="HTML"
        )
        return

    if not context.args[0].isdigit():
        await update.message.reply_text("⚠️ Student ID sirf numbers mein hoti hai.")
        return

    target_student_id = int(context.args[0])
    reply_text = " ".join(context.args[1:])

    try:
        await context.bot.send_message(
            chat_id=target_student_id,
            text=(
                f"💬 <b>अंतिम प्रहार महाबैच - Admin का जवाब:</b>\n\n"
                f"{reply_text}\n\n"
                f"─────────────────────\n"
                f"<i>(यदि आपका कोई और सवाल है तो आप यहीं लिखकर पूछ सकते हैं)</i>"
            ),
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"✅ <b>Reply Successfully Sent!</b>\n\n"
            f"🆔 <b>Student ID:</b> <code>{target_student_id}</code>\n"
            f"💬 <b>Message:</b> {reply_text}",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Student ko message bhejne mein error aaya: {e}")


# Command se bhi remove kar sakein: /remove <user_id ya username>
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Format: <code>/remove &lt;user_id ya @username&gt;</code>\n"
            "Example: <code>/remove 8914751355</code> ya <code>/remove @niistharajput</code>",
            parse_mode="HTML"
        )
        return

    target = context.args[0]
    success, removed = db.remove_student(target)
    if success and removed:
        name = removed.get('full_name', 'Student')
        uname = removed.get('username', 'N/A')
        await update.message.reply_text(
            f"✅ <b>{name}</b> ({uname}) successfully database se remove ho gaya! Wo ab dobara enroll kar sakta hai.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"❌ <code>{target}</code> list mein nahi mila.", parse_mode="HTML")


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
    app.add_handler(CommandHandler("reply", reply_command))

    # Student Buttons
    app.add_handler(CallbackQueryHandler(yes_enroll_handler, pattern="^btn_yes_enroll$"))
    app.add_handler(CallbackQueryHandler(not_interested_handler, pattern="^btn_not_interested$"))
    app.add_handler(CallbackQueryHandler(batch_info_handler, pattern="^btn_batch_info$"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^btn_support$"))

    # Admin Dashboard Buttons
    app.add_handler(CallbackQueryHandler(admin_sendpost_btn, pattern="^adm_sendpost$"))
    app.add_handler(CallbackQueryHandler(admin_deletepost_btn, pattern="^adm_deletepost$"))
    app.add_handler(CallbackQueryHandler(admin_list_btn, pattern="^adm_list$"))
    app.add_handler(CallbackQueryHandler(admin_del_student_callback, pattern="^del_std_"))
    app.add_handler(CallbackQueryHandler(admin_stats_btn, pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(admin_ask_remove_btn, pattern="^adm_ask_remove$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_remove, pattern="^adm_cancel_remove$"))
    app.add_handler(CallbackQueryHandler(admin_ask_broadcast_btn, pattern="^adm_ask_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_broadcast, pattern="^adm_cancel_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_refresh_btn, pattern="^adm_refresh$"))

    # Messages (Student to Admin Support + Admin Replies + Broadcast + Remove ID)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("✅ Bot is running! Waiting for clicks...")
    app.run_polling()

if __name__ == "__main__":
    main()
