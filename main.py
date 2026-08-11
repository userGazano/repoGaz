import asyncio
import logging
import os
import platform
import socket
import sys
import uvicorn
from bot import run_bot
from web import app
def setup_logging():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        force=True,
    )
log = logging.getLogger("shop")
def print_startup_info():
    log.info("=" * 60)
    log.info("🚀 SHOP STARTING")
    log.info("=" * 60)
    log.info("🐍 Python: %s", sys.version.split()[0])
    log.info("🖥 Platform: %s", platform.platform())
    log.info("📦 Python executable: %s", sys.executable)
    log.info("📂 Working directory: %s", os.getcwd())
    log.info("🏠 Hostname: %s", socket.gethostname())
    port = os.getenv(
        "PORT",
        os.getenv("APP_PORT", "8080"),
    )
    log.info("🌐 PORT: %s", port)
    bot_token = os.getenv("BOT_TOKEN", "")
    if bot_token:
        log.info(
            "🔑 BOT_TOKEN: FOUND (length=%d)",
            len(bot_token),
        )
    else:
        log.error("❌ BOT_TOKEN: NOT FOUND")
    database_url = os.getenv(
        "DATABASE_URL",
        "",
    )
    if database_url:
        log.info("🗄 DATABASE_URL: FOUND")
    else:
        log.error("❌ DATABASE_URL: NOT FOUND")
    admin_ids = os.getenv(
        "ADMIN_IDS",
        "",
    )
    log.info(
        "👑 ADMIN_IDS: %s",
        admin_ids if admin_ids else "not configured",
    )
    log.info("=" * 60)
async def run_web():
    host = os.getenv(
        "APP_HOST",
        "0.0.0.0",
    )
    port = int(
        os.getenv(
            "PORT",
            os.getenv("APP_PORT", "8080"),
        )
    )
    log.info(
        "🌐 Starting web server on %s:%s",
        host,
        port,
    )
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.getenv(
            "LOG_LEVEL",
            "info",
        ).lower(),
        access_log=True,
    )
    server = uvicorn.Server(config)
    try:
        await server.serve()
    except Exception:
        log.exception("❌ Web server crashed")
        raise
async def run():
    setup_logging()
    print_startup_info()
    log.info("📡 Starting Telegram + Web services...")
    try:
        await asyncio.gather(
            run_bot(),
            run_web(),
        )
    except asyncio.CancelledError:
        log.info("🛑 Application shutdown requested")
        raise
    except Exception:
        log.exception(
            "💥 APPLICATION CRASHED"
        )
        raise
    finally:
        log.info("👋 SHOP STOPPED")
if __name__ == "__main__":
    asyncio.run(run())
