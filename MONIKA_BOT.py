import telebot
import time
import threading
import os
from datetime import datetime, timezone, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

# ==========================================
# --- YOUR BOT CONFIGURATION ---
# ==========================================
BOT_TOKEN = '8609352944:AAFl3Fyk4CsaLLXjy1b4Pq04I7aMu-3zHZI'
BOT_USERNAME = 'SWIGGY_SECURITY_BOT'
CHANNEL_USERNAME = '@swiggytrick'
ADMIN_PASSWORD = 'MONIKA_BOT'

WARNING_TIMEOUT = 30  # Seconds before warning deletes
MUTE_DURATION = 60    # 1 Minute Penalty

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# --- MEMORY BANKS (Reset on Restart) ---
# ==========================================
tracked_users = {}
known_groups = set()
admin_states = {}
bot_users = set()

# Persistent Admin Storage
ADMINS_FILE = "admins.txt"
authenticated_admins = set()

if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        for line in f:
            if line.strip().isdigit():
                authenticated_admins.add(int(line.strip()))

def save_admin(user_id):
    if user_id not in authenticated_admins:
        authenticated_admins.add(user_id)
        with open(ADMINS_FILE, "a") as f:
            f.write(f"{user_id}\n")

# Helper: Get IST Time
def get_timestamp():
    ist_offset = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist_offset).strftime("%Y-%m-%d %H:%M")

# Helper: Auto-Delete Message
def auto_delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass

# ==========================================
# --- MAIN COMMANDS ---
# ==========================================

@bot.message_handler(commands=['start'], func=lambda message: message.chat.type == 'private')
def send_welcome(message):
    bot_users.add(message.from_user.id)
    welcome_text = (
        f"Thank you for choosing the Security Guardian – your top choice for enhancing "
        f"security in your Telegram community.\n\n"
        f"Ready to strengthen your group's safety? Click the button below! 👇"
    )
    markup = InlineKeyboardMarkup()
    add_url = f"https://t.me/{BOT_USERNAME}?startgroup=true&admin=restrict_members+delete_messages+invite_users+pin_messages+manage_video_chats"
    markup.add(InlineKeyboardButton("➕ Add to Group (With Admin Rights)", url=add_url))
    bot.reply_to(message, welcome_text, reply_markup=markup)
    send_help(message)

@bot.message_handler(commands=['help'], func=lambda message: message.chat.type == 'private')
def send_help(message):
    bot_users.add(message.from_user.id)
    help_text = (
        f"🛠️ **Mona Help Menu** 🛠️\n\n"
        f"**Features Active:**\n"
        f"✅ Professional Profile Change Logging 🔎\n"
        f"✅ 1-Minute Force-Subscribe Penalty 🔇\n"
        f"✅ Smart Admin Panel (Ban/Mute/Broadcast) ⚙️\n"
        f"✅ Global DM Broadcast System 📢\n\n"
        f"**Commands:**\n"
        f"`/search <@username or ID>` - Look up change history.\n"
        f"`/adminpanel <password>` - Login to control panel."
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['search'])
def search_user(message):
    try:
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ **Format Error:** Use `/search @username` or `/search 12345`", parse_mode='Markdown')
            return
            
        target_input = command_parts[1].strip()
        target_id = get_target_id_from_input(target_input)
        
        if not target_id:
            bot.reply_to(message, f"❌ I couldn't find `{target_input}` in memory or Telegram.", parse_mode='Markdown')
            return

        name = "Unknown"
        username_str = ""
        history_text = "No changes found..."

        if target_id in tracked_users:
            user_data = tracked_users[target_id]
            name = user_data['current']['first']
            user_handle = user_data['current']['user']
            if user_handle and user_handle != "None":
                username_str = f" (@{user_handle})"
            if user_data['history']:
                history_text = "\n\n".join(user_data['history'])
        else:
            try:
                chat = bot.get_chat(target_id)
                name = chat.first_name or "Unknown"
                if chat.username:
                    username_str = f" (@{chat.username})"
            except Exception:
                pass

        response_text = f"**User ID:** `{target_id}`\n**Name:** {name}{username_str}\n\n{history_text}"
        bot.reply_to(message, response_text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# ==========================================
# --- ADMIN PANEL LOGIC ---
# ==========================================

def show_admin_panel(message):
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("🚫 Ban", callback_data="admin_global_ban"),
               InlineKeyboardButton("✅ Unban", callback_data="admin_global_unban"))
    markup.row(InlineKeyboardButton("🔇 Mute", callback_data="admin_global_mute"),
               InlineKeyboardButton("🔊 Unmute", callback_data="admin_global_unmute"))
    markup.row(InlineKeyboardButton("👋 Force Leave", callback_data="admin_force_leave"),
               InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"))
    markup.row(InlineKeyboardButton("❌ Close Panel", callback_data="admin_close"))
    bot.reply_to(message, "⚙️ **Secure Admin Panel**\nSelect an action:", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['adminpanel'], func=lambda message: message.chat.type == 'private')
def admin_login(message):
    user_id = message.from_user.id
    parts = message.text.split()
    
    if len(parts) > 1 and parts[1] == ADMIN_PASSWORD:
        save_admin(user_id)
        bot.reply_to(message, "🔓 **Login Successful.** You are now permanently recognized as an admin.")
        show_admin_panel(message)
    elif user_id in authenticated_admins:
        show_admin_panel(message)
    else:
        bot.reply_to(message, "❌ **Access Denied.** Usage: `/adminpanel <password>`", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callback(call):
    user_id = call.from_user.id
    action = call.data

    if action == "admin_close":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    # Set state and prompt user
    prompts = {
        "admin_global_ban": ("🚫 **Global Ban Mode**", "Reply with @username or ID to ban."),
        "admin_global_unban": ("✅ **Global Unban Mode**", "Reply with @username or ID to unban."),
        "admin_global_mute": ("🔇 **Global Mute Mode**", "Reply with @username or ID to mute."),
        "admin_global_unmute": ("🔊 **Global Unmute Mode**", "Reply with @username or ID to unmute."),
        "admin_force_leave": ("👋 **Force Leave Mode**", "Reply with group @username."),
        "admin_broadcast": ("📢 **Broadcast Mode**", f"Reply with message for {len(bot_users)} users.")
    }
    
    if action in prompts:
        admin_states[user_id] = action
        title, desc = prompts[action]
        bot.edit_message_text(f"{title}\n\n{desc}", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

# Helper: Resolve Username to ID
def get_target_id_from_input(text):
    clean = text.strip()
    # Check if number
    if clean.lstrip('-').isdigit():
        return int(clean)
    # Check memory
    search = clean.replace('@', '').lower()
    for uid, data in tracked_users.items():
        if data['current']['user'] and data['current']['user'].lower() == search:
            return uid
    # Check Telegram Global
    try:
        q = clean if clean.startswith('@') else '@' + clean
        return bot.get_chat(q).id
    except:
        return None

# Handle Admin Inputs
@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.from_user.id in admin_states)
def handle_admin_action(message):
    uid = message.from_user.id
    action = admin_states[uid]
    text = message.text.strip()
    
    # Broadcast is special
    if action == "admin_broadcast":
        success, fail = 0, 0
        status = bot.reply_to(message, f"⏳ Sending to {len(bot_users)} users...")
        for target in bot_users:
            try:
                bot.send_message(target, f"📢 **Announcement**\n\n{text}", parse_mode='Markdown')
                success += 1
            except: fail += 1
        bot.edit_message_text(f"✅ **Sent:** {success} | **Failed:** {fail}", message.chat.id, status.message_id, parse_mode='Markdown')
        del admin_states[uid]
        return

    # Force Leave is special
    if action == "admin_force_leave":
        try:
            bot.leave_chat(bot.get_chat(text).id)
            bot.reply_to(message, f"✅ Left {text}")
        except Exception as e:
            bot.reply_to(message, f"❌ Failed: {e}")
        del admin_states[uid]
        return

    # For Ban/Mute/Unban/Unmute
    target_id = get_target_id_from_input(text)
    if not target_id:
        bot.reply_to(message, "❌ User not found. Use ID.")
        del admin_states[uid]
        return

    success, fail = 0, 0
    status = bot.reply_to(message, f"⏳ Processing on {len(known_groups)} groups...")
    
    for gid in known_groups:
        try:
            if action == "admin_global_ban":
                bot.ban_chat_member(gid, target_id)
            elif action == "admin_global_unban":
                bot.unban_chat_member(gid, target_id, only_if_banned=True)
            elif action == "admin_global_mute":
                bot.restrict_chat_member(gid, target_id, permissions=ChatPermissions(can_send_messages=False))
            elif action == "admin_global_unmute":
                bot.restrict_chat_member(gid, target_id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True))
            success += 1
        except:
            fail += 1

    bot.edit_message_text(f"✅ **Done.**\nSuccess: {success}\nFailed/Not Admin: {fail}", message.chat.id, status.message_id, parse_mode='Markdown')
    del admin_states[uid]

# ==========================================
# --- GROUP SCANNER & SECURITY ---
# ==========================================

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'video', 'sticker', 'document', 'new_chat_members'])
def group_scanner(message):
    if message.chat.type == 'private':
        bot_users.add(message.from_user.id)
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    known_groups.add(chat_id)

    # 1. Profile Tracking
    cur_first = message.from_user.first_name or "Unknown"
    cur_user = message.from_user.username or "None"
    
    if user_id not in tracked_users:
        tracked_users[user_id] = {'current': {'first': cur_first, 'user': cur_user}, 'history': []}
    else:
        mem = tracked_users[user_id]
        logs = []
        if mem['current']['first'] != cur_first:
            logs.append(f"🔎 Name Change | {get_timestamp()}\n   ↳ {mem['current']['first']} > {cur_first}")
            mem['current']['first'] = cur_first
        if mem['current']['user'] != cur_user:
            logs.append(f"🔎 Handle Change | {get_timestamp()}\n   ↳ @{mem['current']['user']} > @{cur_user}")
            mem['current']['user'] = cur_user
            
        if logs:
            for log in logs: mem['history'].append(log)
            hist_txt = "\n\n".join(mem['history'][-5:])
            bot.send_message(chat_id, f"**User ID:** `{user_id}`\n**Name:** {cur_first}\n\n**Change History**\n{hist_txt}", parse_mode='Markdown')

    # 2. Force Subscribe Check
    try:
        status = bot.get_chat_member(CHANNEL_USERNAME, user_id).status
        if status not in ['member', 'administrator', 'creator']:
            try:
                bot.delete_message(chat_id, message.message_id)
                mute_until_ts = int(time.time()) + MUTE_DURATION
                bot.restrict_chat_member(chat_id, user_id, until_date=mute_until_ts, permissions=ChatPermissions(can_send_messages=False))
            except:
                return # Bot not admin, ignore
            
            # Format Unmute Time specifically to match the image format
            ist_offset = timezone(timedelta(hours=5, minutes=30))
            unmute_time_str = datetime.fromtimestamp(mute_until_ts, ist_offset).strftime("%d/%m/%Y %H:%M:%S")

            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("📣 Subscribe to channel", url=f"https://t.me/{CHANNEL_USERNAME.replace('@','')}"))
            markup.add(InlineKeyboardButton("✅ OK | I subscribed", callback_data=f"verify_{user_id}"))
            
            msg_text = (
                f"**Error**\n"
                f"Deleted message\n\n"
                f"[{cur_first}](tg://user?id={user_id}) [`{user_id}`] to be accepted in the group, "
                f"please subscribe to [our channel](https://t.me/{CHANNEL_USERNAME.replace('@', '')}). "
                f"Once joined, click the button below.\n\n"
                f"**Action:** Muted 🔇 until {unmute_time_str}."
            )

            # Added disable_web_page_preview=True to keep it clean
            msg = bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode='Markdown', disable_web_page_preview=True)
            threading.Timer(WARNING_TIMEOUT, auto_delete_message, args=[chat_id, msg.message_id]).start()
    except Exception as e:
        print(f"Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_'))
def verify(call):
    if call.from_user.id != int(call.data.split('_')[1]):
        bot.answer_callback_query(call.id, "Not your button!", show_alert=True)
        return
    try:
        if bot.get_chat_member(CHANNEL_USERNAME, call.from_user.id).status in ['member', 'creator', 'administrator']:
            bot.answer_callback_query(call.id, "Verified! Wait for mute to expire.", show_alert=True)
            bot.delete_message(call.message.chat.id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "Join the channel first!", show_alert=True)
    except: pass

# ==========================================
# --- CONNECTION FIX & STARTUP ---
# ==========================================
print("🔄 Cleaning up old connections...")
try:
    bot.remove_webhook()
    time.sleep(1)
except: pass

print("✅ Mona Security Bot is ONLINE.")
# This line keeps the bot alive and ignores timeout errors
bot.infinity_polling(timeout=10, long_polling_timeout=5)
            
