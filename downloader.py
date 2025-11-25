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
        except yt_dlp.utils.DownloadError as e:
            if "ffmpeg is not installed" in str(e):
                print("FFmpeg not found. Falling back to 'best' format (single file).")
                # Remove merge option and use 'best'
                if 'merge_output_format' in ydl_opts:
                    del ydl_opts['merge_output_format']
                ydl_opts['format'] = 'best'
                
                # Retry with new options
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                    info = ydl_fallback.extract_info(url, download=True)
                    filename = ydl_fallback.prepare_filename(info)
                    return filename
            else:
                print(f"Error downloading: {e}")
                return None
        except Exception as e:
            print(f"Error downloading: {e}")
            return None

import sys
import subprocess
import glob

# ... existing imports ...

# ... existing code ...

def download_spotify_sync(url):
    try:
        print(f"Downloading Spotify URL: {url}")
        
        # Get list of files before download to identify the new one
        before_files = set(os.listdir(DOWNLOAD_DIR))
        
        # Run spotdl
        # --output format to ensure we can find it easily? Default is "{artist} - {title}.{ext}"
        # Let's just download to DOWNLOAD_DIR
        cmd = [sys.executable, "-m", "spotdl", url, "--output", DOWNLOAD_DIR]
        
        # Run with a timeout of 5 minutes
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if process.returncode != 0:
            print(f"SpotDL error: {process.stderr}")
            # Sometimes spotdl errors but still downloads (e.g. minor metadata issues)
            # So we proceed to check for new files
        
        # Check for new files
        after_files = set(os.listdir(DOWNLOAD_DIR))
        new_files = after_files - before_files
        
        # Filter for audio files
        audio_files = [f for f in new_files if f.endswith(('.mp3', '.m4a', '.flac'))]
        
        if not audio_files:
            print("No new files found after SpotDL run.")
            return None
            
        # Return the first new file found (absolute path)
        return os.path.join(DOWNLOAD_DIR, audio_files[0])

    except subprocess.TimeoutExpired:
        print("SpotDL timed out")
        return None
    except Exception as e:
        print(f"Error downloading spotify: {e}")
        return None

async def download_spotify(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, download_spotify_sync, url)

async def download_video(url, format_str=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, download_video_sync, url, format_str)
