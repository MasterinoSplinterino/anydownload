import asyncio
import logging
import os
import random
import re
import secrets
import sys
import time

from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import FSInputFile, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import (
    API_TOKEN, API_ID, API_HASH, ADMIN_IDS, setup_cookies,
    MAX_CONCURRENT_DOWNLOADS, MAX_JOBS_PER_USER, DAILY_LIMIT_PER_USER,
)
from downloader import (
    download_video, download_spotify, upload_to_filehost,
    make_job_dir, remove_job_dir, DownloadFailed, DOWNLOAD_DIR,
)
from database import (
    is_user_allowed, add_user, migrate_from_file, get_user_count,
    log_download, count_downloads_since, set_user_daily_limit, get_top_users,
)
from queue_manager import DownloadQueue, Job, LimitError, is_admin, get_daily_limit

# Setup cookies from environment variable on startup
setup_cookies()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Initialize bot and dispatcher
if not API_TOKEN:
    logging.critical("Error: API_TOKEN is not set! Please check your environment variables.")
    sys.exit(1)

if not API_ID or not API_HASH:
    logging.warning("Warning: API_ID or API_HASH not set. Large file uploads via Pyrogram will not work.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

BOT_USERNAME = None
download_queue: DownloadQueue = None
# Only one Pyrogram uploader at a time: they share a session file (SQLite) that locks otherwise
pyrogram_lock = asyncio.Lock()

# Links waiting for a quality choice: {token: (user_id, url, created_at)}
pending_links = {}
PENDING_TTL = 15 * 60

BOT_API_LIMIT = 49 * 1024 * 1024          # Bot API upload limit is 50MB
TELEGRAM_LIMIT = 2 * 1024 * 1024 * 1024   # MTProto (Pyrogram) limit is 2GB

ADMIN_ID = next(iter(ADMIN_IDS)) if ADMIN_IDS else None


async def check_auth(message: types.Message):
    if is_admin(message.from_user.id):
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
    if not is_admin(message.from_user.id):
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
        process = await asyncio.create_subprocess_exec(
            sys.executable, "resolver.py", username,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            try:
                new_user_id = int(stdout.decode().strip())

                if is_user_allowed(new_user_id):
                    await status_msg.edit_text(f"⚠️ Пользователь @{username} (ID: {new_user_id}) уже есть в списке.")
                    return

                if add_user(new_user_id, username, added_by="admin"):
                    await status_msg.edit_text(f"✅ Пользователь @{username} (ID: `{new_user_id}`) успешно добавлен!")
                else:
                    await status_msg.edit_text("❌ Ошибка добавления пользователя в базу данных.")
            except ValueError:
                await status_msg.edit_text(f"❌ Ошибка чтения ID. Ответ: {stdout.decode()}")
        else:
            error_msg = (stderr.decode().strip() or stdout.decode().strip())[-500:]
            await status_msg.edit_text(f"❌ Не удалось найти пользователя.\nОшибка: {error_msg}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Системная ошибка: {e}")


@dp.message(Command("setlimit"))
async def cmd_set_limit(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "ℹ️ Использование: `/setlimit <user_id> <число|default>`\n"
            "0 — без лимита, default — вернуть общий лимит "
            f"({DAILY_LIMIT_PER_USER}/сутки)."
        )
        return
    try:
        user_id = int(args[1])
        limit = None if args[2].lower() == "default" else int(args[2])
    except ValueError:
        await message.answer("❌ user_id и лимит должны быть числами.")
        return

    if set_user_daily_limit(user_id, limit):
        shown = "по умолчанию" if limit is None else ("без лимита" if limit == 0 else f"{limit}/сутки")
        await message.answer(f"✅ Лимит для {user_id}: {shown}")
    else:
        await message.answer("❌ Пользователь не найден в базе.")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    lines = [
        "📊 **Статистика**",
        f"Пользователей: {get_user_count()}",
        f"Скачивается сейчас: {download_queue.running_count}/{MAX_CONCURRENT_DOWNLOADS}",
        f"В очереди: {download_queue.waiting_count}",
        "",
        "Топ за 24 часа:",
    ]
    top = get_top_users(24)
    if top:
        for user_id, username, count in top:
            lines.append(f"• {('@' + username) if username else user_id}: {count}")
    else:
        lines.append("• пока пусто")
    await message.answer("\n".join(lines))


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
        "Просто кинь мне ссылку и я всё сделаю 🚀\n\n"
        "/queue — моя очередь, /limits — мои лимиты, /cancel — отменить ожидающие загрузки"
    )
    await message.answer(welcome_text)
    logging.info(f"User {message.from_user.id} started the bot")


@dp.message(Command("queue"))
async def cmd_queue(message: types.Message):
    if not await check_auth(message):
        return

    jobs = download_queue.user_jobs(message.from_user.id)
    lines = [
        f"⚙️ Сейчас скачивается: {download_queue.running_count}/{MAX_CONCURRENT_DOWNLOADS}",
        f"⏳ Ждут в очереди: {download_queue.waiting_count}",
    ]
    if jobs:
        lines.append("\nТвои загрузки:")
        for job in jobs:
            pos = download_queue.position(job)
            state = "качается" if job.started else f"в очереди, место {pos}"
            lines.append(f"• #{job.id} — {state}")
    else:
        lines.append("\nУ тебя нет активных загрузок.")
    await message.answer("\n".join(lines))


@dp.message(Command("limits"))
async def cmd_limits(message: types.Message):
    if not await check_auth(message):
        return

    user_id = message.from_user.id
    limit = get_daily_limit(user_id)
    used = count_downloads_since(user_id, 24)
    active = len(download_queue.user_jobs(user_id))
    per_day = "без ограничений" if not limit else f"{used}/{limit}"
    await message.answer(
        f"📊 Скачано за 24 часа: {per_day}\n"
        f"🚦 Одновременно: {active}/{'∞' if is_admin(user_id) else MAX_JOBS_PER_USER}"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    if not await check_auth(message):
        return

    cancelled = download_queue.cancel_user_jobs(message.from_user.id)
    if cancelled:
        await message.answer(f"🗑 Отменено загрузок в очереди: {cancelled}")
    else:
        await message.answer("Нечего отменять (уже начатые загрузки не отменяются).")


def get_quality_keyboard(token: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="1080p", callback_data=f"q:{token}:1080")
    builder.button(text="720p", callback_data=f"q:{token}:720")
    builder.button(text="360p", callback_data=f"q:{token}:360")
    builder.button(text="Audio Only", callback_data=f"q:{token}:audio")
    builder.adjust(2)
    return builder.as_markup()


@dp.message(Command("kir"))
async def cmd_kir(message: types.Message):
    try:
        if not os.path.exists("wishes.txt"):
            await message.answer("Файл с пожеланиями не найден. Грусть.")
            return

        with open("wishes.txt", "r", encoding="utf-8") as f:
            wishes = [w for w in f.readlines() if w.strip()]

        if wishes:
            await message.answer(f"✨ {random.choice(wishes).strip()}")
        else:
            await message.answer("Шутки кончились, иди работай!")
    except Exception as e:
        logging.error(f"Error reading wishes: {e}")
        await message.answer("Что-то пошло не так при чтении пожеланий.")


@dp.message(F.text.lower() == "кир")
async def secret_code_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"

    if is_user_allowed(user_id):
        await message.answer("Ты уже в клубе, бро! 😎")
        return

    if add_user(user_id, username, added_by="secret_code"):
        await message.answer("✅ Доступ получен! Добро пожаловать в элитный клуб.\nТеперь можешь скидывать ссылки.")
        logging.info(f"User {username} ({user_id}) added via secret code.")

        if ADMIN_ID:
            try:
                await bot.send_message(ADMIN_ID, f"🆕 Пользователь @{username} ({user_id}) активировал секретный код!")
            except Exception:
                pass
    else:
        await message.answer("Что-то пошло не так при активации кода.")


def detect_platform(url: str) -> str:
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "instagram.com" in u:
        return "instagram"
    if "spotify.com" in u:
        return "spotify"
    if "tiktok.com" in u:
        return "tiktok"
    if re.search(r"(^|[/.])(twitter\.com|x\.com)(/|$)", u):
        return "twitter"
    return "other"


PLATFORM_TEXT = {
    "instagram": "📸 Instagram",
    "spotify": "🎧 Spotify",
    "tiktok": "🎵 TikTok",
    "twitter": "🐦 Twitter/X",
    "youtube": "📺 YouTube",
    "other": "🔄 Видео",
}


async def enqueue(message: types.Message, user_id: int, url: str, quality: str, status_msg: types.Message = None):
    """Create a job and put it into the queue, telling the user their position."""
    platform = detect_platform(url)
    if status_msg is None:
        status_msg = await message.answer(f"{PLATFORM_TEXT[platform]}: добавляю в очередь...")

    job = Job(user_id=user_id, chat_id=message.chat.id, url=url, quality=quality, status_message=status_msg)
    position = download_queue.submit(job)
    text = f"{PLATFORM_TEXT[platform]}: " + (
        "начинаю скачивание..." if position == 0
        else f"⏳ ты в очереди, место {position}. Я напишу, когда начну."
    )
    await safe_edit(status_msg, text)


@dp.message(F.text)
async def handle_url(message: types.Message):
    if not await check_auth(message):
        return

    text = message.text.strip()
    user_id = message.from_user.id
    logging.info(f"Received message from {user_id} (@{message.from_user.username}): {text}")

    match = re.search(r"https?://\S+", text)
    if not match:
        await message.answer("Пожалуйста, отправь корректную ссылку.")
        return
    url = match.group(0)

    try:
        download_queue.check_limits(user_id)
    except LimitError as e:
        await message.answer(str(e))
        return

    platform = detect_platform(url)
    if platform == "youtube":
        # Drop stale links to keep memory bounded
        now = time.time()
        for token in [t for t, v in pending_links.items() if now - v[2] > PENDING_TTL]:
            pending_links.pop(token, None)

        token = secrets.token_urlsafe(6)
        pending_links[token] = (user_id, url, now)
        await message.answer("Выбери качество видео:", reply_markup=get_quality_keyboard(token))
    elif platform == "spotify":
        await enqueue(message, user_id, url, "spotify")
    else:
        await enqueue(message, user_id, url, "best")


@dp.callback_query(F.data.startswith("q:"))
async def handle_quality_selection(callback: types.CallbackQuery):
    _, token, quality = callback.data.split(":", 2)
    user_id = callback.from_user.id
    entry = pending_links.get(token)

    try:
        await callback.answer()
    except TelegramBadRequest:
        pass

    if not entry or entry[0] != user_id:
        await safe_edit(callback.message, "Ссылка устарела. Отправь её снова.")
        return

    try:
        download_queue.check_limits(user_id, check_cooldown=False)
    except LimitError as e:
        await safe_edit(callback.message, str(e))
        return

    pending_links.pop(token, None)
    await safe_edit(callback.message, f"Выбрано качество: {quality}.")
    await enqueue(callback.message, user_id, entry[1], quality, status_msg=callback.message)


def get_format_str(quality):
    # Prefer H.264/AAC in mp4 (plays everywhere in Telegram), fall back to anything within the height
    if quality in ("1080", "720", "360"):
        h = quality
        return (f"bv*[height<={h}][vcodec^=avc1]+ba[ext=m4a]/"
                f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b")
    if quality == "audio":
        return "bestaudio/best"
    # "best" for Instagram/TikTok/X etc: these often have separate video/audio streams,
    # plain "best" (single file only) fails with "Requested format is not available"
    return "bv*[vcodec^=avc1]+ba/bv*+ba/b"


async def safe_edit(message: types.Message, text: str):
    try:
        await message.edit_text(text)
    except TelegramBadRequest:
        pass
    except Exception as e:
        logging.debug(f"edit_text failed: {e}")


async def process_job(job: Job):
    """Worker handler: download the file and send it to the user."""
    message = job.status_message
    url, quality = job.url, job.quality
    job_dir = make_job_dir(job.id)
    loop = asyncio.get_running_loop()
    logging.info(f"Processing job {job.id}: {url} quality={quality} user={job.user_id}")

    try:
        await safe_edit(message, "📥 Начинаю скачивание...")

        last_edit_time = 0

        def progress_handler(d):
            # Called from the downloader thread -> schedule the edit on the bot's loop
            nonlocal last_edit_time
            now = time.time()
            if now - last_edit_time < 3:
                return
            last_edit_time = now

            def clean(v):
                return re.sub(r'\x1b\[[0-9;]*m', '', str(v or 'N/A')).strip()

            text = (f"📥 Скачиваю: {clean(d.get('_percent_str'))}\n"
                    f"🚀 Скорость: {clean(d.get('_speed_str'))}\n"
                    f"⏳ Осталось: {clean(d.get('_eta_str'))}")
            asyncio.run_coroutine_threadsafe(safe_edit(message, text), loop)

        try:
            if quality == "spotify":
                file_path = await download_spotify(url, job_dir)
            else:
                file_path = await download_video(url, get_format_str(quality), job_dir, progress_callback=progress_handler)
        except DownloadFailed as e:
            await safe_edit(message, f"❌ {e}")
            return

        if not file_path or not os.path.exists(file_path):
            logging.error(f"Download failed: file not found at {file_path}")
            await safe_edit(message, "❌ Не удалось скачать файл. Возможно, он недоступен.")
            return

        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / 1024 / 1024
        logging.info(f"Job {job.id}: downloaded {file_path}, size: {file_size_mb:.1f} MB")

        is_audio = quality in ("audio", "spotify")
        caption_text = f"Скачано с помощью @{BOT_USERNAME}" if BOT_USERNAME else "Скачано ботом"
        caption = f"{'🎧' if is_audio else '📹'} {caption_text}"
        use_pyrogram = bool(API_ID and API_HASH)

        sent = False
        if file_size > TELEGRAM_LIMIT or (file_size > BOT_API_LIMIT and not use_pyrogram):
            await safe_edit(message, f"📦 Файл большой ({file_size_mb:.1f} MB). Загружаю на файлообменник...")
            filehost_url = await upload_to_filehost(file_path)
            if filehost_url:
                await message.answer(
                    f"✅ Файл загружен!\n\n📥 {filehost_url}\n\n⚠️ Ссылка временная"
                )
                sent = True
            else:
                await safe_edit(message, "❌ Не удалось загрузить файл на файлообменник.")

        elif file_size > BOT_API_LIMIT:
            await safe_edit(message, f"📤 Файл {file_size_mb:.1f} MB, отправляю в Telegram...")
            sent = await upload_with_pyrogram(job, file_path, "audio" if is_audio else "video", caption)

        else:
            await safe_edit(message, "📤 Загружаю в Telegram...")
            media = FSInputFile(file_path)
            for attempt in range(3):
                try:
                    if is_audio:
                        await bot.send_audio(job.chat_id, media, caption=caption, request_timeout=1200)
                    else:
                        await bot.send_video(job.chat_id, media, caption=caption,
                                             supports_streaming=True, request_timeout=1200)
                    sent = True
                    break
                except Exception as e:
                    logging.warning(f"Upload attempt {attempt + 1} failed: {e}")
                    if attempt == 2:
                        await safe_edit(message, f"❌ Ошибка при отправке файла: {e}")
                    else:
                        await asyncio.sleep(2)

        if sent:
            log_download(job.user_id, url, detect_platform(url), quality, file_size)
            try:
                await message.delete()
            except Exception:
                await safe_edit(message, "✅ Готово!")

    except Exception as e:
        logging.error(f"Error processing job {job.id}: {e}", exc_info=True)
        await safe_edit(message, "❌ Произошла ошибка при обработке видео.")
    finally:
        remove_job_dir(job_dir)


async def upload_with_pyrogram(job: Job, file_path: str, kind: str, caption: str) -> bool:
    message = job.status_message
    async with pyrogram_lock:
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "uploader.py", str(job.chat_id), file_path, kind, caption,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Read stderr concurrently so a chatty process can't deadlock on a full pipe
            stderr_task = asyncio.create_task(process.stderr.read())
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode(errors="ignore").strip()
                if line_str.startswith("Progress:"):
                    await safe_edit(message, f"📤 Загрузка в Telegram: {line_str.split(': ', 1)[1]}")

            await process.wait()
            stderr_data = await stderr_task

            if process.returncode == 0:
                logging.info(f"Job {job.id}: large file upload completed via uploader.py")
                return True

            error_msg = stderr_data.decode(errors="ignore").strip()[-500:]
            logging.error(f"Uploader error: {error_msg}")
            await safe_edit(message, f"❌ Ошибка при загрузке: {error_msg}")
        except Exception as e:
            logging.error(f"Subprocess error: {e}")
            await safe_edit(message, f"❌ Не удалось запустить загрузчик: {e}")
    return False


async def cleanup_downloads():
    """Periodically remove leftovers older than 1 hour (e.g. after a crash)."""
    import shutil
    while True:
        try:
            if os.path.exists(DOWNLOAD_DIR):
                for name in os.listdir(DOWNLOAD_DIR):
                    path = os.path.join(DOWNLOAD_DIR, name)
                    if time.time() - os.path.getmtime(path) > 3600:
                        try:
                            if os.path.isdir(path):
                                shutil.rmtree(path, ignore_errors=True)
                            else:
                                os.remove(path)
                            logging.info(f"Deleted old download: {path}")
                        except Exception as e:
                            logging.error(f"Error deleting {path}: {e}")
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
        await asyncio.sleep(600)


async def main():
    global BOT_USERNAME, download_queue
    logging.info("Starting bot...")

    # Migrate users from old file-based system (one-time)
    if os.path.exists("allowed_users.txt"):
        migrated = migrate_from_file("allowed_users.txt")
        if migrated > 0:
            logging.info(f"Migrated {migrated} users from allowed_users.txt")
            os.rename("allowed_users.txt", "allowed_users.txt.bak")

    logging.info(f"Total allowed users in database: {get_user_count()}")

    download_queue = DownloadQueue(process_job)
    download_queue.start()

    asyncio.create_task(cleanup_downloads())

    try:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
        logging.info(f"Bot started as @{BOT_USERNAME}")
    except Exception as e:
        logging.error(f"Failed to get bot info: {e}")

    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="queue", description="Моя очередь"),
        BotCommand(command="limits", description="Мои лимиты"),
        BotCommand(command="cancel", description="Отменить ожидающие загрузки"),
        BotCommand(command="kir", description="Получить пожелание"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    admin_commands = user_commands + [
        BotCommand(command="add", description="Добавить пользователя"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="setlimit", description="Лимит пользователя"),
    ]
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.error(f"Failed to set admin commands for {admin_id}: {e}")

    logging.info("Starting polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
    except Exception as e:
        logging.critical(f"Critical error: {e}", exc_info=True)
        sys.exit(1)
