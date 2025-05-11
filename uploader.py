import os
import json
import logging
import asyncio
import uuid
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
                          ContextTypes, filters)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

token = "Place your token here"
admin_ids = {place your id here }
required_channels = ["@first channel id (optional)"]
check_channels = True
user_steps = {}
banned_users = set()

def load_json(file_name, default):
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file_name)
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return default
    except Exception as e:
        logger.error(f"خطا در بارگذاری {file_name}: {str(e)}")
        return default

def save_json(file_name, data):
    os.makedirs("data", exist_ok=True)
    file_path = os.path.join("data", file_name)
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"خطا در ذخیره {file_name}: {str(e)}")

def load_admins():
    global admin_ids
    admin_ids = set(load_json("admins.json", [606690587]))

def save_admins():
    save_json("admins.json", list(admin_ids))

def load_channels():
    global required_channels
    required_channels = load_json("channels.json", ["@ChannelOne"])

def save_channels():
    save_json("channels.json", required_channels)

def load_banned_users():
    global banned_users
    banned_users = set(load_json("banned.json", []))

def save_banned_users():
    save_json("banned.json", list(banned_users))

def load_users():
    return set(load_json("users.json", []))

def save_users(users):
    save_json("users.json", list(users))

def load_files():
    return load_json("files.json", [])

def save_files(files):
    save_json("files.json", files)

def load_settings():
    return load_json("settings.json", {"delete_after_seconds": 60})

def save_settings(settings):
    save_json("settings.json", settings)

async def is_user_joined(context, user_id):
    if not check_channels:
        return True
    for channel in required_channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            logger.error(f"خطا در بررسی عضویت کانال {channel}: {str(e)}")
            return False
    return True

def get_start_text():
    path = os.path.join("data", "start.txt")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return f.read()
    return "به ربات خوش آمدید!"

def set_start_text(text):
    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "start.txt"), 'w') as f:
        f.write(text)

async def delete_message_after_delay(context, chat_id, message_id, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"پیام {message_id} در چت {chat_id} بعد از {delay_seconds} ثانیه حذف شد.")
    except Exception as e:
        logger.error(f"خطا در حذف پیام {message_id}: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("شما از ربات بن شده‌اید.")
        return

    users = load_users()
    if user_id not in users:
        users.add(user_id)
        save_users(users)

    args = context.args
    if args and args[0].startswith("getfile"):
        await getfile_handler(update, context)
        return

    if user_id not in admin_ids:
        if not await is_user_joined(context, user_id):
            buttons = [[InlineKeyboardButton(f"کانال {i+1}", url=f"https://t.me/{ch.lstrip('@')}")] for i, ch in enumerate(required_channels)]
            await update.message.reply_text(
                "▫️لطفاً ابتدا در کانال‌های زیر عضو شوید:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await update.message.reply_text("لطفاً لینک فایل را استفاده کنید.")
        return

    keyboard = [["📂 فایل‌های من"], ["☁️ آپلود رسانه ☁️"], ["🗑 حذف فایل"], ["⚙️ پروفایل"],
                ["🔗 کپشن"], ["ورود به پنل مدیریت ⚙️"]]
    await update.message.reply_text(get_start_text(),
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def getfile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if user_id in banned_users:
        await update.message.reply_text("شما از ربات بن شده‌اید.")
        return

    if user_id not in admin_ids and not await is_user_joined(context, user_id):
        buttons = [[InlineKeyboardButton(f"کانال {i+1}", url=f"https://t.me/{ch.lstrip('@')}")] for i, ch in enumerate(required_channels)]
        await update.message.reply_text(
            "▫️لطفاً ابتدا در کانال‌های زیر عضو شوید:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    try:
        params = context.args[0].split('_')
        if len(params) != 3:
            raise ValueError("فرمت لینک نامعتبر است")

        command, ftype, fid = params
        if command != "getfile":
            raise ValueError("دستور نامعتبر است")

        file_types = {'p': 'photo', 'v': 'video', 'm': 'music', 'd': 'document'}
        if ftype not in file_types:
            raise ValueError(f"نوع فایل نامعتبر است: {ftype}")

        files = load_files()
        file_data = next((f for f in files if f["file_id"] == fid and f["type"] == file_types[ftype]), None)
        if not file_data:
            raise KeyError(f"فایل با آیدی {fid} یافت نشد")

        caption = file_data.get("caption", "")
        sent_message = None
        if file_data["type"] == 'photo':
            sent_message = await update.message.reply_photo(photo=file_data["telegram_file_id"], caption=caption)
        elif file_data["type"] == 'video':
            sent_message = await update.message.reply_video(video=file_data["telegram_file_id"], caption=caption)
        elif file_data["type"] == 'music':
            sent_message = await update.message.reply_audio(audio=file_data["telegram_file_id"], caption=caption)
        elif file_data["type"] == 'document':
            sent_message = await update.message.reply_document(document=file_data["telegram_file_id"], caption=caption)

        settings = load_settings()
        delete_after = settings.get("delete_after_seconds", 60)
        warning_time = max(1, delete_after - 15)
        warning_message = (
            f"فایل رو یه جا ذخیره کن، تا {warning_time} ثانیه دیگه پیام پاک می‌شه!"
            if delete_after > 15 else "فوری ذخیره کن، پیام به‌زودی پاک می‌شه!"
        )
        await update.message.reply_text(warning_message)

        if sent_message:
            asyncio.create_task(delete_message_after_delay(context, chat_id, sent_message.message_id, delete_after))

    except Exception as e:
        logger.error(f"خطا در getfile: {str(e)}")
        await update.message.reply_text(f"خطا در دریافت فایل: {str(e)}")

async def show_files(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id=None, page=1):
    viewer_id = update.effective_user.id
    if viewer_id not in admin_ids:
        return

    files = load_files()
    target_id = user_id if user_id else viewer_id
    user_files = [f for f in files if f["user_id"] == str(target_id)]

    per_page = 5
    total_pages = (len(user_files) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_files = user_files[start_idx:end_idx]

    if not page_files:
        text = "هیچ فایلی یافت نشد."
    else:
        text = f"فایل‌های کاربر {target_id} (صفحه {page}/{total_pages}):\n\n"
        for f in page_files:
            size = "نامشخص"
            text += (f"آیدی: {f['file_id']}\nنوع: {f['type']}\n"
                    f"تاریخ آپلود: {f['upload_date']}\nحجم تقریبی: {size}\n"
                    f"کپشن: {f.get('caption', 'ندارد')}\n\n")

    buttons = []
    for f in page_files:
        buttons.append([InlineKeyboardButton(f"حذف {f['file_id']}", callback_data=f"delete_file_{f['file_id']}"),
                       InlineKeyboardButton(f"لینک {f['file_id']}", callback_data=f"link_file_{f['file_id']}")])
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("قبلی", callback_data=f"files_page_{target_id}_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("بعدی", callback_data=f"files_page_{target_id}_{page+1}"))
    nav_buttons.append(InlineKeyboardButton("بازگشت", callback_data="back_to_main"))
    buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_ids:
        return

    text = "کانال‌های اجباری:\n"
    buttons = []
    for channel in required_channels:
        text += f"{channel}\n"
        buttons.append([
            InlineKeyboardButton(f"حذف {channel}", callback_data=f"delete_channel_{channel}"),
            InlineKeyboardButton("بازگشت", callback_data="back_to_admin")
        ])
    buttons.append([InlineKeyboardButton("اضافه کردن کانال", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton("بازگشت به پنل", callback_data="back_to_admin")])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    user_id = update.effective_user.id
    if user_id not in admin_ids:
        return

    if data == "cancel":
        user_steps[user_id] = None
        keyboard = [["📂 فایل‌های من"], ["☁️ آپلود رسانه ☁️"], ["🗑 حذف فایل"], ["⚙️ پروفایل"],
                    ["🔗 کپشن"], ["ورود به پنل مدیریت ⚙️"]]
        await query.message.reply_text("عملیات لغو شد.",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if data.startswith("files_page_"):
        _, target_id, page = data.split("_")
        await show_files(update, context, int(target_id), int(page))
        return

    if data.startswith("delete_file_"):
        file_id = data.split("_")[-1]
        files = load_files()
        files = [f for f in files if f["file_id"] != file_id]
        save_files(files)
        await query.message.reply_text(f"فایل {file_id} حذف شد ✅")
        await show_files(update, context, update.effective_user.id)
        return

    if data.startswith("link_file_"):
        file_id = data.split("_")[-1]
        files = load_files()
        file_data = next((f for f in files if f["file_id"] == file_id), None)
        if file_data:
            bot_username = (await context.bot.get_me()).username
            link = f"https://t.me/{bot_username}?start=getfile_{file_data['type'][0]}_{file_id}"
            await query.message.reply_text(f"لینک جدید: {link}")
        return

    if data.startswith("delete_channel_"):
        channel = data[len("delete_channel_"):]
        global required_channels
        required_channels = [c for c in required_channels if c != channel]
        save_channels()
        await query.message.reply_text(f"کانال {channel} حذف شد ✅")
        await manage_channels(update, context)
        return

    if data == "back_to_admin":
        keyboard = [["📊 آمار کاربران"], ["📨 ارسال همگانی"], ["فروارد همگانی 📩"],
                    ["📄 تغییر پیام استارت"], ["🔁 تغییر وضعیت عضویت اجباری"],
                    ["❌ بن کردن کاربر"], ["✅ رفع مسدودی"], ["👥 لیست کاربران"],
                    ["📂 فایل‌های کاربر"], ["📢 اد کردن کانال"], ["👤 اضافه کردن ادمین"],
                    ["⏰ تغییر زمان حذف"]]
        await query.message.edit_text("به پنل مدیریت خوش آمدید:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if data == "back_to_main":
        keyboard = [["📂 فایل‌های من"], ["☁️ آپلود رسانه ☁️"], ["🗑 حذف فایل"], ["⚙️ پروفایل"],
                    ["🔗 کپشن"], ["ورود به پنل مدیریت ⚙️"]]
        await query.message.edit_text(get_start_text(),
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if data == "add_channel":
        user_steps[user_id] = "add_channel"
        await query.message.reply_text(
            "نام کاربری کانال را وارد کنید (مثل @ChannelName):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
        )
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if user_id in banned_users:
        await update.message.reply_text("شما از ربات بن شده‌اید.")
        return

    if user_id not in admin_ids:
        await update.message.reply_text("لطفاً لینک فایل را استفاده کنید.")
        return

    step = user_steps.get(user_id)

    if step == "set_caption":
        user_steps[user_id] = {"step": "upload", "caption": text}
        await update.message.reply_text(
            "رسانه خود را ارسال کنید (عکس، ویدیو، موزیک یا سند):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
        )
        return

    if step == "delete_file":
        files = load_files()
        file_data = next((f for f in files if f["file_id"] == text and f["user_id"] == str(user_id)), None)
        if file_data:
            files = [f for f in files if f["file_id"] != text]
            save_files(files)
            await update.message.reply_text(f"فایل با آیدی {text} حذف شد ✅")
        else:
            await update.message.reply_text("فایلی با این آیدی یافت نشد.")
        user_steps[user_id] = None
        return

    if step == "add_channel":
        cleaned_text = text.strip()
        if cleaned_text.startswith("@") and len(cleaned_text) > 1:
            global required_channels
            if cleaned_text not in required_channels:
                required_channels.append(cleaned_text)
                save_channels()
                await update.message.reply_text(f"کانال {cleaned_text} اضافه شد ✅")
            else:
                await update.message.reply_text("این کانال قبلاً اضافه شده است.")
        else:
            await update.message.reply_text("لطفاً نام کاربری معتبر کانال وارد کنید (مثل @ChannelName).")
        user_steps[user_id] = None
        return

    if step == "add_admin":
        try:
            new_admin = int(text)
            if new_admin in admin_ids:
                await update.message.reply_text("این کاربر قبلاً ادمین است.")
            else:
                admin_ids.add(new_admin)
                save_admins()
                await update.message.reply_text(f"کاربر {new_admin} به عنوان ادمین اضافه شد ✅")
        except ValueError:
            await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید.")
        user_steps[user_id] = None
        return

    if step == "ban_user":
        try:
            ban_id = int(text)
            if ban_id in admin_ids:
                await update.message.reply_text("نمی‌توانید ادمین را بن کنید!")
            else:
                banned_users.add(ban_id)
                save_banned_users()
                await update.message.reply_text(f"کاربر {ban_id} بن شد ✅")
        except ValueError:
            await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید.")
        user_steps[user_id] = None
        return

    if step == "unban_user":
        try:
            unban_id = int(text)
            if unban_id in banned_users:
                banned_users.remove(unban_id)
                save_banned_users()
                await update.message.reply_text(f"کاربر {unban_id} رفع بن شد ✅")
            else:
                await update.message.reply_text("این کاربر بن نیست.")
        except ValueError:
            await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید.")
        user_steps[user_id] = None
        return

    if step == "show_user_files":
        try:
            target_id = int(text)
            await show_files(update, context, target_id)
        except ValueError:
            await update.message.reply_text("لطفاً یک آیدی عددی معتبر وارد کنید.")
        user_steps[user_id] = None
        return

    if step == "send_broadcast":
        users = load_users()
        sent_count = 0
        for uid in users:
            if int(uid) in banned_users:
                continue
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"خطا در ارسال به {uid}: {str(e)}")
        await update.message.reply_text(f"پیام به {sent_count} کاربر ارسال شد ✅")
        user_steps[user_id] = None
        return

    if step == "forward_broadcast":
        users = load_users()
        sent_count = 0
        for uid in users:
            if int(uid) in banned_users:
                continue
            try:
                await update.message.forward(chat_id=int(uid))
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"خطا در فوروارد به {uid}: {str(e)}")
        await update.message.reply_text(f"پیام به {sent_count} کاربر فوروارد شد ✅")
        user_steps[user_id] = None
        return

    if step == "set_delete_time":
        try:
            seconds = int(text)
            if seconds < 1:
                await update.message.reply_text("لطفاً عدد مثبت وارد کنید.")
            else:
                settings = load_settings()
                settings["delete_after_seconds"] = seconds
                save_settings(settings)
                await update.message.reply_text(f"زمان حذف پیام‌ها به {seconds} ثانیه تنظیم شد ✅")
        except ValueError:
            await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        user_steps[user_id] = None
        return

    if user_id in admin_ids:
        if text == "ورود به پنل مدیریت ⚙️":
            keyboard = [["📊 آمار کاربران"], ["📨 ارسال همگانی"], ["فروارد همگانی 📩"],
                        ["📄 تغییر پیام استارت"], ["🔁 تغییر وضعیت عضویت اجباری"],
                        ["❌ بن کردن کاربر"], ["✅ رفع مسدودی"], ["👥 لیست کاربران"],
                        ["📂 فایل‌های کاربر"], ["📢 اد کردن کانال"], ["👤 اضافه کردن ادمین"],
                        ["⏰ تغییر زمان حذف"]]
            await update.message.reply_text("به پنل مدیریت خوش آمدید:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return

        if text == "📄 تغییر پیام استارت":
            user_steps[user_id] = "change_start"
            await update.message.reply_text(
                "پیام جدید استارت را ارسال کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if step == "change_start":
            set_start_text(text)
            await update.message.reply_text("پیام استارت با موفقیت ذخیره شد ✅")
            user_steps[user_id] = None
            return

        if text == "🔁 تغییر وضعیت عضویت اجباری":
            global check_channels
            check_channels = not check_channels
            status = "فعال" if check_channels else "غیرفعال"
            await update.message.reply_text(f"وضعیت عضویت اجباری: {status}")
            return

        if text == "📊 آمار کاربران":
            users = load_users()
            await update.message.reply_text(f"تعداد کاربران: {len(users)}")
            return

        if text == "📨 ارسال همگانی":
            user_steps[user_id] = "send_broadcast"
            await update.message.reply_text(
                "پیام خود را برای ارسال همگانی وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "فروارد همگانی 📩":
            user_steps[user_id] = "forward_broadcast"
            await update.message.reply_text(
                "پیامی که می‌خواهید فوروارد شود را ارسال کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "❌ بن کردن کاربر":
            user_steps[user_id] = "ban_user"
            await update.message.reply_text(
                "آیدی عددی کاربر را برای بن کردن وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "✅ رفع مسدودی":
            user_steps[user_id] = "unban_user"
            await update.message.reply_text(
                "آیدی عددی کاربر را برای رفع بن وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "👥 لیست کاربران":
            users = sorted(load_users())
            per_page = 10
            page = 1
            total_pages = (len(users) + per_page - 1) // per_page
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_users = users[start_idx:end_idx]

            text = f"صفحه {page} از {total_pages}\nلیست کاربران:\n"
            for uid in page_users:
                text += f"آیدی: {uid}\n"

            buttons = []
            if page > 1:
                buttons.append(InlineKeyboardButton("قبلی", callback_data=f"users_page_{page-1}"))
            if page < total_pages:
                buttons.append(InlineKeyboardButton("بعدی", callback_data=f"users_page_{page+1}"))
            buttons.append(InlineKeyboardButton("بازگشت", callback_data="back_to_admin"))
            reply_markup = InlineKeyboardMarkup([buttons])
            await update.message.reply_text(text, reply_markup=reply_markup)
            return

        if text == "📂 فایل‌های کاربر":
            user_steps[user_id] = "show_user_files"
            await update.message.reply_text(
                "آیدی عددی کاربر را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "📢 اد کردن کانال":
            await manage_channels(update, context)
            return

        if text == "👤 اضافه کردن ادمین":
            if user_id != 606690587:
                await update.message.reply_text("فقط ادمین اصلی می‌تواند ادمین اضافه کند.")
                return
            user_steps[user_id] = "add_admin"
            await update.message.reply_text(
                "آیدی عددی کاربر را برای اضافه کردن به ادمین‌ها وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

        if text == "⏰ تغییر زمان حذف":
            user_steps[user_id] = "set_delete_time"
            settings = load_settings()
            current_time = settings.get("delete_after_seconds", 60)
            await update.message.reply_text(
                f"زمان فعلی حذف پیام‌ها: {current_time} ثانیه\n"
                "تعداد ثانیه جدید را وارد کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
            return

    if text == "📂 فایل‌های من":
        await show_files(update, context)
        return

    if text == "☁️ آپلود رسانه ☁️":
        user_steps[user_id] = "set_caption"
        await update.message.reply_text(
            "کپشن فایل را وارد کنید (یا برای خالی گذاشتن بنویسید 'خالی'):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
        )
        return

    if step and step.get("step") == "upload":
        file = update.message
        file_type = None
        file_id = None

        if file.photo:
            file_id = file.photo[-1].file_id
            file_type = "photo"
        elif file.video:
            file_id = file.video.file_id
            file_type = "video"
        elif file.audio:
            file_id = file.audio.file_id
            file_type = "music"
        elif file.document:
            file_id = file.document.file_id
            file_type = "document"

        if file_type and file_id:
            files = load_files()
            rand_id = str(uuid.uuid4())[:8]
            caption = step.get("caption") if step.get("caption") != "خالی" else ""
            files.append({
                "file_id": rand_id,
                "type": file_type,
                "telegram_file_id": file_id,
                "user_id": str(user_id),
                "caption": caption,
                "upload_date": datetime.now().isoformat()
            })
            save_files(files)
            bot_username = (await context.bot.get_me()).username
            link = f"https://t.me/{bot_username}?start=getfile_{file_type[0]}_{rand_id}"
            await update.message.reply_text(
                f"فایل با موفقیت ذخیره شد ✅\nآیدی فایل: {rand_id}\nلینک دانلود: {link}\nکپشن: {caption if caption else 'ندارد'}")
            user_steps[user_id] = None
        else:
            await update.message.reply_text(
                "لطفاً فقط عکس، ویدیو، موزیک یا سند ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
            )
        return

    if text == "⚙️ پروفایل":
        files = load_files()
        user_files = [f for f in files if f["user_id"] == str(user_id)]
        total = len(user_files)
        await update.message.reply_text(
            f"نام: {update.effective_user.first_name}\nشناسه: {user_id}\nتعداد فایل‌ها: {total}")
        return

    if text == "🔗 کپشن":
        await update.message.reply_text(
            "برای تنظیم کپشن، موقع آپلود رسانه کپشن جدید را وارد کنید.")
        return

    if text == "🗑 حذف فایل":
        user_steps[user_id] = "delete_file"
        await update.message.reply_text(
            "آیدی فایل مورد نظر را ارسال کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel")]])
        )
        return

def main():
    load_admins()
    load_channels()
    load_banned_users()
    load_users()
    load_settings()
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r'^getfile_'), getfile_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__ == '__main__':
    main()
