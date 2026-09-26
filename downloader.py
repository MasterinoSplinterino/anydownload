import yt_dlp
import os
import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor
import sys
import subprocess
import requests
from config import COOKIES_PATH, MAX_CONCURRENT_DOWNLOADS, POT_PROVIDER_URL

# Create a downloads directory if it doesn't exist
if os.environ.get("VERCEL"):
    DOWNLOAD_DIR = "/tmp"
else:
    DOWNLOAD_DIR = "downloads"
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

# +1 worker so file host uploads are not blocked by running downloads
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS + 1)

FALLBACK_FORMAT = 'bv*+ba/b'

MEDIA_EXTENSIONS = ('.mp4', '.mkv', '.webm', '.mov', '.m4a', '.mp3', '.opus', '.ogg', '.flac', '.wav', '.jpg', '.png')


class DownloadFailed(Exception):
    """Download failed; message is a short user-facing reason."""


def make_job_dir(job_id):
    """Every job gets its own directory so parallel jobs never touch each other's files."""
    path = os.path.join(DOWNLOAD_DIR, f"job_{job_id}")
    shutil.rmtree(path, ignore_errors=True)  # job ids restart after a reboot
    os.makedirs(path, exist_ok=True)
    return path


def remove_job_dir(path):
    shutil.rmtree(path, ignore_errors=True)


def _base_opts():
    opts = {
        'quiet': False,
        'no_warnings': False,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'force_ipv4': True,
        # JavaScript runtime for solving YouTube n/sig challenges (needs yt-dlp-ejs + node >= 20)
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
    }
    if os.path.exists(COOKIES_PATH):
        opts['cookiefile'] = COOKIES_PATH
    return opts


def _youtube_extractor_args(clients):
    args = {'youtube': {'player_client': clients}}
    if POT_PROVIDER_URL:
        args['youtubepot-bgutilhttp'] = {'base_url': [POT_PROVIDER_URL]}
    return args


def _find_output_file(info, job_dir):
    """Return the real path of the downloaded file."""
    for d in (info or {}).get('requested_downloads') or []:
        path = d.get('filepath')
        if path and os.path.exists(path):
            return path
    # Fallback: biggest media file in the job directory
    files = [
        os.path.join(job_dir, f) for f in os.listdir(job_dir)
        if f.lower().endswith(MEDIA_EXTENSIONS) and not f.endswith('.part')
    ]
    return max(files, key=os.path.getsize) if files else None


def _user_reason(error_str):
    e = error_str.lower()
    if 'sign in to confirm' in e or 'not a bot' in e:
        return "YouTube требует подтверждения, что это не бот (нужны свежие cookies / PO token)."
    if 'private' in e or 'login' in e or 'log in' in e:
        return "Контент приватный или требует входа в аккаунт."
    if 'unsupported url' in e:
        return "Этот сайт не поддерживается."
    if 'geo' in e or 'not available in your country' in e:
        return "Видео недоступно в регионе сервера."
    if 'video unavailable' in e or 'has been removed' in e or '404' in e:
        return "Видео удалено или недоступно."
    if 'requested format is not available' in e:
        return "Нужный формат недоступен."
    return "Не удалось скачать. Возможно, ссылка недоступна."


def download_video_sync(url, format_str, job_dir, progress_callback=None):
    """Download with yt-dlp into job_dir. Returns file path or raises DownloadFailed."""
    is_youtube = 'youtube.com' in url or 'youtu.be' in url
    print(f"[DOWNLOAD] url={url} format={format_str} cookies={os.path.exists(COOKIES_PATH)}")

    # Player clients are YouTube-specific; other sites need a single attempt
    attempts = [['default'], ['default', 'mweb'], ['tv', 'web_safari']] if is_youtube else [None]
    last_error = "unknown error"

    def hook(d):
        if d.get('status') == 'downloading' and progress_callback:
            progress_callback(d)

    for clients in attempts:
        formats = [format_str] if format_str == FALLBACK_FORMAT else [format_str, FALLBACK_FORMAT]
        for fmt in formats:
            ydl_opts = _base_opts()
            ydl_opts.update({
                # Titles of Instagram/TikTok posts can be huge -> limit bytes to avoid "File name too long"
                'outtmpl': os.path.join(job_dir, '%(title).80B [%(id).40B].%(ext)s'),
                'format': fmt,
                'progress_hooks': [hook],
            })
            if fmt != 'bestaudio/best':
                ydl_opts['merge_output_format'] = 'mp4'
            if clients:
                ydl_opts['extractor_args'] = _youtube_extractor_args(clients)

            print(f"[DOWNLOAD] Trying clients={clients} format={fmt}")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                path = _find_output_file(info, job_dir)
                if path:
                    print(f"[DOWNLOAD] Success: {path} (height: {info.get('height')})")
                    return path
                last_error = "file not found after download"
                break
            except yt_dlp.utils.DownloadError as e:
                last_error = str(e)
                print(f"[DOWNLOAD] DownloadError clients={clients} format={fmt}: {last_error}")
                if 'Requested format is not available' in last_error:
                    continue  # same client, looser format
                break  # next player client
            except Exception as e:
                last_error = str(e)
                print(f"[DOWNLOAD] Unexpected error clients={clients}: {e}")
                break

        # Non-retryable problems: don't waste time on other clients
        low = last_error.lower()
        if any(s in low for s in ('unsupported url', 'private', 'has been removed', 'video unavailable')):
            break

    print(f"[DOWNLOAD] All attempts failed: {last_error}")
    raise DownloadFailed(_user_reason(last_error))


def download_spotify_sync(url, job_dir):
    try:
        print(f"Downloading Spotify URL: {url}")
        output = os.path.join(job_dir, "{artists} - {title}.{output-ext}")
        cmd = [sys.executable, "-m", "spotdl", "download", url, "--output", output]
        process = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if process.returncode != 0:
            # spotdl sometimes errors but still downloads (e.g. metadata issues)
            print(f"SpotDL error: {process.stderr[-2000:]}")

        audio_files = [
            os.path.join(job_dir, f) for f in os.listdir(job_dir)
            if f.endswith(('.mp3', '.m4a', '.flac', '.opus', '.ogg'))
        ]
        if not audio_files:
            raise DownloadFailed("Spotify: трек не найден или не скачался.")
        return max(audio_files, key=os.path.getmtime)
    except subprocess.TimeoutExpired:
        raise DownloadFailed("Spotify: превышено время ожидания.")


async def download_spotify(url, job_dir):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, download_spotify_sync, url, job_dir)


async def download_video(url, format_str, job_dir, progress_callback=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, download_video_sync, url, format_str, job_dir, progress_callback)


def upload_to_filehost_sync(file_path):
    """Upload file to file hosting and return download link"""
    filename = os.path.basename(file_path)

    # Try multiple file hosts in order
    hosts = [
        ("0x0.st", _upload_0x0),
        ("pixeldrain.com", _upload_pixeldrain),
        ("litterbox.catbox.moe", _upload_litterbox),
    ]

    for host_name, upload_func in hosts:
        try:
            print(f"[UPLOAD] Trying {host_name}...")
            url = upload_func(file_path, filename)
            if url:
                print(f"[UPLOAD] Success with {host_name}: {url}")
                return url
        except Exception as e:
            print(f"[UPLOAD] {host_name} failed: {e}")
            continue

    print("[UPLOAD] All hosts failed")
    return None


def _upload_0x0(file_path, filename):
    """Upload to 0x0.st (512MB limit)"""
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (filename, f)},
            timeout=600
        )
    if resp.status_code == 200:
        return resp.text.strip()
    return None


def _upload_pixeldrain(file_path, filename):
    """Upload to pixeldrain.com (20GB limit)"""
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://pixeldrain.com/api/file",
            files={"file": (filename, f)},
            timeout=600
        )
    if resp.status_code == 201:
        data = resp.json()
        return f"https://pixeldrain.com/u/{data['id']}"
    return None


def _upload_litterbox(file_path, filename):
    """Upload to litterbox.catbox.moe (1GB limit, 72h storage)"""
    with open(file_path, "rb") as f:
        resp = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "72h"},
            files={"fileToUpload": (filename, f)},
            timeout=600
        )
    if resp.status_code == 200 and resp.text.startswith("https://"):
        return resp.text.strip()
    return None


async def upload_to_filehost(file_path):
    """Async wrapper for file host upload"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, upload_to_filehost_sync, file_path)
