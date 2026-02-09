import yt_dlp
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
import sys
import subprocess
import glob
from config import COOKIES_PATH

# Create a downloads directory if it doesn't exist
if os.environ.get("VERCEL"):
    DOWNLOAD_DIR = "/tmp"
else:
    DOWNLOAD_DIR = "downloads"
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

executor = ThreadPoolExecutor(max_workers=5)

def get_video_info_sync(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['web']}},
        'js_runtimes': ['node'],
        'remote_components': ['ejs:github'],
    }
    # Add cookies if file exists
    if os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH
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

def download_video_sync(url, format_str=None, output_filename=None, progress_callback=None):
    # Add cookies if file exists
    print(f"[DOWNLOAD] COOKIES_PATH={COOKIES_PATH}, exists={os.path.exists(COOKIES_PATH)}")

    # Try different player clients in order of preference
    player_clients = [
        ['ios', 'web'],      # iOS client often bypasses restrictions
        ['android', 'web'],  # Android as fallback
        ['web'],             # Web only
        ['tv_embedded'],     # TV embedded player
    ]

    for clients in player_clients:
        print(f"[DOWNLOAD] Trying player_client: {clients}")

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
            'extractor_args': {'youtube': {'player_client': clients}},
            'format': format_str if format_str else 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'force_ipv4': True,  # Force IPv4 to avoid some bot detection
            'sleep_interval': 1,  # Add delay between requests
            'max_sleep_interval': 3,
            # JavaScript runtime for solving YouTube challenges
            'js_runtimes': ['node'],
            'remote_components': ['ejs:github'],
        }

        if os.path.exists(COOKIES_PATH):
            ydl_opts['cookiefile'] = COOKIES_PATH
            print(f"[DOWNLOAD] Using cookies file: {COOKIES_PATH}")
        else:
            print(f"[DOWNLOAD] Cookies file not found: {COOKIES_PATH}")

        # If output_filename is provided, use it (useful for temp names)
        if output_filename:
            ydl_opts['outtmpl'] = os.path.join(DOWNLOAD_DIR, output_filename)

        # Add progress hook
        def my_hook(d):
            if d['status'] == 'downloading':
                if progress_callback:
                    progress_callback(d)

        if progress_callback:
            ydl_opts['progress_hooks'] = [my_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"[DOWNLOAD] Starting download...")
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                print(f"[DOWNLOAD] Success: {filename}")
                return filename
        except yt_dlp.utils.DownloadError as e:
            error_str = str(e)
            print(f"[DOWNLOAD] DownloadError with {clients}: {error_str}")

            if "Sign in to confirm" in error_str or "bot" in error_str.lower():
                print(f"[DOWNLOAD] Bot detection triggered, trying next player client...")
                continue
            elif "Requested format is not available" in error_str:
                print(f"[DOWNLOAD] Format not available with {clients}, trying next...")
                continue
            elif "ffmpeg is not installed" in error_str:
                # Try without merge
                try:
                    del ydl_opts['merge_output_format']
                    ydl_opts['format'] = 'best'
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                        info = ydl_fallback.extract_info(url, download=True)
                        filename = ydl_fallback.prepare_filename(info)
                        return filename
                except Exception:
                    continue
            else:
                continue
        except Exception as e:
            print(f"[DOWNLOAD] Unexpected error with {clients}: {e}")
            continue

    print("[DOWNLOAD] All player clients failed")
    return None

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

async def download_video(url, format_str=None, progress_callback=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, download_video_sync, url, format_str, None, progress_callback)
