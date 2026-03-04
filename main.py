import os
import httpx
from fastapi import FastAPI, Request

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# --- demo "database" in memory ---
MATCH_ID = "usa_iran"
MATCH_HOME = "USA"
MATCH_AWAY = "Iran"

PREDICTIONS: dict[int, tuple[int, int]] = {}
PENDING_HOME: dict[int, int] = {}

# --- UI: Reply keyboard (big buttons) ---
MAIN_MENU_KB = {
    "keyboard": [
        [{"text": "⚽ Predict"}, {"text": "🏆 Table"}],
        [{"text": "ℹ️ Help"}],
    ],
    "resize_keyboard": True,
    "one_time_keyboard": False,
}

def goals_keyboard(prefix: str) -> dict:
    row = [{"text": str(g), "callback_data": f"{prefix}:{MATCH_ID}:{g}"} for g in range(0, 6)]
    return {"inline_keyboard": [row]}

def predict_menu(chat_id: int) -> tuple[str, dict]:
    pred = PREDICTIONS.get(chat_id)
    if pred:
        text = f"⚽ {MATCH_HOME} vs {MATCH_AWAY}\nYour prediction: ✅ {pred[0]} - {pred[1]}\n\nTap to change:"
        kb = {"inline_keyboard": [[{"text": "Change prediction", "callback_data": f"start:{MATCH_ID}"}]]}
    else:
        text = f"⚽ {MATCH_HOME} vs {MATCH_AWAY}\nYour prediction: ⬜ not set\n\nTap to set:"
        kb = {"inline_keyboard": [[{"text": "Set prediction", "callback_data": f"start:{MATCH_ID}"}]]}
    return text, kb

async def tg(method: str, payload: dict):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{TELEGRAM_API}/{method}", json=payload)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data}")
        return data

@app.get("/")
async def health():
    return {"status": "ok", "version": "buttons-v1"}

@app.post("/telegram/webhook")
async def webhook(request: Request):
    update = await request.json()

    # --- handle normal messages ---
    msg = update.get("message")
    if msg and "text" in msg:
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip()

        # normalize button texts to actions
        if text == "⚽ Predict":
            text = "/predict"
        elif text == "🏆 Table":
            text = "/table"
        elif text == "ℹ️ Help":
            text = "/help"

        if text.startswith("/start"):
            await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "Welcome! Use the buttons below 👇",
                "reply_markup": MAIN_MENU_KB
            })

        elif text.startswith("/predict"):
            text_out, kb = predict_menu(chat_id)
            await tg("sendMessage", {
                "chat_id": chat_id,
                "text": text_out,
                "reply_markup": kb
            })

        elif text.startswith("/table"):
            # placeholder for later
            await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "🏆 Table is not implemented yet (next step).",
                "reply_markup": MAIN_MENU_KB
            })

        elif text.startswith("/help"):
            await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "Buttons:\n⚽ Predict — set your score\n🏆 Table — leaderboard (coming next)",
                "reply_markup": MAIN_MENU_KB
            })

        else:
            await tg("sendMessage", {
                "chat_id": chat_id,
                "text": "Use the buttons below 👇",
                "reply_markup": MAIN_MENU_KB
            })

        return {"ok": True}

    # --- handle button clicks (inline callback_query) ---
    cq = update.get("callback_query")
    if cq:
        cq_id = cq["id"]
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        message_id = cq["message"]["message_id"]

        await tg("answerCallbackQuery", {"callback_query_id": cq_id})

        if data.startswith("start:"):
            await tg("editMessageText", {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"Select {MATCH_HOME} goals:",
                "reply_markup": goals_keyboard("home")
            })
            return {"ok": True}

        if data.startswith("home:"):
            _, match_id, goals = data.split(":")
            if match_id == MATCH_ID:
                PENDING_HOME[chat_id] = int(goals)
                await tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": f"Selected: {MATCH_HOME} {goals} - ? {MATCH_AWAY}\n\nSelect {MATCH_AWAY} goals:",
                    "reply_markup": goals_keyboard("away")
                })
            return {"ok": True}

        if data.startswith("away:"):
            _, match_id, goals = data.split(":")
            if match_id == MATCH_ID:
                if chat_id not in PENDING_HOME:
                    await tg("editMessageText", {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": f"Select {MATCH_HOME} goals first:",
                        "reply_markup": goals_keyboard("home")
                    })
                    return {"ok": True}

                home_goals = PENDING_HOME.pop(chat_id)
                away_goals = int(goals)
                PREDICTIONS[chat_id] = (home_goals, away_goals)

                text_out, kb = predict_menu(chat_id)
                await tg("editMessageText", {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": f"✅ Saved prediction: {MATCH_HOME} {home_goals} - {away_goals} {MATCH_AWAY}\n\n{text_out}",
                    "reply_markup": kb
                })
            return {"ok": True}

    return {"ok": True}