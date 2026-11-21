"""
============================================================
  🎯 अंतिम प्रहार महाबैच & करेंट अफेयर्स - MULTI-BATCH & MULTI-GROUP BOT
  - Exact User-Requested Design (Photo + Blockquote Text + Buttons)
  - 2 Batches Support: अंतिम प्रहार महाबैच (₹99) & करेंट अफेयर्स स्पेशल (₹49)
  - 2 Groups Support: Post to Group 1, Group 2, or Both Groups
  - In-Chat Banner Change: Send photo to bot DM -> Instant Banner Update!
  - Real-time MongoDB Saving (No Data Loss & Duplicate Lock per batch)
  - Instant Admin Private Alerts (Clean & Compact)
  - 1-Click Student Removal & Telegram Reply Support
============================================================
"""

import os
import io
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta

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

# IST Timezone (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Initialize MongoDB
db = DatabaseManager(mongo_uri=config.MONGO_URI, db_name=config.MONGO_DB_NAME)

# Path to Banner Image (Local + Catbox Fallback)
BANNER_PATH = os.path.join(os.path.dirname(__file__), "banner.jpg")
BANNER_URL = "https://files.catbox.moe/pycwyv.jpg"

# States for admin input
WAITING_FOR_BROADCAST = set()
WAITING_FOR_REMOVE_STUDENT = set()
WAITING_FOR_GROUP2_ID = set()
WAITING_FOR_BANNER = set()


# ────────────────────────────────────────────────────────────
# 1. BATCH TEXT & KEYBOARD HELPERS
# ────────────────────────────────────────────────────────────

def get_post_text(batch_key="b1"):
    """Exact styling requested by user with Blockquote"""
    if batch_key == "b2":
        return (
            f"🔥 <b>{config.BATCH_2_NAME}</b> 🔥\n\n"
            f"<blockquote>विशेष कवरेज - Daily & Monthly Current Affairs, वार्षिकी\n"
            f"💰 कीमत – मात्र ₹{config.BATCH_2_FEE}</blockquote>\n\n"
            f"🚀 <b>नया बैच जल्द शुरू हो रहा है!</b>\n"
            f"📝 <b>आज ही रजिस्ट्रेशन करें!</b>"
        )
    return (
        f"🔥 <b>{config.BATCH_1_NAME}</b> 🔥\n\n"
        f"<blockquote>विशेष पुस्तकें - FATMAN , रसगुल्ला करेंट , सुदर्शन चक्र\n"
        f"💰 कीमत – मात्र ₹{config.BATCH_1_FEE}</blockquote>\n\n"
        f"🚀 <b>बैच जल्द आ रहा है!</b>\n"
        f"📝 <b>आज ही रजिस्ट्रेशन करें!</b>"
    )

def get_group_enroll_keyboard(batch_key="b1"):
    """Group me dikhne wale buttons"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ YES Enroll Now", callback_data=f"btn_yes_{batch_key}")],
        [InlineKeyboardButton("❌ Not Interested", callback_data=f"btn_no_{batch_key}")]
    ])

def get_admin_dashboard_keyboard():
    """Admin ke liye Main Control Buttons"""
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
            InlineKeyboardButton("⚙️ Groups Manage (1 & 2)", callback_data="adm_manage_groups"),
            InlineKeyboardButton("🖼️ Banner Badlein", callback_data="adm_change_banner")
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
        [InlineKeyboardButton("🚀 Batch 1: अंतिम प्रहार महाबैच", callback_data="btn_yes_b1")],
        [InlineKeyboardButton("📰 Batch 2: करेंट अफेयर्स स्पेशल", callback_data="btn_yes_b2")],
        [InlineKeyboardButton("📖 Batch Details", callback_data="btn_batch_info")],
        [InlineKeyboardButton("📞 Support / Contact", callback_data="btn_support")]
    ])

async def send_banner_to_chat(bot, chat_id, text, keyboard):
    """Banners sending helper: MongoDB custom banner -> Local banner.jpg -> Online Catbox"""
    custom_file_id = db.get_banner_file_id()
    if custom_file_id:
        try:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=custom_file_id,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Failed to send with custom_file_id: {e}, falling back to file/url")

    if os.path.exists(BANNER_PATH):
        try:
            with open(BANNER_PATH, "rb") as photo:
                return await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.warning(f"Failed to send local photo: {e}")

    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=BANNER_URL,
            caption=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ────────────────────────────────────────────────────────────
# 2. /start & /admin COMMAND
# ────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # AGAR GROUP ME BOT KO /start KIYA GAYA HAI -> Auto-Register Group
    if chat.type in ["group", "supergroup"]:
        if user.id == config.ADMIN_ID:
            groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
            if not groups.get("group_1"):
                db.save_group(chat.id, chat.title, slot="group_1")
                slot_name = "Group 1 (Main Study Group)"
            elif not groups.get("group_2") and groups.get("group_1", {}).get("chat_id") != chat.id:
                db.save_group(chat.id, chat.title, slot="group_2")
                slot_name = "Group 2"
            else:
                db.save_group(chat.id, chat.title)
                slot_name = "Connected Group"

            await update.message.reply_text(
                f"✅ <b>{chat.title}</b> bot ke sath successfully connect ho gaya hai!\n"
                f"📌 Slot: <b>{slot_name}</b>\n"
                f"🆔 Group ID: <code>{chat.id}</code>",
                parse_mode="HTML"
            )
            return

    # AGAR ADMIN HAI PRIVATE CHAT ME -> Admin Dashboard with Buttons
    if user.id == config.ADMIN_ID and chat.type == "private":
        students_b1 = db.get_enrolled_list(config.BATCH_1_NAME)
        students_b2 = db.get_enrolled_list(config.BATCH_2_NAME)
        total_students = len(students_b1) + len(students_b2)
        groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)

        g1_txt = groups.get("group_1", {}).get("title", "Main Group") if groups.get("group_1") else "Not Set"
        g2_txt = groups.get("group_2", {}).get("title", "Second Group") if groups.get("group_2") else "Not Set"

        admin_text = (
            f"👑 <b>ADMIN CONTROL PANEL</b>\n"
            f"─────────────────────────\n"
            f"🎯 <b>Batch 1:</b> {config.BATCH_1_NAME} (₹{config.BATCH_1_FEE}) → <code>{len(students_b1)}</code> Enrolled\n"
            f"📰 <b>Batch 2:</b> {config.BATCH_2_NAME} (₹{config.BATCH_2_FEE}) → <code>{len(students_b2)}</code> Enrolled\n"
            f"👥 <b>Total Enrollments:</b> <code>{total_students}</code>\n"
            f"─────────────────────────\n"
            f"📍 <b>Group 1:</b> {g1_txt}\n"
            f"📍 <b>Group 2:</b> {g2_txt}\n\n"
            f"Niche diye gaye <b>Buttons</b> se poora bot control karein 👇"
        )
        await update.message.reply_text(
            admin_text,
            reply_markup=get_admin_dashboard_keyboard(),
            parse_mode="HTML"
        )
        return

    # STUDENT KE LIYE PRIVATE CHAT ME
    if chat.type == "private":
        caption = (
            f"👋 <b>नमस्ते {user.full_name}!</b>\n\n"
            f"हमारे आगामी स्पेशल बैचेस में आपका स्वागत है:\n\n"
            f"1️⃣ <b>{config.BATCH_1_NAME}</b> (मात्र ₹{config.BATCH_1_FEE})\n"
            f"2️⃣ <b>{config.BATCH_2_NAME}</b> (मात्र ₹{config.BATCH_2_FEE})\n\n"
            f"जिस बैच में आप जुड़ना चाहते हैं, नीचे बटन दबाएं 👇"
        )
        await send_banner_to_chat(context.bot, chat.id, caption, get_student_dm_keyboard())
        return

    # GROUP ME DEFAULT POST
    await send_banner_to_chat(context.bot, chat.id, get_post_text("b1"), get_group_enroll_keyboard("b1"))


# ────────────────────────────────────────────────────────────
# 3. YES ENROLL & NOT INTERESTED BUTTONS (Multi-Batch)
# ────────────────────────────────────────────────────────────

async def yes_enroll_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    if "b2" in data:
        batch_key = "b2"
        batch_name = config.BATCH_2_NAME
        batch_fee = config.BATCH_2_FEE
        details_txt = "Daily & Monthly Current Affairs, वार्षिकी"
    else:
        batch_key = "b1"
        batch_name = config.BATCH_1_NAME
        batch_fee = config.BATCH_1_FEE
        details_txt = "FATMAN , रसगुल्ला करेंट , सुदर्शन चक्र"

    try:
        success, is_new, enrolled_time = db.enroll_student(
            user_id=user.id,
            full_name=user.full_name,
            username=user.username,
            batch_name=batch_name
        )

        if not success:
            await query.answer("❌ Error aaya. Kripya dobara prayas karein.", show_alert=True)
            return

        bot_username = context.bot.username or "antimpraharrbatch_bot"

        if is_new:
            alert_msg = (
                f"🎉 REGISTRATION CONFIRMED! ✅\n"
                f"─────────────────────────\n"
                f"👤 Candidate: {user.full_name}\n"
                f"🎯 Batch: {batch_name}\n"
                f"💰 Fee: मात्र ₹{batch_fee}\n"
                f"─────────────────────────\n"
                f"📌 आपका नाम {batch_name} में दर्ज हो चुका है!\n\n"
                f"⚠️ महत्वपूर्ण सूचना:\n"
                f"पेमेंट लिंक व क्लास अपडेट्स सीधे इनबॉक्स में पाने हेतु @{bot_username} को Private DM में Start जरूर कर लें।"
            )
            await query.answer(alert_msg, show_alert=True)
            logger.info(f"New Enrollment [{batch_name}]: {user.full_name} ({user.id})")

            try:
                student_dm_text = (
                    f"🎉 <b>बधाई हो {user.full_name}!</b>\n\n"
                    f"आपका <b>{batch_name}</b> में Enrollment सफलतापूर्वक दर्ज हो गया है! 🚀\n\n"
                    f"📖 <b>कवरेज:</b> {details_txt}\n"
                    f"💰 <b>कीमत:</b> मात्र ₹{batch_fee}\n\n"
                    f"बैच लॉन्च होते ही पेमेंट व परचेज लिंक आपको सीधे यहीं इनबॉक्स में भेजा जाएगा।\n\n"
                    f"💬 <i>यदि आपका कोई सवाल है तो आप इसी चैट में लिखकर भेज सकते हैं! Admin आपको यहीं Bot से जवाब देंगे।</i>"
                )
                await context.bot.send_message(
                    chat_id=user.id,
                    text=student_dm_text,
                    parse_mode="HTML"
                )
            except Exception as dm_err:
                logger.info(f"Could not send DM to {user.id}: {dm_err}")

            uname_text = f"@{user.username}" if user.username else "N/A"
            total_b = len(db.get_enrolled_list(batch_name))
            admin_alert = (
                f"🔔 <b>New Enroll [{batch_name}]:</b> {user.full_name} ({uname_text})\n"
                f"🆔 <code>{user.id}</code> | 👥 <b>Total {batch_name}:</b> {total_b}"
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
            already_msg = (
                f"ℹ️ ALREADY REGISTERED\n"
                f"─────────────────────────\n"
                f"👤 Candidate: {user.full_name}\n"
                f"🎯 Batch: {batch_name}\n"
                f"─────────────────────────\n"
                f"✅ आपका रजिस्ट्रेशन {batch_name} में पहले से ही दर्ज है।"
            )
            await query.answer(already_msg, show_alert=True)

    except Exception as err:
        logger.error(f"Error in yes_enroll_handler: {err}")
        try:
            await query.answer("✅ आपका Enrollment दर्ज हो गया है!", show_alert=True)
        except Exception:
            pass


async def not_interested_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data

    batch_name = config.BATCH_2_NAME if "b2" in data else config.BATCH_1_NAME

    try:
        was_enrolled = db.mark_not_interested(user.id, batch_name=batch_name)

        if was_enrolled:
            alert_text = (
                f"📋 STATUS: UN-ENROLLED ℹ️\n"
                f"─────────────────────────\n"
                f"👤 Candidate: {user.full_name}\n"
                f"🎯 Batch: {batch_name}\n"
                f"─────────────────────────\n"
                f"✅ आपका नाम {batch_name} लिस्ट से हटा दिया गया है।\n\n"
                f"💡 आप कभी भी दोबारा 'YES Enroll' बटन दबाकर जुड़ सकते हैं। All the Best! 🎯"
            )
        else:
            alert_text = (
                f"🎯 FEEDBACK RECORDED ℹ️\n"
                f"─────────────────────────\n"
                f"👤 Candidate: {user.full_name}\n"
                f"─────────────────────────\n"
                f"👍 आपकी पसंद नोट कर ली गई है। आगामी परीक्षा के लिए All the Best! ✨"
            )

        await query.answer(alert_text, show_alert=True)

        if was_enrolled:
            uname_text = f"@{user.username}" if user.username else "N/A"
            total_now = len(db.get_enrolled_list(batch_name))
            admin_alert = (
                f"❌ <b>Un-Enrolled [{batch_name}]:</b> {user.full_name} ({uname_text})\n"
                f"🆔 <code>{user.id}</code> | 👥 <b>Remaining:</b> {total_now}"
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
        f"📖 <b>AVAILABLE BATCHES INFORMATION</b>\n\n"
        f"1️⃣ <b>{config.BATCH_1_NAME}</b>\n"
        f"🔹 3 Books: Parmar SSC Fatman + Rasgulla Book + Sudarshan Chakra\n"
        f"🔹 Daily Practice & Tests\n"
        f"💰 Fee: ₹{config.BATCH_1_FEE}\n\n"
        f"2️⃣ <b>{config.BATCH_2_NAME}</b>\n"
        f"🔹 Daily & Monthly Current Affairs\n"
        f"🔹 Special Exam Coverage & Quizes\n"
        f"💰 Fee: ₹{config.BATCH_2_FEE}\n\n"
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
        f"Admin ID: <code>{config.ADMIN_ID}</code>\n\n"
        f"Aap is chat me seedha apna message likh kar bhi bhej sakte hain!"
    )
    await query.edit_message_caption(
        caption=text,
        reply_markup=get_student_dm_keyboard(),
        parse_mode="HTML"
    )


# ────────────────────────────────────────────────────────────
# 4. DIRECT GROUP POSTING (Group 1, Group 2, ya Dono)
# ────────────────────────────────────────────────────────────

async def admin_sendpost_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
    g1 = groups.get("group_1")
    g2 = groups.get("group_2")

    g1_label = g1["title"] if g1 else "Group 1 (Main Study Group)"
    g2_label = g2["title"] if g2 else "Group 2"

    text = (
        f"📢 <b>POST KAHAN LAGANI HAI?</b>\n\n"
        f"🎯 <b>अंतिम प्रहार महाबैच</b> (₹{config.BATCH_FEE})\n"
        f"<blockquote>विशेष पुस्तकें - FATMAN , रसगुल्ला करेंट , सुदर्शन चक्र</blockquote>\n\n"
        f"Aapke Groups:\n"
        f"1️⃣ <b>Group 1:</b> {g1_label}\n"
        f"2️⃣ <b>Group 2:</b> {g2_label if g2 else '<i>(Abhi set nahi hai)</i>'}\n\n"
        f"Kis group me post bhejna chahte hain? Select karein 👇"
    )

    buttons = [
        [InlineKeyboardButton("📌 Group 1 me Lagayein", callback_data="adm_post_send_g1")],
    ]
    if g2:
        buttons.append([InlineKeyboardButton("📌 Group 2 me Lagayein", callback_data="adm_post_send_g2")])
        buttons.append([InlineKeyboardButton("📢 Dono Groups me Ek Sath", callback_data="adm_post_send_both")])
    else:
        buttons.append([InlineKeyboardButton("➕ Group 2 Add Karein (/setgroup2)", callback_data="adm_manage_groups")])

    buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_refresh")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def admin_post_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target = query.data.replace("adm_post_send_", "")  # g1, g2, both

    post_caption = get_post_text()
    post_keyboard = get_group_enroll_keyboard()

    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
    g1 = groups.get("group_1")
    g2 = groups.get("group_2")

    targets_to_send = []
    if target in ["g1", "both"]:
        if g1:
            targets_to_send.append(("Group 1", g1["chat_id"]))
        else:
            await query.answer("❌ Group 1 ID set nahi hai!", show_alert=True)
            return

    if target in ["g2", "both"]:
        if g2:
            targets_to_send.append(("Group 2", g2["chat_id"]))
        elif target == "g2":
            await query.answer("❌ Group 2 abhi set nahi hai! Doosre group me /setgroup2 likhein.", show_alert=True)
            return

    sent_names = []
    errors = []

    for name, cid in targets_to_send:
        try:
            sent_msg = await send_banner_to_chat(context.bot, cid, post_caption, post_keyboard)
            if sent_msg:
                db.save_post_id(sent_msg.message_id, chat_id=cid)
                sent_names.append(name)
        except Exception as e:
            logger.error(f"Failed to send post to {name} ({cid}): {e}")
            errors.append(f"{name}: {e}")

    if sent_names:
        msg = f"✅ Success! Post bhej di gayi:\n📍 Groups: {', '.join(sent_names)}"
        if errors:
            msg += f"\n⚠️ Errors: {', '.join(errors)}"
        await query.answer(msg, show_alert=True)
    else:
        await query.answer(f"❌ Post bhejne me error aaya: {', '.join(errors)}", show_alert=True)

    await admin_refresh_btn(update, context)


# ────────────────────────────────────────────────────────────
# 5. POST DELETING MENU (Group 1, Group 2, or Both)
# ────────────────────────────────────────────────────────────

async def admin_deletepost_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
    g1 = groups.get("group_1")
    g2 = groups.get("group_2")

    text = (
        f"🗑️ <b>GROUP SE POST HATAYEIN</b>\n\n"
        f"Aap kis group se active post hatana chahte hain?\n\n"
        f"1️⃣ Group 1: <b>{g1['title'] if g1 else 'Not Set'}</b>\n"
        f"2️⃣ Group 2: <b>{g2['title'] if g2 else 'Not Set'}</b>\n\n"
        f"Select karein 👇"
    )

    buttons = [
        [InlineKeyboardButton("🗑️ Group 1 se Hatayein", callback_data="adm_del_exec_g1")]
    ]
    if g2:
        buttons.append([InlineKeyboardButton("🗑️ Group 2 se Hatayein", callback_data="adm_del_exec_g2")])
        buttons.append([InlineKeyboardButton("🗑️ Dono Groups se Hatayein", callback_data="adm_del_exec_both")])

    buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_refresh")])

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")


async def admin_del_post_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    target = query.data.replace("adm_del_exec_", "")

    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
    g1 = groups.get("group_1")
    g2 = groups.get("group_2")

    targets_to_delete = []
    if target in ["g1", "both"] and g1:
        targets_to_delete.append(("Group 1", g1["chat_id"]))
    if target in ["g2", "both"] and g2:
        targets_to_delete.append(("Group 2", g2["chat_id"]))

    deleted_names = []
    not_found = []

    for name, cid in targets_to_delete:
        pid = db.get_post_id(chat_id=cid)
        if pid:
            try:
                await context.bot.delete_message(chat_id=cid, message_id=pid)
                db.clear_post_id(chat_id=cid)
                deleted_names.append(name)
            except Exception as e:
                db.clear_post_id(chat_id=cid)
                deleted_names.append(f"{name} (Cleared)")
        else:
            not_found.append(name)

    if deleted_names:
        await query.answer(f"✅ Post successfully hata di gayi: {', '.join(deleted_names)}", show_alert=True)
    else:
        await query.answer("ℹ️ In groups mein koi active post nahi mili.", show_alert=True)

    await admin_refresh_btn(update, context)


# ────────────────────────────────────────────────────────────
# 6. GROUPS MANAGEMENT MENU
# ────────────────────────────────────────────────────────────

async def admin_manage_groups_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)
    g1 = groups.get("group_1")
    g2 = groups.get("group_2")

    g1_str = f"<b>{g1['title']}</b> (<code>{g1['chat_id']}</code>)" if g1 else "<i>Not Set</i>"
    g2_str = f"<b>{g2['title']}</b> (<code>{g2['chat_id']}</code>)" if g2 else "<i>Abhi Set Nahi Hai</i>"

    text = (
        f"⚙️ <b>CONNECTED TELEGRAM GROUPS</b>\n"
        f"─────────────────────────\n"
        f"1️⃣ <b>Group 1 (Main Study Group):</b>\n"
        f"   {g1_str}\n\n"
        f"2️⃣ <b>Group 2:</b>\n"
        f"   {g2_str}\n"
        f"─────────────────────────\n"
        f"👉 <b>Group 2 Kaise Add Karein:</b>\n"
        f"1️⃣ Bot ko apne doosre group me add karke <b>Admin</b> bana dein.\n"
        f"2️⃣ Us group me command bhejein: <code>/setgroup2</code>\n"
        f"<i>(Bot turant us group ko Group 2 ke roop me save kar lega!)</i>\n\n"
        f"Ya fir niche <b>[➕ Group 2 ID Enter Karein]</b> dabayein:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Group 2 ID Enter Karein", callback_data="adm_ask_g2_id")],
        [InlineKeyboardButton("🔄 Refresh Groups", callback_data="adm_manage_groups")],
        [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_refresh")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


async def admin_ask_g2_id_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_GROUP2_ID.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_manage_groups")]])

    await query.message.reply_text(
        "📝 <b>Group 2 ki Chat ID bhejein:</b>\n\n"
        "Apne doosre group ki Telegram Chat ID yahan type karke send karein (jaise: <code>-100xxxxxxxxxx</code>).\n\n"
        "<i>💡 Sabse aasan tarika: Doosre group me bot ko admin banakar us group me <code>/setgroup2</code> likh dein!</i>",
        reply_markup=cancel_btn,
        parse_mode="HTML"
    )


# ────────────────────────────────────────────────────────────
# 7. BANNER CHANGE MENU (No Code Needed!)
# ────────────────────────────────────────────────────────────

async def admin_change_banner_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_BANNER.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_refresh")]])

    text = (
        f"🖼️ <b>BANNER CHANGE KAREIN (No Code Needed!)</b>\n\n"
        f"Apne mobile ki Gallery se jo photo aapko naya Banner banani hai, "
        f"wo photo abhi <b>is chat me Photo ke roop me send kar dein!</b>\n\n"
        f"Bot turant use save kar lega aur abhi se har post me wahi naya banner dikhega. 🚀\n\n"
        f"Agar abhi nahi badalna toh niche Cancel dabayein:"
    )
    await query.message.reply_text(text, reply_markup=cancel_btn, parse_mode="HTML")


# ────────────────────────────────────────────────────────────
# 8. ENROLLED STUDENTS LIST (Direct 1-Click View)
# ────────────────────────────────────────────────────────────

async def admin_list_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    students = db.get_enrolled_list()
    total = len(students)
    if total == 0:
        await query.answer("ℹ️ Abhi koi student enrolled nahi hai.", show_alert=True)
        return

    header = f"📋 <b>ENROLLED STUDENTS LIST</b>\n👥 <b>Total Enrolled:</b> {total}\n"
    divider = "─" * 35 + "\n\n"

    lines = []
    remove_buttons = []

    for idx, s in enumerate(students, start=1):
        name = s.get('full_name', 'Unknown')
        uname = s.get('username', 'N/A')
        uid = s.get('user_id', '')
        time_str = s.get('enrolled_at', '')
        lines.append(f"<b>{idx}.</b> {name} ({uname})\n   🆔 <code>{uid}</code> | 🕒 <code>{time_str}</code>")

        if idx <= 20:
            btn_label = f"❌ Remove {name[:14]} ({uname[:12]})"
            remove_buttons.append([InlineKeyboardButton(btn_label, callback_data=f"del_std_{uid}")])

    remove_buttons.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="adm_refresh")])
    list_markup = InlineKeyboardMarkup(remove_buttons)

    full_text = header + divider + "\n\n".join(lines)
    full_text += "\n\n💡 <i>Kisi student ko nikalne ke liye niche diye gaye <b>[❌ Remove]</b> button dabayein:</i>"

    if len(full_text) < 4000:
        await query.edit_message_text(full_text, reply_markup=list_markup, parse_mode="HTML")
    else:
        file_content = f"TOTAL ENROLLED: {total}\n" + "="*50 + "\n\n"
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
            f"Yeh student list se remove ho gaya hai aur ab <b>dobara enroll kar sakta hai</b>! 🚀",
            parse_mode="HTML"
        )
    else:
        await query.answer("❌ Student list mein nahi mila ya pehle hi remove ho chuka hai.", show_alert=True)


# Total Stats
async def admin_stats_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    b1_count = len(db.get_enrolled_list(config.BATCH_1_NAME))
    b2_count = len(db.get_enrolled_list(config.BATCH_2_NAME))
    total = b1_count + b2_count
    await query.answer(
        f"📊 STATS:\n• {config.BATCH_1_NAME}: {b1_count}\n• {config.BATCH_2_NAME}: {b2_count}\n• Total: {total}",
        show_alert=True
    )


# Student Remove via Text Input
async def admin_ask_remove_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_REMOVE_STUDENT.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_remove")]])

    await query.message.reply_text(
        "❌ <b>Kis Student ko Remove karna chahte hain?</b>\n\n"
        "Aap inme se kuch bhi yahan bhej sakte hain:\n"
        "• <b>Telegram User ID</b> (jaise: <code>8914751355</code>)\n"
        "• <b>Username</b> (jaise: <code>@niistharajput</code>)\n"
        "• <b>Student ka Name</b>\n\n"
        "<i>(Remove hote hi student dobara enroll kar sakega!)</i>",
        reply_markup=cancel_btn,
        parse_mode="HTML"
    )


async def admin_cancel_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    WAITING_FOR_REMOVE_STUDENT.discard(query.from_user.id)
    await query.edit_message_text("❌ Remove cancel kar diya gaya.")


# Broadcast flow
async def admin_ask_broadcast_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_FOR_BROADCAST.add(query.from_user.id)
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="adm_cancel_broadcast")]])

    await query.message.reply_text(
        "📝 <b>Aap sabhi Enrolled Students ko kya message ya payment link bhejna chahte hain?</b>\n\n"
        "Apna poora message yahan type karke send kar dein. Bot use sabhi enrolled students ke private DM me deliver kar dega!\n\n"
        "Agar abhi nahi bhejna toh niche Cancel dabayein:",
        reply_markup=cancel_btn,
        parse_mode="HTML"
    )


async def admin_cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    WAITING_FOR_BROADCAST.discard(query.from_user.id)
    await query.edit_message_text("❌ Broadcast cancel kar diya gaya.")


# Refresh Dashboard
async def admin_refresh_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔄 Refreshing...")

    students_b1 = db.get_enrolled_list(config.BATCH_1_NAME)
    students_b2 = db.get_enrolled_list(config.BATCH_2_NAME)
    total_students = len(students_b1) + len(students_b2)
    groups = db.get_registered_groups(config.GROUP_1_ID, config.GROUP_2_ID)

    g1_txt = groups.get("group_1", {}).get("title", "Main Group") if groups.get("group_1") else "Not Set"
    g2_txt = groups.get("group_2", {}).get("title", "Second Group") if groups.get("group_2") else "Not Set"

    admin_text = (
        f"👑 <b>ADMIN CONTROL PANEL</b>\n"
        f"─────────────────────────\n"
        f"🎯 <b>Batch 1:</b> {config.BATCH_1_NAME} (₹{config.BATCH_1_FEE}) → <code>{len(students_b1)}</code> Enrolled\n"
        f"📰 <b>Batch 2:</b> {config.BATCH_2_NAME} (₹{config.BATCH_2_FEE}) → <code>{len(students_b2)}</code> Enrolled\n"
        f"👥 <b>Total Enrollments:</b> <code>{total_students}</code>\n"
        f"─────────────────────────\n"
        f"📍 <b>Group 1:</b> {g1_txt}\n"
        f"📍 <b>Group 2:</b> {g2_txt}\n\n"
        f"Niche diye gaye <b>Buttons</b> se poora bot control karein 👇"
    )
    await query.edit_message_text(
        admin_text,
        reply_markup=get_admin_dashboard_keyboard(),
        parse_mode="HTML"
    )


# ────────────────────────────────────────────────────────────
# 9. PHOTO HANDLER (Instant Banner Upload via Telegram)
# ────────────────────────────────────────────────────────────

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # Sirf Admin aur Private Chat me
    if user.id != config.ADMIN_ID or chat.type != "private":
        return

    # Photo ki sabse highest resolution wali file
    photo_file = update.message.photo[-1]
    file_id = photo_file.file_id

    # 1. MongoDB Atlas me save karein (Railway restart par bhi safe!)
    db.save_banner_file_id(file_id)

    # 2. Local fallback file me download karein
    try:
        tg_file = await context.bot.get_file(file_id)
        await tg_file.download_to_drive(custom_path=BANNER_PATH)
    except Exception as e:
        logger.warning(f"Could not save local banner.jpg: {e}")

    WAITING_FOR_BANNER.discard(user.id)

    await update.message.reply_photo(
        photo=file_id,
        caption=(
            f"✅ <b>NAYA BANNER SUCCESSFULLY SET HO GAYA!</b> 🎉\n\n"
            f"📌 <b>File ID:</b> <code>{file_id[:25]}...</code>\n\n"
            f"Ab jab bhi aap <b>Group 1</b> ya <b>Group 2</b> me post lagayenge, "
            f"yahi naya banner automatically display hoga!\n\n"
            f"<i>(Kisi bhi code ya command line ki zaroorat nahi hai.)</i>"
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📢 Group me Post Lagayein", callback_data="adm_sendpost")]]),
        parse_mode="HTML"
    )


# ────────────────────────────────────────────────────────────
# 10. MESSAGE HANDLER & 2-WAY SUPPORT CHAT
# ────────────────────────────────────────────────────────────

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    text = (update.message.text or "").strip()

    # Agar Group me koi text message aaya hai -> ignore
    if chat.type != "private":
        return

    # ========================================================
    # CASE A: AGAR ADMIN NE MESSAGE BHEJA HAI
    # ========================================================
    if user.id == config.ADMIN_ID:
        # 1. Group 2 ID enter karne ka input
        if user.id in WAITING_FOR_GROUP2_ID:
            WAITING_FOR_GROUP2_ID.discard(user.id)
            try:
                g2_id = int(text)
                db.save_group(g2_id, f"Group 2 ({g2_id})", slot="group_2")
                await update.message.reply_text(
                    f"✅ <b>Group 2 Successfully Saved!</b>\n\n"
                    f"🆔 Group ID: <code>{g2_id}</code>\n\n"
                    f"Ab aap Group 2 me bhi direct post bhej sakte hain!",
                    reply_markup=get_admin_dashboard_keyboard(),
                    parse_mode="HTML"
                )
            except ValueError:
                await update.message.reply_text("❌ Invalid Group ID. Group ID sirf numbers mein hoti hai (jaise: <code>-1003493006883</code>).", parse_mode="HTML")
            return

        # 2. Check agar Admin kisi Student ke message ko Telegram 'Reply' kar raha hai
        if update.message.reply_to_message:
            rep_msg = update.message.reply_to_message.text or ""
            m = re.search(r"🆔 (?:Telegram )?ID:\s*<code>(\d+)</code>", rep_msg)
            if m:
                target_student_id = int(m.group(1))
                try:
                    await context.bot.send_message(
                        chat_id=target_student_id,
                        text=(
                            f"💬 <b>Admin का जवाब:</b>\n\n"
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

        # 3. Check agar Admin Student Remove ID bhej raha hai
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

        # 4. Check agar Admin Broadcast Message bhej raha hai
        if user.id in WAITING_FOR_BROADCAST:
            WAITING_FOR_BROADCAST.discard(user.id)
            students = db.get_enrolled_list()

            if not students:
                await update.message.reply_text("ℹ️ Koi student enrolled nahi hai.")
                return

            status_msg = await update.message.reply_text(f"⏳ <b>Broadcasting to {len(students)} students...</b>", parse_mode="HTML")
            sent = 0
            failed = 0

            seen_uids = set()
            for s in students:
                target_uid = s.get("user_id")
                if target_uid in seen_uids:
                    continue
                seen_uids.add(target_uid)

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
                f"📨 Successfully Sent: {sent}/{len(seen_uids)}\n"
                f"❌ Blocked/Failed: {failed}",
                parse_mode="HTML"
            )
            return

        return

    # Student private message to bot
    await update.message.reply_text(
        "✅ <b>आपका संदेश Admin तक पहुँचा दिया गया है!</b>\n\n"
        "जल्द ही Admin आपको यहीं Bot के माध्यम से उत्तर देंगे। धैर्य रखने के लिए धन्यवाद! 🙏",
        parse_mode="HTML"
    )

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


# ────────────────────────────────────────────────────────────
# 11. COMMANDS: /setgroup1, /setgroup2, /setbanner, /reply, /remove
# ────────────────────────────────────────────────────────────

async def setgroup1_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if user.id != config.ADMIN_ID:
        return

    # If run inside group
    if chat.type in ["group", "supergroup"]:
        target_id = chat.id
        title = chat.title
    elif context.args and context.args[0].lstrip("-").isdigit():
        target_id = int(context.args[0])
        title = f"Group 1 ({target_id})"
    else:
        await update.message.reply_text(
            "⚠️ <b>Tarika:</b> Is group me <code>/setgroup1</code> likhein ya private me <code>/setgroup1 &lt;Group_ID&gt;</code> bhejein.",
            parse_mode="HTML"
        )
        return

    db.save_group(target_id, title, slot="group_1")
    await update.message.reply_text(
        f"✅ <b>Group 1 Successfully Set!</b>\n\n"
        f"📌 Title: <b>{title}</b>\n"
        f"🆔 ID: <code>{target_id}</code>",
        parse_mode="HTML"
    )


async def setgroup2_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if user.id != config.ADMIN_ID:
        return

    if chat.type in ["group", "supergroup"]:
        target_id = chat.id
        title = chat.title
    elif context.args and context.args[0].lstrip("-").isdigit():
        target_id = int(context.args[0])
        title = f"Group 2 ({target_id})"
    else:
        await update.message.reply_text(
            "⚠️ <b>Tarika:</b> Apne 2nd group me <code>/setgroup2</code> likhein ya private me <code>/setgroup2 &lt;Group_ID&gt;</code> bhejein.",
            parse_mode="HTML"
        )
        return

    db.save_group(target_id, title, slot="group_2")
    await update.message.reply_text(
        f"✅ <b>Group 2 Successfully Set!</b>\n\n"
        f"📌 Title: <b>{title}</b>\n"
        f"🆔 ID: <code>{target_id}</code>\n\n"
        f"Ab aap Group 2 me bhi direct post bhej sakte hain!",
        parse_mode="HTML"
    )


async def setbanner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != config.ADMIN_ID:
        return

    await update.message.reply_text(
        "🖼️ <b>Naya Banner Kaise Badlein:</b>\n\n"
        "Apni Gallery se jo photo aapko banner banani hai, use seedha <b>is chat me Photo send</b> kar dein!\n\n"
        "Bot turant use naya banner set kar dega.",
        parse_mode="HTML"
    )


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
                f"💬 <b>Admin का जवाब:</b>\n\n"
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


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != config.ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Format: <code>/remove &lt;user_id ya @username&gt;</code>\n"
            "Example: <code>/remove 8914751355</code>",
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
# 12. MAIN FUNCTION
# ────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("🚀 Starting Antim Prahar Multi-Batch & Multi-Group Bot...")
    print(f"📌 Admin ID: {config.ADMIN_ID}")
    print("=" * 60)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", start_command))
    app.add_handler(CommandHandler("setgroup1", setgroup1_command))
    app.add_handler(CommandHandler("setgroup2", setgroup2_command))
    app.add_handler(CommandHandler("setbanner", setbanner_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("reply", reply_command))

    # Student Buttons (Support both b1, b2, and legacy patterns)
    app.add_handler(CallbackQueryHandler(yes_enroll_handler, pattern="^(btn_yes_enroll|btn_yes_b1|btn_yes_b2)$"))
    app.add_handler(CallbackQueryHandler(not_interested_handler, pattern="^(btn_not_interested|btn_no_b1|btn_no_b2)$"))
    app.add_handler(CallbackQueryHandler(batch_info_handler, pattern="^btn_batch_info$"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^btn_support$"))

    # Admin: Posting & Groups Menu
    app.add_handler(CallbackQueryHandler(admin_sendpost_menu, pattern="^adm_sendpost$"))
    app.add_handler(CallbackQueryHandler(admin_post_execute, pattern="^adm_post_send_"))

    # Admin: Post Delete Menu
    app.add_handler(CallbackQueryHandler(admin_deletepost_menu, pattern="^adm_deletepost$"))
    app.add_handler(CallbackQueryHandler(admin_del_post_execute, pattern="^adm_del_exec_"))

    # Admin: Groups Manage Menu
    app.add_handler(CallbackQueryHandler(admin_manage_groups_btn, pattern="^adm_manage_groups$"))
    app.add_handler(CallbackQueryHandler(admin_ask_g2_id_btn, pattern="^adm_ask_g2_id$"))

    # Admin: Banner Change
    app.add_handler(CallbackQueryHandler(admin_change_banner_btn, pattern="^adm_change_banner$"))

    # Admin: Enrolled List & Stats
    app.add_handler(CallbackQueryHandler(admin_list_btn, pattern="^(adm_list|adm_list_menu)$"))
    app.add_handler(CallbackQueryHandler(admin_del_student_callback, pattern="^del_std_"))
    app.add_handler(CallbackQueryHandler(admin_stats_btn, pattern="^adm_stats$"))

    # Admin: Student Remove & Broadcast
    app.add_handler(CallbackQueryHandler(admin_ask_remove_btn, pattern="^adm_ask_remove$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_remove, pattern="^adm_cancel_remove$"))
    app.add_handler(CallbackQueryHandler(admin_ask_broadcast_btn, pattern="^adm_ask_broadcast$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_broadcast, pattern="^adm_cancel_broadcast$"))

    # Admin: Refresh
    app.add_handler(CallbackQueryHandler(admin_refresh_btn, pattern="^adm_refresh$"))

    # Photos (Admin sending photo to change banner!)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_upload))

    # Messages (Student to Admin Support + Admin Replies + Broadcast + Input IDs)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))

    print("✅ Bot is fully configured & ready!")
    app.run_polling()

if __name__ == "__main__":
    main()
