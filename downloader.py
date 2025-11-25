import yt_dlp
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Create a downloads directory if it doesn't exist
if os.environ.get("VERCEL"):
    DOWNLOAD_DIR = "/tmp"
else:
    DOWNLOAD_DIR = "downloads"
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

executor = ThreadPoolExecutor(max_workers=2)

def get_video_info_sync(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return info
        except Exception as e:
            print(f"Error extracting info: {e}")
            return None

async def get_video_info(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, get_video_info_sync, url)

def download_video_sync(url, format_str=None, output_filename=None):
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
    }
    
    if format_str:
        ydl_opts['format'] = format_str
    else:
        ydl_opts['format'] = 'best'

    # If output_filename is provided, use it (useful for temp names)
    if output_filename:
        ydl_opts['outtmpl'] = os.path.join(DOWNLOAD_DIR, output_filename)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return filename
        except Exception as e:
            print(f"Error downloading: {e}")
            return None

async def download_video(url, format_str=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, download_video_sync, url, format_str)
