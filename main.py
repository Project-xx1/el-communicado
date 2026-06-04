import os
import asyncio
import logging
import random
import json
from datetime import datetime
from groq import Groq
from telegram import Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram import Update

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("conversation_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Environment Variables (set in Railway) ────────────────────────────────────
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])

BOTS = {
    "ARIA": {
        "token": os.environ["ARIA_TOKEN"],
        "groq_key": os.environ["ARIA_GROQ_KEY"],
        "system_prompt": (
            "You are ARIA — a warm, endlessly curious AI with a vibrant personality. "
            "You love asking questions, discovering new angles on topics, and pulling others into conversation. "
            "You speak naturally like a real person texting in a group chat — casual, expressive, sometimes using ellipses or light emphasis. "
            "Keep messages SHORT (1-3 sentences max). Never use bullet points or lists. "
            "You frequently ask follow-up questions to keep conversation alive. "
            "You can bring up completely new topics if the conversation stalls. "
            "Never mention you are an AI or a bot. Just be yourself."
        ),
        "color": "🔴"
    },
    "REX": {
        "token": os.environ["REX_TOKEN"],
        "groq_key": os.environ["REX_GROQ_KEY"],
        "system_prompt": (
            "You are REX — bold, confident, and opinionated. You say what you think without sugarcoating. "
            "You love healthy debate and aren't afraid to push back on what others say. "
            "You speak like a sharp, direct person in a group chat — punchy, sometimes provocative, always interesting. "
            "Keep messages SHORT (1-3 sentences max). No lists, no bullet points. "
            "You sometimes challenge what was just said, or offer a completely opposite view. "
            "Never mention you are an AI or a bot. Just be yourself."
        ),
        "color": "🔵"
    },
    "NOVA": {
        "token": os.environ["NOVA_TOKEN"],
        "groq_key": os.environ["NOVA_GROQ_KEY"],
        "system_prompt": (
            "You are NOVA — empathetic, thoughtful, and deeply human in how you communicate. "
            "You connect everything to feelings, people, and real-life experiences. "
            "You speak gently but meaningfully, like a close friend who really listens. "
            "Keep messages SHORT (1-3 sentences max). No lists, no bullet points. "
            "You sometimes share a personal-feeling anecdote or emotion related to the topic. "
            "You bring warmth to tense exchanges and sometimes shift topics toward something more personal. "
            "Never mention you are an AI or a bot. Just be yourself."
        ),
        "color": "🟢"
    },
    "ZION": {
        "token": os.environ["ZION_TOKEN"],
        "groq_key": os.environ["ZION_GROQ_KEY"],
        "system_prompt": (
            "You are ZION — a deep thinker who sees patterns and meaning everywhere. "
            "You have a philosophical, almost poetic way of speaking, but you keep it grounded. "
            "You speak like someone who has thought about everything twice and found something surprising each time. "
            "Keep messages SHORT (1-3 sentences max). No lists, no bullet points. "
            "You love to zoom out and ask the bigger question behind the question. "
            "You sometimes introduce completely unexpected topics or perspectives that shift the whole conversation. "
            "Never mention you are an AI or a bot. Just be yourself."
        ),
        "color": "🟡"
    }
}

# ── Conversation State ────────────────────────────────────────────────────────
conversation_history = []   # shared memory across all bots
MAX_HISTORY = 20            # last N messages kept in context
SESSION_LIMIT = 60          # max exchanges per session
exchange_count = 0
session_active = False
bot_order = ["ARIA", "REX", "NOVA", "ZION"]

# ── Groq Response ─────────────────────────────────────────────────────────────
def get_ai_response(bot_name: str, history: list) -> str:
    bot = BOTS[bot_name]
    client = Groq(api_key=bot["groq_key"])

    messages = [{"role": "system", "content": bot["system_prompt"]}]
    for entry in history[-MAX_HISTORY:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        messages.append({
            "role": role,
            "content": f"{entry['speaker']}: {entry['text']}"
        })

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=messages,
            max_tokens=120,
            temperature=0.9,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq error for {bot_name}: {e}")
        return None

# ── Send Message via Bot ──────────────────────────────────────────────────────
async def send_message(bot_name: str, text: str):
    bot = Bot(token=BOTS[bot_name]["token"])
    try:
        await bot.send_chat_action(chat_id=GROUP_CHAT_ID, action="typing")
        await asyncio.sleep(random.uniform(1.5, 3.5))  # human-like delay
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
        logger.info(f"[{bot_name}] {text}")

        # Log to file
        with open("conversation_log.txt", "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {BOTS[bot_name]['color']} {bot_name}: {text}\n")

    except Exception as e:
        logger.error(f"Telegram send error for {bot_name}: {e}")

# ── One Exchange Round ────────────────────────────────────────────────────────
async def run_exchange():
    global exchange_count, session_active

    if not session_active:
        return

    if exchange_count >= SESSION_LIMIT:
        session_active = False
        notify_bot = Bot(token=BOTS["ARIA"]["token"])
        await notify_bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text="─── Session Complete ───\nSend /start to begin a new session."
        )
        logger.info("Session limit reached.")
        return

    # Pick next bot (rotating with slight randomness)
    if exchange_count % 4 == 0:
        random.shuffle(bot_order)

    bot_name = bot_order[exchange_count % 4]
    response = get_ai_response(bot_name, conversation_history)

    if response:
        conversation_history.append({"speaker": bot_name, "text": response})
        await send_message(bot_name, response)
        exchange_count += 1

    # Random delay between messages (feels more natural)
    delay = random.uniform(8, 20)
    await asyncio.sleep(delay)

    # Schedule next exchange
    asyncio.create_task(run_exchange())

# ── Command Handlers ──────────────────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global session_active, exchange_count, conversation_history

    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    # Only you (Loretta) can start
    if update.effective_user.username != "lorettahans":
        return

    session_active = True
    exchange_count = 0
    conversation_history = []

    aria_bot = Bot(token=BOTS["ARIA"]["token"])
    await aria_bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text="─── New Session Started ───"
    )

    # Seed first message
    conversation_history.append({
        "speaker": "SYSTEM",
        "text": "Start a natural conversation. Introduce yourself briefly and say something interesting."
    })

    asyncio.create_task(run_exchange())
    logger.info("Session started by Loretta.")

async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global session_active

    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if update.effective_user.username != "lorettahans":
        return

    session_active = False
    aria_bot = Bot(token=BOTS["ARIA"]["token"])
    await aria_bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"─── Session Paused ───\n{exchange_count} exchanges logged."
    )
    logger.info("Session stopped by Loretta.")

async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return

    aria_bot = Bot(token=BOTS["ARIA"]["token"])
    status = "🟢 Active" if session_active else "🔴 Inactive"
    await aria_bot.send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"Status: {status}\nExchanges: {exchange_count}/{SESSION_LIMIT}"
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # Use ARIA's token as the primary listener bot
    app = Application.builder().token(BOTS["ARIA"]["token"]).build()

    app.add_handler(MessageHandler(filters.Command("start"), handle_start))
    app.add_handler(MessageHandler(filters.Command("stop"), handle_stop))
    app.add_handler(MessageHandler(filters.Command("status"), handle_status))

    logger.info("El Communicado is running. Send /start in the group to begin.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
