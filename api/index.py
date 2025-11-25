import os
import json
import asyncio
from bot import bot, dp
from aiogram.types import Update

async def handler(request):
    if request.method == "POST":
        try:
            data = await request.json()
            update = Update.model_validate(data, context={"bot": bot})
            await dp.feed_update(bot, update)
            return {"statusCode": 200, "body": "OK"}
        except Exception as e:
            print(f"Error: {e}")
            return {"statusCode": 500, "body": str(e)}
    return {"statusCode": 200, "body": "Bot is running"}

# Vercel entry point
def index(request):
    # Vercel passes a request object, but for async handling we might need a wrapper
    # However, Vercel Python runtime supports async handlers if defined correctly.
    # Standard Vercel Python is WSGI. For async, we usually use a framework or run_until_complete.
    
    # Simple synchronous wrapper for Vercel's WSGI-like environment if needed,
    # but Vercel also supports Sanic/FastAPI.
    # Let's assume standard Vercel Python function signature.
    
    # Actually, for Vercel Serverless Functions with Python, it's often easier to use
    # a micro-framework like FastAPI or just handle the raw request.
    # Let's try the raw request approach compatible with Vercel's `http.server` style.
    pass

# Better approach: Use FastAPI for Vercel
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/api/index")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/index")
async def status():
    return {"status": "active"}
