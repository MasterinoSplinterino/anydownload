import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH')


def _int_env(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Admins (comma-separated Telegram IDs) are exempt from limits
ADMIN_IDS = {
    int(x) for x in os.getenv('ADMIN_IDS', '177036997').replace(' ', '').split(',') if x
}

# Queue and per-user limits
MAX_CONCURRENT_DOWNLOADS = _int_env('MAX_CONCURRENT_DOWNLOADS', 2)  # downloads running at the same time
MAX_QUEUE_SIZE = _int_env('MAX_QUEUE_SIZE', 50)                    # total waiting jobs
MAX_JOBS_PER_USER = _int_env('MAX_JOBS_PER_USER', 2)                # running + waiting jobs per user
DAILY_LIMIT_PER_USER = _int_env('DAILY_LIMIT_PER_USER', 30)         # successful downloads per 24h, 0 = unlimited
COOLDOWN_SECONDS = _int_env('COOLDOWN_SECONDS', 5)                  # min pause between links from one user

# bgutil PO Token provider (docker-compose service), e.g. http://pot-provider:4416
POT_PROVIDER_URL = os.getenv('POT_PROVIDER_URL', '')

# Path to YouTube cookies file (for yt-dlp authentication)
# Use data/ directory to avoid conflicts with potential folders
COOKIES_PATH = os.getenv('COOKIES_PATH', 'data/youtube_cookies.txt')

# Cookies content from env (base64 encoded for multi-line support)
YOUTUBE_COOKIES_CONTENT = os.getenv('YOUTUBE_COOKIES_CONTENT', '')


def setup_cookies():
    """Write cookies from env to file if provided"""
    print(f"[COOKIES] Setup started. COOKIES_PATH={COOKIES_PATH}")
    print(f"[COOKIES] YOUTUBE_COOKIES_CONTENT length: {len(YOUTUBE_COOKIES_CONTENT) if YOUTUBE_COOKIES_CONTENT else 0}")
    if YOUTUBE_COOKIES_CONTENT and COOKIES_PATH:
        try:
            import base64
            # Create directory if needed
            cookies_dir = os.path.dirname(COOKIES_PATH)
            if cookies_dir and not os.path.exists(cookies_dir):
                os.makedirs(cookies_dir)
                print(f"[COOKIES] Created directory: {cookies_dir}")
            # Decode base64 content
            content = base64.b64decode(YOUTUBE_COOKIES_CONTENT).decode('utf-8')
            print(f"[COOKIES] Decoded content length: {len(content)}")
            with open(COOKIES_PATH, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[COOKIES] Successfully written to {COOKIES_PATH}")
            # Verify file exists
            if os.path.exists(COOKIES_PATH) and os.path.isfile(COOKIES_PATH):
                file_size = os.path.getsize(COOKIES_PATH)
                print(f"[COOKIES] File verified: {COOKIES_PATH} (size: {file_size} bytes)")
            else:
                print(f"[COOKIES] ERROR: File was not created or is not a file!")
        except Exception as e:
            print(f"[COOKIES] Error writing cookies: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[COOKIES] Skipping: No cookies content in env")

