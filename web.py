from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from config import get_settings

app = FastAPI(title="Shop Health")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def root():
    return "<h1>Shop is running</h1><p>Telegram bot is active.</p>"
