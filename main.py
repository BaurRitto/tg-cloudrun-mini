import os
import httpx
from fastapi import FastAPI, Request

BOT_TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()

@app.get("/")
async def health():
    return {"status": "ok"}

async def send_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={
            "chat_id": chat_id,
            "text": text
        })

@app.post("/telegram/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message")

    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":
            await send_message(chat_id, "Hello from Cloud Run 🚀")
        else:
            await send_message(chat_id, f"You said: {text}")

    return {"ok": True}