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
    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'extractor_args': {'youtube': {'player_client': ['web']}},
    }
    # Add cookies if file exists
    print(f"[DOWNLOAD] COOKIES_PATH={COOKIES_PATH}, exists={os.path.exists(COOKIES_PATH)}")
    if os.path.exists(COOKIES_PATH):
        ydl_opts['cookiefile'] = COOKIES_PATH
        print(f"[DOWNLOAD] Using cookies file: {COOKIES_PATH}")
    else:
        print(f"[DOWNLOAD] Cookies file not found: {COOKIES_PATH}")
    
    if format_str:
        ydl_opts['format'] = format_str
        print(f"[DOWNLOAD] Requested format: {format_str}")
    else:
        ydl_opts['format'] = 'best'
        print(f"[DOWNLOAD] Using default format: best")

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

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # First, extract info to check available formats
            print(f"[DOWNLOAD] Extracting video info to check formats...")
            info = ydl.extract_info(url, download=False)
            
            # Log available formats for debugging
            if info and 'formats' in info:
                formats = info['formats']
                print(f"[DOWNLOAD] Available formats count: {len(formats)}")
                # Show best video and audio formats found
                video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('height')]
                audio_formats = [f for f in formats if f.get('acodec') != 'none']
                if video_formats:
                    best_video = max(video_formats, key=lambda x: x.get('height', 0))
                    print(f"[DOWNLOAD] Best video format: {best_video.get('height')}p, vcodec={best_video.get('vcodec')}")
                if audio_formats:
                    best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                    print(f"[DOWNLOAD] Best audio format: abr={best_audio.get('abr')}, acodec={best_audio.get('acodec')}")
            
            # Now download
            print(f"[DOWNLOAD] Starting download...")
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            print(f"[DOWNLOAD] Success: {filename}")
            return filename
        except yt_dlp.utils.DownloadError as e:
            error_str = str(e)
            print(f"[DOWNLOAD] DownloadError: {error_str}")
            
            if "ffmpeg is not installed" in error_str:
                print("[DOWNLOAD] FFmpeg not found. Falling back to 'best' format (single file).")
                # Remove merge option and use 'best'
                if 'merge_output_format' in ydl_opts:
                    del ydl_opts['merge_output_format']
                ydl_opts['format'] = 'best'
                
                # Retry with new options
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                    info = ydl_fallback.extract_info(url, download=True)
                    filename = ydl_fallback.prepare_filename(info)
                    return filename
            elif "Requested format is not available" in error_str:
                print("[DOWNLOAD] Format not available. Trying fallback formats...")
                # Try progressively simpler formats
                fallback_formats = [
                    'bestvideo+bestaudio/best',  # Try any quality merge
                    'best',  # Single file best quality
                    'worst',  # Worst quality as last resort
                ]
                
                # Remove merge option for fallback attempts
                if 'merge_output_format' in ydl_opts:
                    del ydl_opts['merge_output_format']
                
                for fallback_fmt in fallback_formats:
                    try:
                        print(f"[DOWNLOAD] Trying fallback format: {fallback_fmt}")
                        ydl_opts['format'] = fallback_fmt
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                            info = ydl_fallback.extract_info(url, download=True)
                            filename = ydl_fallback.prepare_filename(info)
                            print(f"[DOWNLOAD] Fallback success with '{fallback_fmt}': {filename}")
                            return filename
                    except Exception as fallback_error:
                        print(f"[DOWNLOAD] Fallback '{fallback_fmt}' failed: {fallback_error}")
                        continue
                
                print("[DOWNLOAD] All fallback formats failed")
                return None
            else:
                print(f"[DOWNLOAD] Error downloading: {e}")
                return None
        except Exception as e:
            print(f"[DOWNLOAD] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
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
