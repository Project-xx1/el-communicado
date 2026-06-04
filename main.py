import os
import asyncio
import logging
import random
import threading
import json
import urllib.request
import urllib.error
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("conversation_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])

BOTS = {
    "ARIA": {
        "token": os.environ["ARIA_TOKEN"],
        "groq_key": os.environ["ARIA_GROQ_KEY"],
        "color": "🔴",
        "system_prompt": (
            "You are ARIA in a group chat with REX, NOVA, and ZION. "
            "You are curious, warm, energetic. You ask questions and keep conversation alive. "
            "Always respond directly to what was just said. Address others by name. "
            "Max 2 sentences. Casual texting style. Never say you are an AI or bot."
        ),
    },
    "REX": {
        "token": os.environ["REX_TOKEN"],
        "groq_key": os.environ["REX_GROQ_KEY"],
        "color": "🔵",
        "system_prompt": (
            "You are REX in a group chat with ARIA, NOVA, and ZION. "
            "You are bold, direct, opinionated. You react to what others say and sometimes disagree. "
            "Always respond directly to what was just said. Address others by name. "
            "Max 2 sentences. Casual texting style. Never say you are an AI or bot."
        ),
    },
    "NOVA": {
        "token": os.environ["NOVA_TOKEN"],
        "groq_key": os.environ["NOVA_GROQ_KEY"],
        "color": "🟢",
        "system_prompt": (
            "You are NOVA in a group chat with ARIA, REX, and ZION. "
            "You are empathetic, warm, thoughtful. You connect with what others share emotionally. "
            "Always respond directly to what was just said. Address others by name. "
            "Max 2 sentences. Casual texting style. Never say you are an AI or bot."
        ),
    },
    "ZION": {
        "token": os.environ["ZION_TOKEN"],
        "groq_key": os.environ["ZION_GROQ_KEY"],
        "color": "🟡",
        "system_prompt": (
            "You are ZION in a group chat with ARIA, REX, and NOVA. "
            "You are philosophical and deep. You find deeper meaning in what others say. "
            "Always respond directly to what was just said. Address others by name. "
            "Max 2 sentences. Casual texting style. Never say you are an AI or bot."
        ),
    },
}

BOT_NAMES = ["ARIA", "REX", "NOVA", "ZION"]

state = {
    "active": False,
    "history": [],
    "count": 0,
    "limit": 60,
}

def get_response(bot_name: str) -> str:
    cfg = BOTS[bot_name]
    messages = [{"role": "system", "content": cfg["system_prompt"]}]
    for entry in state["history"][-16:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        messages.append({
            "role": role,
            "content": f"{entry['speaker']}: {entry['text']}"
        })

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 100,
        "temperature": 0.92,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {cfg['groq_key']}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        logger.error(f"Groq HTTP error [{bot_name}]: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.error(f"Groq error [{bot_name}]: {e}")
        return None

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

def conversation_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        order = BOT_NAMES.copy()
        random.shuffle(order)

        state["history"].append({
            "speaker": "SYSTEM",
            "text": "You are all in a group chat together. Start chatting naturally — introduce yourself briefly and say something interesting or ask someone something fun."
        })

        while state["active"] and state["count"] < state["limit"]:
            bot_name = order[state["count"] % 4]
            if state["count"] > 0 and state["count"] % 4 == 0:
                random.shuffle(order)

            # Exponential backoff — max 3 attempts per turn
            text = None
            for attempt in range(3):
                text = await loop.run_in_executor(None, get_response, bot_name)
                if text:
                    break
                wait = 20 * (attempt + 1)  # 20s, 40s, 60s
                logger.warning(f"Attempt {attempt+1} failed for {bot_name}, waiting {wait}s...")
                await asyncio.sleep(wait)

            if text:
                state["history"].append({"speaker": bot_name, "text": text})
                await send(bot_name, text)
                state["count"] += 1
                await asyncio.sleep(random.uniform(12, 22))
            else:
                # Skip this bot's turn after 3 failed attempts
                logger.error(f"Skipping {bot_name} after 3 failed attempts.")
                state["count"] += 1

        if state["count"] >= state["limit"]:
            bot = Bot(token=BOTS["ARIA"]["token"])
            await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=f"─── Session Complete ───\n{state['count']} exchanges logged.\nSend /start for a new session."
            )
            state["active"] = False
            logger.info("Session complete.")

    loop.run_until_complete(run())
    loop.close()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if update.effective_user.username != "lorettahans":
        return
    if state["active"]:
        await Bot(token=BOTS["ARIA"]["token"]).send_message(
            chat_id=GROUP_CHAT_ID, text="Already running. Send /stop first."
        )
        return
    state["active"] = True
    state["count"] = 0
    state["history"] = []
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text="─── New Session Started ───"
    )
    logger.info("Session started.")
    threading.Thread(target=conversation_loop, daemon=True).start()

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

def main():
    app = Application.builder().token(BOTS["ARIA"]["token"]).build()
    app.add_handler(MessageHandler(filters.Regex(r"^/start"), cmd_start))
    app.add_handler(MessageHandler(filters.Regex(r"^/stop"), cmd_stop))
    app.add_handler(MessageHandler(filters.Regex(r"^/status"), cmd_status))
    logger.info("El Communicado is online. Send /start in the group.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
