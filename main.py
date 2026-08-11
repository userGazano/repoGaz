import asyncio
import os
import uvicorn
from bot import run_bot
from web import app

async def run_web():
    config = uvicorn.Config(
        app,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", os.getenv("APP_PORT", "8080"))),
        log_level="info",
    )
    await uvicorn.Server(config).serve()

async def run():
    await asyncio.gather(run_bot(), run_web())
