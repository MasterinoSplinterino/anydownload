import os
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH')

# Path to YouTube cookies file (for yt-dlp authentication)
COOKIES_PATH = os.getenv('COOKIES_PATH', 'youtube_cookies.txt')

# Cookies content from env (base64 encoded for multi-line support)
YOUTUBE_COOKIES_CONTENT = os.getenv('YOUTUBE_COOKIES_CONTENT', '')


def setup_cookies():
    """Write cookies from env to file if provided"""
    print(f"[COOKIES] Setup started. COOKIES_PATH={COOKIES_PATH}")
    print(f"[COOKIES] YOUTUBE_COOKIES_CONTENT length: {len(YOUTUBE_COOKIES_CONTENT) if YOUTUBE_COOKIES_CONTENT else 0}")
    if YOUTUBE_COOKIES_CONTENT and COOKIES_PATH:
        try:
            import base64
            # Decode base64 content
            content = base64.b64decode(YOUTUBE_COOKIES_CONTENT).decode('utf-8')
            print(f"[COOKIES] Decoded content length: {len(content)}")
            with open(COOKIES_PATH, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[COOKIES] Successfully written to {COOKIES_PATH}")
            # Verify file exists
            if os.path.exists(COOKIES_PATH):
                file_size = os.path.getsize(COOKIES_PATH)
                print(f"[COOKIES] File verified: {COOKIES_PATH} (size: {file_size} bytes)")
            else:
                print(f"[COOKIES] ERROR: File was not created!")
        except Exception as e:
            print(f"[COOKIES] Error writing cookies: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"[COOKIES] Skipping: No cookies content in env")

