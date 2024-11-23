import os
import time
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, CallbackQueryHandler, filters
import yt_dlp as youtube_dl

# توکن ربات تلگرام
TELEGRAM_BOT_TOKEN = '7812571905:AAEJBxXurS4WN0ZiIF9a-hyvKgsJGaNnGOg'
ADMIN_CHAT_ID = 7443354922  # آیدی تلگرام ادمین (سازنده ربات)

# پوشه دانلود
DOWNLOAD_FOLDER = 'downloads/'

# نگهداری وضعیت دانلود برای هر کاربر
downloads_in_progress = {}
cancel_download_flags = {}  # نگهداری وضعیت کنسل شدن دانلود توسط کاربر
user_status = {}  # وضعیت کاربر (یوتیوب یا اینستاگرام)

# ایجاد پوشه دانلود در صورت عدم وجود
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# تابع برای ارسال پیام‌های خطا فقط به ادمین (سازنده ربات)
async def send_error_to_admin(context, error_message):
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f'⚠️ خطا رخ داد: {error_message}')
    except Exception as e:
        print(f'خطا در ارسال پیام به ادمین: {e}')

# نمایش پیشرفت دانلود به کاربر
def progress_hook(d, update, context, user_id):
    if user_id not in downloads_in_progress:
        return  # اگر کاربر دانلود را لغو کرده است

    if cancel_download_flags.get(user_id):
        raise Exception("دانلود کنسل شد.")  # اگر کاربر دانلود را لغو کرده باشد، دانلود را متوقف کنید.

    if d['status'] == 'downloading':
        percent = d['_percent_str']
        speed = d['_speed_str']
        eta = d['eta']
        message = f"⬇️ دانلود: {percent} - سرعت: {speed}/s - زمان تخمینی: {eta}s"
        context.bot.send_message(chat_id=update.message.chat_id, text=message)

# تابع برای دانلود ویدیو از یوتیوب
async def download_video(url, update, context):
    user_id = update.message.chat_id

    if user_id in downloads_in_progress and downloads_in_progress[user_id] is not None:
        await update.message.reply_text("⚠️ دانلود دیگری در حال انجام است. لطفاً صبر کنید یا آن را متوقف کنید.")
        return

    downloads_in_progress[user_id] = True
    cancel_download_flags[user_id] = False  # تنظیم پرچم عدم لغو دانلود

    try:
        # گزینه‌های دانلود با yt-dlp
        ydl_opts = {
            'outtmpl': DOWNLOAD_FOLDER + '%(title)s.%(ext)s',
            'format': 'best',
            'noplaylist': True,
            'progress_hooks': [lambda d: progress_hook(d, update, context, user_id)],
            'concurrent_fragment_downloads': 5,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(result)
            return file_path
    except Exception as e:
        if cancel_download_flags.get(user_id):
            await update.message.reply_text("⛔ دانلود توسط کاربر لغو شد.")
        else:
            await send_error_to_admin(context, f'خطا در دانلود ویدیو: {e}')
        return None
    finally:
        downloads_in_progress[user_id] = None  # وضعیت دانلود پایان یافت

# تابع دانلود ویدیو از اینستاگرام
async def download_instagram_video(url, update, context):
    user_id = update.message.chat_id

    if user_id in downloads_in_progress and downloads_in_progress[user_id] is not None:
        await update.message.reply_text("⚠️ دانلود دیگری در حال انجام است. لطفاً صبر کنید یا آن را متوقف کنید.")
        return

    downloads_in_progress[user_id] = True
    cancel_download_flags[user_id] = False  # تنظیم پرچم عدم لغو دانلود

    try:
        # گزینه‌های دانلود با yt-dlp برای اینستاگرام
        ydl_opts = {
            'outtmpl': DOWNLOAD_FOLDER + '%(title)s.%(ext)s',
            'format': 'best',
            'progress_hooks': [lambda d: progress_hook(d, update, context, user_id)],
            'concurrent_fragment_downloads': 5,
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(result)
            return file_path
    except Exception as e:
        if cancel_download_flags.get(user_id):
            await update.message.reply_text("⛔ دانلود توسط کاربر لغو شد.")
        else:
            await send_error_to_admin(context, f'خطا در دانلود ویدیو: {e}')
        return None
    finally:
        downloads_in_progress[user_id] = None  # وضعیت دانلود پایان یافت

# ارسال فایل دانلود شده به کاربر و حذف فایل پس از ارسال
async def send_file(update, context, file_path):
    try:
        if not os.path.exists(file_path):
            await update.message.reply_text('❌ خطا: فایل یافت نشد.')
            return

        # ارسال فایل ویدیویی یا مستندات
        if file_path.endswith(('.mp4', '.mkv', '.avi')):
            with open(file_path, 'rb') as f:
                await update.message.reply_video(video=f)
            await update.message.reply_text('🎉 ویدیو با موفقیت ارسال شد!')
        else:
            with open(file_path, 'rb') as f:
                await update.message.reply_document(document=f)
            await update.message.reply_text('🎉 فایل با موفقیت ارسال شد!')

        # حذف فایل از حافظه سرور پس از ارسال
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        await send_error_to_admin(context, f'خطا در ارسال فایل: {e}')

# هندلر برای دریافت لینک‌ها و مدیریت دانلود
async def handle_message(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    message_text = update.message.text

    # بررسی وضعیت کاربر
    if user_id in user_status:
        if user_status[user_id] == 'youtube':
            await update.message.reply_text('⬇️ در حال آماده‌سازی دانلود ویدیو از یوتیوب...')
            start_time = time.time()
            file_path = await download_video(message_text, update, context)
            end_time = time.time()

            if file_path:
                download_duration = end_time - start_time
                await update.message.reply_text(f'✅ ویدیو با موفقیت دانلود شد! ⏳ زمان دانلود: {download_duration:.2f} ثانیه.')
                await send_file(update, context, file_path)

        elif user_status[user_id] == 'instagram':
            await update.message.reply_text('⬇️ در حال آماده‌سازی دانلود از اینستاگرام...')
            start_time = time.time()
            file_path = await download_instagram_video(message_text, update, context)
            end_time = time.time()

            if file_path:
                download_duration = end_time - start_time
                await update.message.reply_text(f'✅ پست با موفقیت دانلود شد! ⏳ زمان دانلود: {download_duration:.2f} ثانیه.')
                await send_file(update, context, file_path)

        # پاک کردن وضعیت کاربر پس از دانلود
        del user_status[user_id]

    else:
        await update.message.reply_text('❌ لطفاً ابتدا یکی از دکمه‌ها را انتخاب کنید.')

# هندلر برای دکمه‌های شیشه‌ای و مدیریت توقف و کنسل کردن دانلود
async def button_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.message.chat_id

    if query.data == 'youtube':
        # تنظیم وضعیت کاربر به یوتیوب
        user_status[user_id] = 'youtube'
        await query.edit_message_text(text="📺 لطفاً لینک ویدیوی یوتیوب خود را ارسال کنید:")

    elif query.data == 'instagram':
        # تنظیم وضعیت کاربر به اینستاگرام
        user_status[user_id] = 'instagram'
        await query.edit_message_text(text="📸 لطفاً لینک پست اینستاگرام خود را ارسال کنید:")

    elif query.data == 'cancel_download':
        # این قسمت برای لغو دانلود استفاده می‌شود
        cancel_download_flags[user_id] = True  # پرچم لغو دانلود به true تنظیم می‌شود
        await query.edit_message_text(text="❌ دانلود کنسل شد.")

    elif query.data == 'support':
        await query.edit_message_text(
            text="🔧 **پشتیبانی ربات**:\n\n"
                 "👤 سازنده: اردلان شعبان زاده\n"
                 "📞 شماره تماس: 09128232615\n"
                 "✉️ آیدی تلگرام: @Ardalan_1377\n"
                 "📧 آدرس ایمیل: ardalanshabanzadeh35@gmail.com"
        )

# هندلر برای نمایش راهنما در دستور /help
async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "❓ **راهنمای ربات**:\n\n"
        "📥 این ربات به شما اجازه می‌دهد ویدیوهای یوتیوب و پست‌های اینستاگرام را دانلود کنید.\n\n"
        "🔹 *دستورات*:\n"
        "/start - شروع ربات\n"
        "/help - نمایش راهنما\n\n"
        "🔧 **نحوه استفاده**:\n"
        "1️⃣ دکمه یوتیوب یا اینستاگرام را انتخاب کنید.\n"
        "2️⃣ لینک ویدیو یا پست مورد نظر را ارسال کنید.\n"
        "3️⃣ ربات ویدیو یا پست مورد نظر را دانلود و برای شما ارسال می‌کند.\n\n"
        "📞 *پشتیبانی*: اگر مشکلی داشتید با [سازنده](https://t.me/Ardalan_1377) تماس بگیرید."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# هندلر برای شروع ربات با دکمه‌های شیشه‌ای
async def start(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎥 شروع دانلود از یوتیوب", callback_data='youtube')],
        [InlineKeyboardButton("📸 شروع دانلود از اینستاگرام", callback_data='instagram')],
        [InlineKeyboardButton("❌ کنسل کردن دانلود", callback_data='cancel_download')],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data='support')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('به ربات دانلود خوش آمدید! لطفاً پلتفرم خود را انتخاب کنید:', reply_markup=reply_markup)

# تابع اصلی برای راه‌اندازی ربات
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # هندلر برای شروع ربات
    application.add_handler(CommandHandler('start', start))

    # هندلر برای دستور /help
    application.add_handler(CommandHandler('help', help_command))

    # هندلر برای دریافت لینک‌ها و پیام‌ها
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # هندلر برای مدیریت دکمه‌های شیشه‌ای
    application.add_handler(CallbackQueryHandler(button_callback))

    # شروع ربات
    application.run_polling()

if __name__ == '__main__':
    main()
