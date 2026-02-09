import asyncio
import logging
import os
import re
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import API_TOKEN, API_ID, API_HASH, setup_cookies
from downloader import download_video, download_spotify, upload_to_filehost
from database import is_user_allowed, add_user, migrate_from_file, get_user_count

# Setup cookies from environment variable on startup
setup_cookies()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

import random

# ... imports ...

# Initialize bot and dispatcher
if not API_TOKEN:
    logging.critical("Error: API_TOKEN is not set! Please check your environment variables.")
    sys.exit(1)

if not API_ID or not API_HASH:
    logging.warning("Warning: API_ID or API_HASH not set. Large file uploads via Pyrogram will not work.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Store user URLs temporarily: {user_id: url}
user_urls = {}


async def check_auth(message: types.Message):
    # Admin is always allowed
    if message.from_user.id == 177036997:
        return True

    if not is_user_allowed(message.from_user.id):
        jokes = [
            "⛔️ **Доступ запрещен!**\nМой создатель не разрешал мне разговаривать с незнакомцами.",
            "🕵️ **Вы кто?**\nВас нет в списках VIP. Предъявите пропуск или коробку конфет администратору.",
            "🤖 **Бип-буп!**\nМои сенсоры не опознают вас. Попробуйте перезагрузить вселенную.",
            "🚪 **Тук-тук!**\n— Кто там?\n— Никого. Доступа нет.",
            "🚫 **Error 403**\nВы не авторизованы. Но вы держитесь там, всего вам доброго!",
        ]
        await message.answer(random.choice(jokes))
        logging.warning(f"Unauthorized access attempt by user {message.from_user.id} (@{message.from_user.username})")
        return False
    return True

@dp.message(Command("add"))
async def cmd_add_user(message: types.Message):
    # Admin check
    if message.from_user.id != 177036997:
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer("ℹ️ **Использование:** `/add @username`")
        return

    username = args[1]
    if username.startswith("@"):
        username = username[1:]

    status_msg = await message.answer(f"🔎 Ищу пользователя @{username}...")

    try:
        # Run resolver.py as a separate process
        python_executable = sys.executable
        process = await asyncio.create_subprocess_exec(
            python_executable, "resolver.py", username,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            try:
                new_user_id = int(stdout.decode().strip())

                # Check if already exists
                if is_user_allowed(new_user_id):
                    await status_msg.edit_text(f"⚠️ Пользователь @{username} (ID: {new_user_id}) уже есть в списке.")
                    return

                # Add to database
                if add_user(new_user_id, username, added_by="admin"):
                    await status_msg.edit_text(f"✅ Пользователь @{username} (ID: `{new_user_id}`) успешно добавлен!")
                else:
                    await status_msg.edit_text(f"❌ Ошибка добавления пользователя в базу данных.")
            except ValueError:
                 await status_msg.edit_text(f"❌ Ошибка чтения ID. Ответ: {stdout.decode()}")
        else:
            error_msg = stderr.decode().strip()
            await status_msg.edit_text(f"❌ Не удалось найти пользователя.\nОшибка: {error_msg}")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Системная ошибка: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if not await check_auth(message):
        return

    welcome_text = (
        f"👋 Йоу, {message.from_user.first_name}!\n\n"
        "Я умею скачивать видео практически откуда угодно:\n\n"
        "📺 YouTube (до 1080p)\n"
        "🎵 TikTok\n"
        "📸 Instagram\n"
        "🐦 Twitter/X\n"
        "🎧 Spotify\n"
        "...и ещё 1800+ сайтов!\n\n"
        "Просто кинь мне ссылку и я всё сделаю 🚀"
    )
    await message.answer(welcome_text)
    logging.info(f"User {message.from_user.id} started the bot")

def get_quality_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="1080p", callback_data="quality_1080")
    builder.button(text="720p", callback_data="quality_720")
    builder.button(text="360p", callback_data="quality_360")
    builder.button(text="Audio Only", callback_data="quality_audio")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(Command("kir"))
async def cmd_kir(message: types.Message):
    try:
        if not os.path.exists("wishes.txt"):
             await message.answer("Файл с пожеланиями не найден. Грусть.")
             return

        with open("wishes.txt", "r", encoding="utf-8") as f:
            wishes = f.readlines()
        
        if wishes:
            wish = random.choice(wishes).strip()
            await message.answer(f"✨ {wish}")
        else:
            await message.answer("Шутки кончились, иди работай!")
    except Exception as e:
        logging.error(f"Error reading wishes: {e}")
        await message.answer("Что-то пошло не так при чтении пожеланий.")

@dp.message(F.text.lower() == "кир")
async def secret_code_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Check if already allowed
    if is_user_allowed(user_id):
        await message.answer("Ты уже в клубе, бро! 😎")
        return

    # Add to database
    if add_user(user_id, username, added_by="secret_code"):
        await message.answer("✅ Доступ получен! Добро пожаловать в элитный клуб.\nТеперь можешь скидывать ссылки.")
        logging.info(f"User {username} ({user_id}) added via secret code.")

        # Notify admin
        try:
            await bot.send_message(177036997, f"🆕 Пользователь @{username} ({user_id}) активировал секретный код!")
        except:
            pass
    else:
        await message.answer("Что-то пошло не так при активации кода.")

@dp.message(F.text)
async def handle_url(message: types.Message):
    if not await check_auth(message):
        return

    url = message.text.strip()
    user_id = message.from_user.id
    username = message.from_user.username
    logging.info(f"Received URL from {user_id} (@{username}): {url}")

    # Simple URL validation
    if not url.startswith(("http://", "https://")):
        await message.answer("Пожалуйста, отправь корректную ссылку.")
        return

    # Check if YouTube
    if "youtube.com" in url or "youtu.be" in url:
        user_urls[user_id] = url
        await message.answer(
            "Выбери качество видео:",
            reply_markup=get_quality_keyboard()
        )
    # Check if Instagram
    elif "instagram.com" in url:
        await message.answer("Скачиваю видео с Instagram...")
        await process_download(message, url, quality="best")
    # Check if Spotify
    elif "spotify.com" in url:
        await message.answer("🎧 Скачиваю музыку со Spotify...")
        await process_download(message, url, quality="spotify")
    # Check if TikTok
    elif "tiktok.com" in url or "vm.tiktok.com" in url:
        await message.answer("🎵 Скачиваю видео с TikTok...")
        await process_download(message, url, quality="best")
    # Check if Twitter/X
    elif "twitter.com" in url or "x.com" in url:
        await message.answer("🐦 Скачиваю видео с Twitter/X...")
        await process_download(message, url, quality="best")
    else:
        # Try generic download (yt-dlp supports 1000+ sites)
        await message.answer("🔄 Скачиваю видео...")
        await process_download(message, url, quality="best")

@dp.callback_query(F.data.startswith("quality_"))
async def handle_quality_selection(callback: types.CallbackQuery):
    quality = callback.data.split("_")[1]
    user_id = callback.from_user.id
    url = user_urls.get(user_id)

    if not url:
        await callback.message.answer("Ссылка устарела. Отправь её снова.")
        await callback.answer()
        return

    await callback.message.edit_text(f"Выбрано качество: {quality}. Скачиваю...")
    
    from aiogram.exceptions import TelegramBadRequest
    try:
        await callback.answer()
    except TelegramBadRequest:
        pass
    await process_download(callback.message, url, quality)

def get_format_str(quality):
    if quality == "1080":
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    elif quality == "720":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif quality == "360":
        return "bestvideo[height<=360]+bestaudio/best[height<=360]"
    elif quality == "audio":
        return "bestaudio/best"
    elif quality == "best":
        return "best"
    return "best"

async def process_download(message: types.Message, url: str, quality: str):
    global download_semaphore
    
    logging.info(f"Processing download for URL: {url} with quality: {quality} from user {message.chat.id}")

    # Notify if queue is full
    if download_semaphore.locked():
        await message.answer("⏳ **Бот занят другим скачиванием.**\nВы добавлены в очередь, пожалуйста подождите...")

    async with download_semaphore:
        try:
            # Progress update logic
            last_edit_time = 0
            
            def progress_handler(d):
                nonlocal last_edit_time
                import time
                current_time = time.time()
                
                # Update every 3 seconds to avoid flood limits
                if current_time - last_edit_time < 3:
                    return

                percent = d.get('_percent_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                speed = d.get('_speed_str', 'N/A')
                
                # Clean up ANSI codes if present
                percent = re.sub(r'\x1b\[[0-9;]*m', '', str(percent))
                eta = re.sub(r'\x1b\[[0-9;]*m', '', str(eta))
                speed = re.sub(r'\x1b\[[0-9;]*m', '', str(speed))
                
                text = f"📥 **Скачиваю:** {percent}\n🚀 **Скорость:** {speed}\n⏳ **Осталось:** {eta}"
                
                try:
                    # Schedule async update in the main loop
                    asyncio.run_coroutine_threadsafe(
                        message.edit_text(text),
                        asyncio.get_running_loop()
                    )
                    last_edit_time = current_time
                except Exception:
                    pass

            if quality == "spotify":
                file_path = await download_spotify(url)
            else:
                format_str = get_format_str(quality)
                # Pass progress_handler only for video downloads
                file_path = await download_video(url, format_str, progress_callback=progress_handler)
            
            if not file_path or not os.path.exists(file_path):
                logging.error(f"Download failed: file not found at {file_path}")
                await message.answer("Не удалось скачать файл. Возможно, он недоступен.")
                return

            # Check file size (Telegram limit ~50MB for bots)
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / 1024 / 1024
            logging.info(f"File downloaded: {file_path}, size: {file_size_mb:.1f} MB")

            # Telegram limit is 2GB with Pyrogram API
            telegram_limit = 2 * 1024 * 1024 * 1024  # 2GB

            # For files > 2GB, upload to file host
            if file_size > telegram_limit:
                await message.answer(f"📦 Файл очень большой ({file_size_mb:.1f} MB).\nЗагружаю на файлообменник...")

                filehost_url = await upload_to_filehost(file_path)

                if filehost_url:
                    await message.answer(
                        f"✅ **Файл загружен!**\n\n"
                        f"📥 [Скачать файл]({filehost_url})\n\n"
                        f"⚠️ Ссылка временная",
                        parse_mode="Markdown"
                    )
                else:
                    await message.answer("❌ Не удалось загрузить файл на файлообменник.")

                # Cleanup
                if os.path.exists(file_path):
                    os.remove(file_path)
                return

            # Use Pyrogram (uploader.py) for files > 40MB (up to 2GB)
            large_file_threshold = 40 * 1024 * 1024 if (API_ID and API_HASH) else 49 * 1024 * 1024

            if file_size > large_file_threshold:
                await message.answer(f"Файл ({file_size / 1024 / 1024:.1f} MB) большой.\n"
                                     "Скачиваю ваш файлик, чуть-чуть подожди, дорогой ...")
                
                try:
                    # Run uploader.py as a separate process
                    import subprocess
                    
                    # Use the same python interpreter
                    python_executable = sys.executable
                    
                    process = await asyncio.create_subprocess_exec(
                        python_executable, "uploader.py", str(message.chat.id), file_path,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    # Wait for it to finish and read stdout
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        
                        line_str = line.decode().strip()
                        if "Progress:" in line_str:
                            try:
                                await message.edit_text(f"📤 **Загрузка в Telegram:** {line_str.split(': ')[1]}")
                            except Exception:
                                pass
                    
                    await process.wait()
                    
                    if process.returncode == 0:
                        logging.info("Large file upload completed successfully via uploader.py")
                        await message.answer("✅ Загрузка завершена!")
                    else:
                        stderr_data = await process.stderr.read()
                        error_msg = stderr_data.decode().strip()
                        logging.error(f"Uploader error: {error_msg}")
                        await message.answer(f"Ошибка при загрузке: {error_msg}")
                
                except Exception as e:
                    logging.error(f"Subprocess error: {e}")
                    await message.answer(f"Не удалось запустить загрузчик: {e}")
                
                # Cleanup
                if os.path.exists(file_path):
                    os.remove(file_path)
                return

            await message.answer("Загружаю видео в Telegram...")
            
            video_file = FSInputFile(file_path)
            try:
                caption_text = f"Скачано с помощью @{BOT_USERNAME}" if BOT_USERNAME else "Скачано ботом"
                
                # Retry logic for upload
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if quality in ["audio", "spotify"]:
                             await message.answer_audio(
                                video_file,
                                caption=f"🎧 {caption_text}",
                                request_timeout=1200
                             )
                        else:
                             await message.answer_video(
                                video_file,
                                caption=f"📹 {caption_text}",
                                supports_streaming=True,
                                request_timeout=1200
                             )
                        break # Success
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        logging.warning(f"Upload attempt {attempt + 1} failed: {e}. Retrying...")
                        await asyncio.sleep(2)

            except Exception as e:
                await message.answer(f"Ошибка при отправке файла: {e}")
            
            # Cleanup
            if os.path.exists(file_path):
                os.remove(file_path)
                logging.info(f"Cleaned up file: {file_path}")
        except Exception as e:
            logging.error(f"Error processing download: {e}", exc_info=True)
            await message.answer("Произошла ошибка при обработке видео.")

async def cleanup_downloads():
    """Periodically clean up the downloads directory."""
    while True:
        try:
            download_dir = "downloads"
            if os.path.exists(download_dir):
                current_time = asyncio.get_running_loop().time()
                for filename in os.listdir(download_dir):
                    file_path = os.path.join(download_dir, filename)
                    # Delete files older than 1 hour (3600 seconds)
                    if os.path.isfile(file_path):
                        file_age = os.path.getmtime(file_path)
                        # Check if file is older than 1 hour
                        import time
                        if time.time() - file_age > 3600:
                            try:
                                os.remove(file_path)
                                logging.info(f"Deleted old file: {file_path}")
                            except Exception as e:
                                logging.error(f"Error deleting file {file_path}: {e}")
            
            # Wait for 10 minutes before next check
            await asyncio.sleep(600)
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
            await asyncio.sleep(600)

from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

# Global variable for bot username
BOT_USERNAME = None
# Semaphore to limit concurrent downloads
download_semaphore = None

async def main():
    global BOT_USERNAME, download_semaphore
    print("Starting bot...")
    logging.info("Starting bot...")

    # Migrate users from old file-based system (one-time)
    if os.path.exists("allowed_users.txt"):
        migrated = migrate_from_file("allowed_users.txt")
        if migrated > 0:
            logging.info(f"Migrated {migrated} users from allowed_users.txt")
            # Rename old file to keep backup
            os.rename("allowed_users.txt", "allowed_users.txt.bak")
            logging.info("Renamed allowed_users.txt to allowed_users.txt.bak")

    user_count = get_user_count()
    logging.info(f"Total allowed users in database: {user_count}")

    # Initialize semaphore
    download_semaphore = asyncio.Semaphore(5)

    # Start cleanup task
    asyncio.create_task(cleanup_downloads())
    
    # Get bot info
    try:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
        logging.info(f"Bot started as @{BOT_USERNAME}")
    except Exception as e:
        logging.error(f"Failed to get bot info: {e}")
        # Continue anyway, just won't have username in captions
    
    # Set default commands
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="kir", description="Получить пожелание"),
        ],
        scope=BotCommandScopeDefault()
    )
    
    # Set admin commands
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запустить бота"),
                BotCommand(command="add", description="Добавить пользователя"),
                BotCommand(command="kir", description="Получить пожелание"),
            ],
            scope=BotCommandScopeChat(chat_id=177036997)
        )
    except Exception as e:
        logging.error(f"Failed to set admin commands: {e}")

    # Start aiogram polling
    print("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
    except Exception as e:
        print(f"Critical error: {e}")
        logging.critical(f"Critical error: {e}")
        sys.exit(1)
