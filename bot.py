import asyncio
import logging
import os
import re
import sys
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import API_TOKEN, API_ID, API_HASH
from downloader import download_video, download_spotify

# Configure logging
logging.basicConfig(level=logging.INFO)

import random

# ... imports ...

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Store user URLs temporarily: {user_id: url}
user_urls = {}

def load_allowed_users():
    """Load allowed user IDs from allowed_users.txt"""
    users = set()
    if os.path.exists("allowed_users.txt"):
        with open("allowed_users.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    try:
                        users.add(int(line))
                    except ValueError:
                        pass
    return users

def is_user_allowed(user_id):
    allowed_users = load_allowed_users()
    # If file is empty or only comments, maybe allow everyone? 
    # Or strictly deny? The user asked for a check, so strictly deny if not in list.
    # But for testing, if list is empty, maybe we should warn?
    # Let's assume strict whitelist.
    return user_id in allowed_users

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
                current_users = load_allowed_users()
                if new_user_id in current_users:
                    await status_msg.edit_text(f"⚠️ Пользователь @{username} (ID: {new_user_id}) уже есть в списке.")
                    return

                # Add to file
                with open("allowed_users.txt", "a") as f:
                    f.write(f"\n{new_user_id} # {username}")
                
                await status_msg.edit_text(f"✅ Пользователь @{username} (ID: `{new_user_id}`) успешно добавлен!")
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
        
    await message.answer(
        "Привет! Я бот для скачивания видео.\n"
        "Отправь мне ссылку на YouTube или Instagram видео, и я скачаю его для тебя."
    )

def get_quality_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="1080p", callback_data="quality_1080")
    builder.button(text="720p", callback_data="quality_720")
    builder.button(text="360p", callback_data="quality_360")
    builder.button(text="Audio Only", callback_data="quality_audio")
    builder.adjust(2)
    return builder.as_markup()

@dp.message(F.text)
async def handle_url(message: types.Message):
    if not await check_auth(message):
        return

    url = message.text.strip()
    user_id = message.from_user.id

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
    else:
        # Try generic download
        await message.answer("Пробую скачать по ссылке...")
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
    try:
        if quality == "spotify":
            file_path = await download_spotify(url)
        else:
            format_str = get_format_str(quality)
            file_path = await download_video(url, format_str)
        
        if not file_path or not os.path.exists(file_path):
            await message.answer("Не удалось скачать файл. Возможно, он недоступен.")
            return

        # Check file size (Telegram limit ~50MB for bots)
        file_size = os.path.getsize(file_path)
        if file_size > 49 * 1024 * 1024: # 49MB safety margin
            await message.answer(f"Файл ({file_size / 1024 / 1024:.1f} MB) больше лимита Telegram (50 MB).\n"
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
                
                # Wait for it to finish
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    await message.answer("✅ Загрузка завершена!")
                else:
                    error_msg = stderr.decode().strip()
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
            if quality in ["audio", "spotify"]:
                 await message.answer_audio(video_file)
            else:
                 await message.answer_video(video_file)
        except Exception as e:
            await message.answer(f"Ошибка при отправке файла: {e}")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:
        logging.error(f"Error processing download: {e}")
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

async def main():
    # Start cleanup task
    asyncio.create_task(cleanup_downloads())
    
    # Set default commands
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
        ],
        scope=BotCommandScopeDefault()
    )
    
    # Set admin commands
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Запустить бота"),
                BotCommand(command="add", description="Добавить пользователя"),
            ],
            scope=BotCommandScopeChat(chat_id=177036997)
        )
    except Exception as e:
        logging.error(f"Failed to set admin commands: {e}")

    # Start aiogram polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
