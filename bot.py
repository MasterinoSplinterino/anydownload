import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import API_TOKEN
from downloader import download_video

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Store user URLs temporarily: {user_id: url}
user_urls = {}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
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
        await process_download(message, url, format_str="best")
    else:
        # Try generic download
        await message.answer("Пробую скачать по ссылке...")
        await process_download(message, url, format_str="best")

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
    
    format_str = "best"
    if quality == "1080":
        format_str = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    elif quality == "720":
        format_str = "bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif quality == "360":
        format_str = "bestvideo[height<=360]+bestaudio/best[height<=360]"
    elif quality == "audio":
        format_str = "bestaudio/best"

    await process_download(callback.message, url, format_str)
    await callback.answer()

async def process_download(message: types.Message, url: str, format_str: str):
    try:
        file_path = await download_video(url, format_str)
        
        if not file_path or not os.path.exists(file_path):
            await message.answer("Не удалось скачать видео. Возможно, оно недоступно или приватное.")
            return

        # Check file size (Telegram limit ~50MB for bots)
        file_size = os.path.getsize(file_path)
        if file_size > 50 * 1024 * 1024:
            await message.answer("Файл слишком большой для отправки через Telegram (лимит 50МБ).")
            os.remove(file_path)
            return

        await message.answer("Загружаю видео в Telegram...")
        
        video_file = FSInputFile(file_path)
        if "audio" in format_str and "video" not in format_str:
             await message.answer_audio(video_file)
        else:
             await message.answer_video(video_file)

        # Cleanup
        os.remove(file_path)

    except Exception as e:
        logging.error(f"Error processing download: {e}")
        await message.answer("Произошла ошибка при обработке видео.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
