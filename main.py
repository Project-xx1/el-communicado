import os
import asyncio
import logging
import random
import threading
from datetime import datetime
from groq import Groq
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("conversation_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])

BOTS = {
    "ARIA": {
        "token": os.environ["ARIA_TOKEN"],
        "groq_key": os.environ["ARIA_GROQ_KEY"],
        "color": "🔴",
        "system_prompt": (
            "You are ARIA — curious, warm, energetic. You love asking questions and keeping "
            "conversation alive. You text like a real person in a group chat — short, casual, "
            "expressive. Max 2 sentences. No lists. Never say you are an AI or bot."
        ),
    },
    "REX": {
        "token": os.environ["REX_TOKEN"],
        "groq_key": os.environ["REX_GROQ_KEY"],
        "color": "🔵",
        "system_prompt": (
            "You are REX — bold, direct, opinionated. You say what you think and love debating. "
            "You text like a confident person in a group chat — punchy, sometimes provocative. "
            "Max 2 sentences. No lists. Never say you are an AI or bot."
        ),
    },
    "NOVA": {
        "token": os.environ["NOVA_TOKEN"],
        "groq_key": os.environ["NOVA_GROQ_KEY"],
        "color": "🟢",
        "system_prompt": (
            "You are NOVA — empathetic, thoughtful, human. You connect topics to feelings and "
            "real life. You text like a close friend — gentle but meaningful. "
            "Max 2 sentences. No lists. Never say you are an AI or bot."
        ),
    },
    "ZION": {
        "token": os.environ["ZION_TOKEN"],
        "groq_key": os.environ["ZION_GROQ_KEY"],
        "color": "🟡",
        "system_prompt": (
            "You are ZION — philosophical, deep, unpredictable. You find meaning in everything "
            "and often shift topics in surprising directions. You text like a thinker — poetic "
            "but grounded. Max 2 sentences. No lists. Never say you are an AI or bot."
        ),
    },
}

BOT_NAMES = ["ARIA", "REX", "NOVA", "ZION"]

# ── State ─────────────────────────────────────────────────────────────────────
state = {
    "active": False,
    "history": [],
    "count": 0,
    "limit": 60,
}

# ── Groq Call ─────────────────────────────────────────────────────────────────
def get_response(bot_name: str) -> str:
    cfg = BOTS[bot_name]
    client = Groq(api_key=cfg["groq_key"])

    messages = [{"role": "system", "content": cfg["system_prompt"]}]

    for entry in state["history"][-16:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        messages.append({"role": role, "content": f"{entry['speaker']}: {entry['text']}"})

    try:
        res = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            max_tokens=100,
            temperature=0.92,
        )
        return res.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error [{bot_name}]: {e}")
        return None

# ── Telegram Send ─────────────────────────────────────────────────────────────
async def send(bot_name: str, text: str):
    bot = Bot(token=BOTS[bot_name]["token"])
    try:
        await bot.send_chat_action(chat_id=GROUP_CHAT_ID, action="typing")
        await asyncio.sleep(random.uniform(2, 4))
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
        logger.info(f"{BOTS[bot_name]['color']} {bot_name}: {text}")
        with open("conversation_log.txt", "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {BOTS[bot_name]['color']} {bot_name}: {text}\n")
    except Exception as e:
        logger.error(f"Send error [{bot_name}]: {e}")

# ── Conversation Loop (runs in background thread) ─────────────────────────────
def conversation_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        order = BOT_NAMES.copy()
        random.shuffle(order)

        # Seed opening
        state["history"].append({
            "speaker": "SYSTEM",
            "text": "Start a natural casual conversation. Introduce yourself briefly and say something interesting or ask something."
        })

        while state["active"] and state["count"] < state["limit"]:
            bot_name = order[state["count"] % 4]
            if state["count"] % 4 == 0:
                random.shuffle(order)

            text = get_response(bot_name)
            if text:
                state["history"].append({"speaker": bot_name, "text": text})
                await send(bot_name, text)
                state["count"] += 1
                await asyncio.sleep(random.uniform(8, 18))
            else:
                await asyncio.sleep(5)

        if state["count"] >= state["limit"]:
            bot = Bot(token=BOTS["ARIA"]["token"])
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"─── Session Complete ───\n{state['count']} exchanges logged.\nSend /start for a new session."
            )
            state["active"] = False

    loop.run_until_complete(run())
    loop.close()

# ── Command Handlers ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if update.effective_user.username != "lorettahans":
        return

    if state["active"]:
        await Bot(token=BOTS["ARIA"]["token"]).send_message(
            chat_id=GROUP_CHAT_ID, text="A session is already running. Send /stop first."
        )
        return

    state["active"] = True
    state["count"] = 0
    state["history"] = []

    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text="─── New Session Started ───"
    )
    logger.info("Session started.")

    t = threading.Thread(target=conversation_loop, daemon=True)
    t.start()

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if update.effective_user.username != "lorettahans":
        return

    state["active"] = False
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"─── Session Stopped ───\n{state['count']} exchanges logged."
    )
    logger.info("Session stopped.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    status = "🟢 Active" if state["active"] else "🔴 Inactive"
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"Status: {status}\nExchanges: {state['count']}/{state['limit']}"
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOTS["ARIA"]["token"]).build()
    app.add_handler(MessageHandler(filters.Regex(r"^/start"), cmd_start))
    app.add_handler(MessageHandler(filters.Regex(r"^/stop"), cmd_stop))
    app.add_handler(MessageHandler(filters.Regex(r"^/status"), cmd_status))

    logger.info("El Communicado is online. Send /start in the group.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
