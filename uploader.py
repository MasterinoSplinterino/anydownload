import sys
import asyncio
import os
from pyrogram import Client
from config import API_ID, API_HASH, API_TOKEN

# Check arguments
if len(sys.argv) < 3:
    print("Usage: python uploader.py <chat_id> <file_path>")
    sys.exit(1)

chat_id = int(sys.argv[1])
file_path = sys.argv[2]

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    sys.exit(1)

try:
    import tgcrypto
    print("Fast crypto (tgcrypto) is available.", flush=True)
except ImportError:
    print("Warning: tgcrypto not found. Uploads will be slower.", flush=True)

app = Client(
    "uploader_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=API_TOKEN,
    ipv6=False,
    max_concurrent_transmissions=4
)

async def main():
    async with app:
        print(f"Uploading {file_path} to {chat_id}...")
        
        import time
        last_print_time = 0

        async def progress(current, total):
            nonlocal last_print_time
            current_time = time.time()
            
            # Print every 3 seconds to ensure user sees progress
            if current_time - last_print_time >= 3:
                percent = current * 100 / total
                print(f"Progress: {percent:.1f}%", flush=True)
                last_print_time = current_time

        try:
            await app.send_video(
                chat_id=chat_id,
                video=file_path,
                caption="Скачано с помощью @any_download_pro_bot",
                supports_streaming=True,
                progress=progress
            )
            print("Upload complete!")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    # Run Pyrogram client
    app.run(main())
