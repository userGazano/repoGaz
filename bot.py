import asyncio
import logging
import os

import uvicorn

from bot import run_bot
from web import app

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s | %(levelname)s | %(name)s | %(message)s”,
)

async def run_web():
config = uvicorn.Config(
app,
host=os.getenv(“APP_HOST”, “0.0.0.0”),
port=int(os.getenv(“PORT”, os.getenv(“APP_PORT”, “8080”))),
log_level=“info”,
)

server = uvicorn.Server(config)
await server.serve()

async def run():
logging.getLogger(name).info(“Starting application…”)

await asyncio.gather(
    run_bot(),
    run_web(),
)
