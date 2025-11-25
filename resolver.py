import sys
import asyncio
from pyrogram import Client
from config import API_ID, API_HASH, API_TOKEN

if len(sys.argv) < 2:
    print("Usage: python resolver.py <username>")
    sys.exit(1)

username = sys.argv[1]

# Use in-memory session to avoid file locks
app = Client(
    "resolver_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=API_TOKEN,
    ipv6=False,
    in_memory=True
)

async def main():
    async with app:
        try:
            user = await app.get_users(username)
            print(user.id)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    app.run(main())
