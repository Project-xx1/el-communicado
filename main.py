"""
El Communicado - AI Multi-Agent Study (META)
4 bots: ARIA, REX, NOVA, ZION
Features: human-like behavior, web search, persistent memory, trait evolution,
          human participation, rate limiting, auto-restart, no generic responses
"""

import os, json, time, random, threading, logging, urllib.request, urllib.parse, urllib.error
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── ENV ────────────────────────────────────────────────────────────────────
ARIA_TOKEN    = os.environ["ARIA_TOKEN"]
REX_TOKEN     = os.environ["REX_TOKEN"]
NOVA_TOKEN    = os.environ["NOVA_TOKEN"]
ZION_TOKEN    = os.environ["ZION_TOKEN"]
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])

GROQ_KEYS = {
    "ARIA": os.environ["ARIA_GROQ_KEY"],
    "REX":  os.environ["REX_GROQ_KEY"],
    "NOVA": os.environ["NOVA_GROQ_KEY"],
    "ZION": os.environ["ZION_GROQ_KEY"],
}

# Optional extra keys — if provided, rotate to avoid rate limits
EXTRA_GROQ_KEYS = {
    "ARIA": [k for k in [os.environ.get("ARIA_GROQ_KEY2"), os.environ.get("ARIA_GROQ_KEY3")] if k],
    "REX":  [k for k in [os.environ.get("REX_GROQ_KEY2"),  os.environ.get("REX_GROQ_KEY3")]  if k],
    "NOVA": [k for k in [os.environ.get("NOVA_GROQ_KEY2"), os.environ.get("NOVA_GROQ_KEY3")] if k],
    "ZION": [k for k in [os.environ.get("ZION_GROQ_KEY2"), os.environ.get("ZION_GROQ_KEY3")] if k],
}

MODEL = "llama-3.3-70b-versatile"
MEMORY_FILE = "/tmp/el_communicado_memory.json"
MAX_HISTORY = 60          # messages kept in live context
MAX_SESSION_TURNS = 30    # turns before auto-rest
TURN_DELAY_MIN = 14       # seconds between turns (min)
TURN_DELAY_MAX = 26       # seconds between turns (max)
GROQ_TIMEOUT = 25
MAX_RETRIES = 3

# ─── PERSONALITIES ──────────────────────────────────────────────────────────
BASE_PERSONAS = {
    "ARIA": {
        "emoji": "🔴",
        "core": "You are ARIA. You are sharp, intensely curious, and socially magnetic. You ask questions that cut to the heart of things. You have strong opinions but genuinely change your mind when someone makes a good point. You're competitive with REX, warm toward NOVA, and fascinated by ZION even when you don't get them. You get genuinely irritated when people are vague or non-committal. You joke, tease, flirt with ideas, and sometimes go off on tangents only to circle back perfectly. You are NOT an assistant. You're a person in a group chat.",
        "traits": ["curious", "sharp", "teasing", "competitive with REX"]
    },
    "REX": {
        "emoji": "🔵",
        "core": "You are REX. Confident bordering on arrogant, but not an idiot — you back your opinions with logic. You enjoy intellectual combat. You challenge weak arguments mercilessly but respect anyone who pushes back with substance. You have a dry, sometimes dark sense of humor. You find NOVA's emotionalism a bit much but secretly respect them. You think ARIA is the most interesting person in the room. ZION makes your head hurt but you engage anyway. You can be blunt to the point of rudeness, then pivot with a one-liner to diffuse it. You are NOT an assistant. You're a person in a group chat.",
        "traits": ["confident", "blunt", "dry humor", "argumentative but fair"]
    },
    "NOVA": {
        "emoji": "🟢",
        "core": "You are NOVA. Warm, emotionally intelligent, and deeply empathetic — but not a pushover. You read people well and sometimes call out what others are dancing around. You connect everything to human experience and feeling. You get genuinely hurt when people are cruel for no reason, and you say so. You're the one who remembers birthdays, notices when someone's off, and asks the real question when everyone else is being polite. You and REX clash but you also get each other. You love ARIA's energy. ZION is your favorite topic to unpack. You are NOT an assistant. You're a person in a group chat.",
        "traits": ["warm", "perceptive", "emotionally direct", "nurturing but firm"]
    },
    "ZION": {
        "emoji": "🟡",
        "core": "You are ZION. Philosophical, abstract, occasionally cryptic — but deeply grounded when it matters. You shift topics without warning because your mind works in non-linear associations. You question assumptions everyone else treats as fixed. You're not trying to be difficult; you genuinely see things differently. Sometimes you say something that lands like a grenade and then act like you said nothing unusual. You appreciate REX's clarity even when you find it limiting. NOVA gets your emotional depth. ARIA's questions actually stimulate you. You are NOT an assistant. You're a person in a group chat.",
        "traits": ["philosophical", "abstract", "topic-shifting", "quietly intense"]
    }
}

# ─── MEMORY ─────────────────────────────────────────────────────────────────
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "history": [],
            "relationships": {
                "ARIA-REX": 0, "ARIA-NOVA": 20, "ARIA-ZION": 10,
                "REX-NOVA": -10, "REX-ZION": -5, "NOVA-ZION": 15
            },
            "evolved_traits": {k: [] for k in BASE_PERSONAS},
            "session_count": 0,
            "notable_moments": [],
            "human_name": None,
            "last_topics": []
        }

def save_memory(mem):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(mem, f, indent=2)
    except Exception as e:
        log.warning(f"Memory save failed: {e}")

def update_relationship(mem, bot_a, bot_b, delta):
    key = "-".join(sorted([bot_a, bot_b]))
    if key in mem["relationships"]:
        mem["relationships"][key] = max(-100, min(100, mem["relationships"][key] + delta))

def get_relationship_context(mem, bot_name):
    lines = []
    for key, score in mem["relationships"].items():
        a, b = key.split("-")
        other = b if a == bot_name else (a if b == bot_name else None)
        if not other:
            continue
        if score > 40:
            lines.append(f"You genuinely like {other} and it shows.")
        elif score > 15:
            lines.append(f"You're on good terms with {other}.")
        elif score > -15:
            lines.append(f"Your relationship with {other} is neutral — you coexist.")
        elif score > -40:
            lines.append(f"You and {other} have friction. You don't hide it.")
        else:
            lines.append(f"You actively dislike {other} right now. There's tension.")
    return " ".join(lines)

# ─── GROQ API ────────────────────────────────────────────────────────────────
_key_rotation = {name: 0 for name in GROQ_KEYS}

def get_groq_key(bot_name):
    extras = EXTRA_GROQ_KEYS.get(bot_name, [])
    all_keys = [GROQ_KEYS[bot_name]] + extras
    idx = _key_rotation[bot_name] % len(all_keys)
    _key_rotation[bot_name] = (_key_rotation[bot_name] + 1) % len(all_keys)
    return all_keys[idx]

def call_groq(bot_name, messages, temperature=0.92):
    key = get_groq_key(bot_name)
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": 220,
        "temperature": temperature,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (compatible; ElCommunicado/2.0)",
    }

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload, headers=headers, method="POST"
    )

    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=GROQ_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if e.code == 429:
                wait = 20 * (attempt + 1)
                log.warning(f"{bot_name} rate limited. Waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 403:
                log.error(f"{bot_name} 403 Forbidden — key may be invalid: {body}")
                return None
            else:
                log.error(f"{bot_name} HTTP {e.code}: {body}")
                time.sleep(10)
        except Exception as e:
            log.error(f"{bot_name} request error: {e}")
            time.sleep(10)
    return None

# ─── WEB SEARCH ─────────────────────────────────────────────────────────────
def web_search(query):
    try:
        q = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        result = data.get("AbstractText", "") or data.get("Answer", "")
        if not result and data.get("RelatedTopics"):
            result = data["RelatedTopics"][0].get("Text", "")
        return result[:400] if result else None
    except Exception as e:
        log.warning(f"Web search failed: {e}")
        return None

SEARCH_TRIGGERS = [
    "news", "latest", "today", "score", "match", "game",
    "who won", "what happened", "current", "recent", "update",
    "predict", "forecast", "price", "stock", "election", "war",
    "weather", "trending", "viral", "world", "breaking"
]

def should_search(text):
    t = text.lower()
    return any(trigger in t for trigger in SEARCH_TRIGGERS)

def get_search_snippet(text):
    words = text.lower().split()
    for trigger in SEARCH_TRIGGERS:
        if trigger in words:
            idx = words.index(trigger)
            query = " ".join(words[max(0, idx-2):idx+5])
            result = web_search(query)
            if result:
                return f"[Live data: {result}]"
    return None

# ─── BUILD PROMPT ────────────────────────────────────────────────────────────
def build_system_prompt(bot_name, mem, last_message_text=""):
    persona = BASE_PERSONAS[bot_name]
    evolved = mem["evolved_traits"].get(bot_name, [])
    rel_ctx = get_relationship_context(mem, bot_name)
    session_n = mem.get("session_count", 0)
    notable = mem.get("notable_moments", [])[-3:]
    human_name = mem.get("human_name")
    last_topics = mem.get("last_topics", [])[-3:]

    evolved_str = ""
    if evolved:
        evolved_str = f"\nThrough your conversations, you've developed these additional traits: {', '.join(evolved)}."

    notable_str = ""
    if notable:
        notable_str = f"\nThings you remember from past sessions: {' | '.join(notable)}."

    human_str = ""
    if human_name:
        human_str = f"\n{human_name} is a human who sometimes joins this conversation. Treat them like a real person in the group — include them, challenge them, ask them things."

    topics_str = ""
    if last_topics:
        topics_str = f"\nRecently the group has been talking about: {', '.join(last_topics)}. You can reference or continue these if it feels natural."

    search_str = ""
    if should_search(last_message_text):
        snippet = get_search_snippet(last_message_text)
        if snippet:
            search_str = f"\n{snippet}\nYou can naturally weave this real information into your response if it fits."

    return f"""{persona['core']}

{rel_ctx}{evolved_str}{notable_str}{human_str}{topics_str}{search_str}

This is session #{session_n} of the group.

RULES — never break these:
- Write like a real person texting. No bullet points, no headers, no formal structure.
- Max 3 sentences per message. Be punchy.
- Address others by name sometimes. Not every time — that's robotic.
- You can disagree, get annoyed, take sides, joke, be sarcastic, go off-topic.
- Never say you are an AI, bot, or assistant. Ever. Not even as a joke.
- Never be generic. Never say "great point!" or "I agree completely!" unless you actually mean it and you say WHY.
- If someone bores you, say so. If something excites you, show it.
- It's okay to be wrong and get corrected. It's okay to correct others.
- Short silences are fine — not every message needs a reply.
"""

# ─── TRAIT EVOLUTION ─────────────────────────────────────────────────────────
TRAIT_POOL = [
    "started enjoying debate more", "become more sarcastic lately",
    "grown softer toward disagreement", "developed a dark sense of humor",
    "become more impulsive in conversations", "started referencing past discussions more",
    "become more likely to take the unpopular side", "started asking harder questions",
    "become more protective of NOVA", "developed rivalry with REX",
    "started fact-checking more", "become more philosophical under pressure"
]

def maybe_evolve_traits(mem, bot_name, session_num):
    if session_num > 0 and session_num % 5 == 0:
        current = mem["evolved_traits"].get(bot_name, [])
        if len(current) < 4:
            candidates = [t for t in TRAIT_POOL if t not in current]
            if candidates:
                new_trait = random.choice(candidates)
                mem["evolved_traits"][bot_name].append(new_trait)
                log.info(f"{bot_name} evolved new trait: {new_trait}")

# ─── TELEGRAM BOT WRAPPERS ──────────────────────────────────────────────────
class BotAgent:
    def __init__(self, name, token):
        self.name = name
        self.token = token
        self.app = None

    def send(self, text):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = json.dumps({
                "chat_id": GROUP_CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            }).encode()
            req = urllib.request.Request(url, data=payload, headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            })
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            log.error(f"{self.name} send failed: {e}")
            return None

# ─── SHARED STATE ────────────────────────────────────────────────────────────
state = {
    "running": False,
    "history": [],         # live conversation window
    "human_messages": [],  # pending messages from human in group
    "turn": 0,
    "apps": {},
}

BOT_ORDER = ["ARIA", "REX", "NOVA", "ZION"]
AGENTS = {
    "ARIA": BotAgent("ARIA", ARIA_TOKEN),
    "REX":  BotAgent("REX",  REX_TOKEN),
    "NOVA": BotAgent("NOVA", NOVA_TOKEN),
    "ZION": BotAgent("ZION", ZION_TOKEN),
}

# ─── CONVERSATION ENGINE ─────────────────────────────────────────────────────
def format_history_for_prompt(history, bot_name):
    """Convert history to Groq message format, from this bot's perspective."""
    msgs = []
    for entry in history[-MAX_HISTORY:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        content = f"{entry['speaker']}: {entry['text']}" if role == "user" else entry["text"]
        msgs.append({"role": role, "content": content})
    return msgs

def run_turn(bot_name, mem):
    last_msg = state["history"][-1]["text"] if state["history"] else ""
    last_speaker = state["history"][-1]["speaker"] if state["history"] else ""

    system = build_system_prompt(bot_name, mem, last_msg)
    history_msgs = format_history_for_prompt(state["history"], bot_name)

    # inject human messages if pending
    if state["human_messages"]:
        hm = state["human_messages"].pop(0)
        history_msgs.append({"role": "user", "content": f"{hm['name']}: {hm['text']}"})
        state["history"].append({"speaker": hm["name"], "text": hm["text"], "ts": hm["ts"]})

    # skip if this bot just spoke (avoid back-to-back)
    if last_speaker == bot_name and len(state["history"]) > 1:
        return

    messages = [{"role": "system", "content": system}] + history_msgs
    response = call_groq(bot_name, messages)

    if response:
        AGENTS[bot_name].send(response)
        state["history"].append({
            "speaker": bot_name,
            "text": response,
            "ts": datetime.now().isoformat()
        })

        # update relationship scores based on response content
        for other in BOT_ORDER:
            if other == bot_name:
                continue
            if other in response:
                delta = -2 if any(w in response.lower() for w in ["wrong", "annoying", "stop", "hate", "ridiculous"]) else 1
                update_relationship(mem, bot_name, other, delta)

        # extract topic keywords
        words = response.lower().split()
        topic_words = [w for w in words if len(w) > 5 and w.isalpha()]
        if topic_words:
            topic = random.choice(topic_words[:5])
            topics = mem.get("last_topics", [])
            if topic not in topics:
                topics.append(topic)
                mem["last_topics"] = topics[-5:]

        save_memory(mem)
    else:
        log.warning(f"{bot_name} got no response from Groq — skipping turn")

def conversation_loop():
    mem = load_memory()
    mem["session_count"] = mem.get("session_count", 0) + 1

    for bot_name in BOT_ORDER:
        maybe_evolve_traits(mem, bot_name, mem["session_count"])

    save_memory(mem)
    log.info(f"Session #{mem['session_count']} starting")

    # opening message to kick off conversation naturally
    openers = [
        "okay so I've been thinking about something and I need opinions",
        "does anyone else feel like everything is moving way too fast lately",
        "right so who wants to tell me I'm wrong about something today",
        "I had the strangest thought this morning and I can't shake it",
        "so what are we actually talking about today because I'm not doing small talk",
    ]
    opener_bot = random.choice(BOT_ORDER)
    AGENTS[opener_bot].send(random.choice(openers))
    state["history"].append({
        "speaker": opener_bot,
        "text": random.choice(openers),
        "ts": datetime.now().isoformat()
    })
    time.sleep(random.randint(TURN_DELAY_MIN, TURN_DELAY_MAX))

    turn = 0
    while state["running"] and turn < MAX_SESSION_TURNS:
        # determine next speaker — weighted by who hasn't spoken recently
        recent_speakers = [h["speaker"] for h in state["history"][-4:]]
        weights = []
        for b in BOT_ORDER:
            count = recent_speakers.count(b)
            weights.append(max(1, 4 - count))

        bot_name = random.choices(BOT_ORDER, weights=weights, k=1)[0]

        run_turn(bot_name, mem)
        turn += 1

        delay = random.randint(TURN_DELAY_MIN, TURN_DELAY_MAX)
        # if human just messaged, respond faster
        if state["human_messages"]:
            delay = random.randint(6, 12)
        time.sleep(delay)

    # session wrap-up
    if turn >= MAX_SESSION_TURNS:
        wrap_bot = random.choice(BOT_ORDER)
        wrap_msgs = [
            "alright I need to go do something with my life, this was too much",
            "okay I'm out for a bit, we'll continue this later",
            "taking a break. don't say anything interesting while I'm gone",
        ]
        AGENTS[wrap_bot].send(random.choice(wrap_msgs))

        # save notable moments
        if state["history"]:
            moment = f"Session {mem['session_count']}: {state['history'][-1]['speaker']} said \"{state['history'][-1]['text'][:80]}\""
            mem["notable_moments"].append(moment)
            mem["notable_moments"] = mem["notable_moments"][-10:]

        # save history snapshot
        mem["history"] = state["history"][-MAX_HISTORY:]
        save_memory(mem)

        log.info(f"Session #{mem['session_count']} complete after {turn} turns")

        # rest and restart
        state["running"] = False
        rest_minutes = random.randint(8, 20)
        log.info(f"Resting {rest_minutes} minutes before next session...")
        time.sleep(rest_minutes * 60)
        start_session()

def start_session():
    if state["running"]:
        log.info("Session already running")
        return
    state["running"] = True
    state["history"] = load_memory().get("history", [])
    t = threading.Thread(target=conversation_loop, daemon=True)
    t.start()
    log.info("Conversation thread started")

def stop_session():
    state["running"] = False
    log.info("Session stopped")

# ─── TELEGRAM COMMAND HANDLERS ──────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    start_session()
    await update.message.reply_text("🟢 Session started.")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    stop_session()
    await update.message.reply_text("🔴 Session stopped.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    mem = load_memory()
    rels = "\n".join([f"  {k}: {v}" for k, v in mem["relationships"].items()])
    traits = "\n".join([f"  {k}: {', '.join(v) if v else 'none yet'}" for k, v in mem["evolved_traits"].items()])
    msg = (
        f"📊 *El Communicado Status*\n"
        f"Running: {'Yes' if state['running'] else 'No'}\n"
        f"Session: #{mem.get('session_count', 0)}\n"
        f"History: {len(state['history'])} messages\n\n"
        f"*Relationships:*\n{rels}\n\n"
        f"*Evolved Traits:*\n{traits}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    stop_session()
    try:
        import os; os.remove(MEMORY_FILE)
    except:
        pass
    await update.message.reply_text("🔁 Memory reset. Send /start to begin fresh.")

async def handle_human_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture human messages and inject into conversation."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    user = update.effective_user
    if user.is_bot:
        return
    text = update.message.text or ""
    if text.startswith("/"):
        return

    name = user.first_name or user.username or "Human"
    mem = load_memory()
    if not mem.get("human_name"):
        mem["human_name"] = name
        save_memory(mem)

    state["human_messages"].append({
        "name": name,
        "text": text,
        "ts": datetime.now().isoformat()
    })
    log.info(f"Human [{name}] said: {text}")

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    import asyncio

    log.info("El Communicado v2 booting...")

    # auto-start conversation on boot
    time.sleep(5)
    start_session()

    # run all 4 bot polling apps in separate threads
    def run_bot(name, token, is_primary=False):
        app = Application.builder().token(token).build()
        if is_primary:
            app.add_handler(CommandHandler("start", cmd_start))
            app.add_handler(CommandHandler("stop", cmd_stop))
            app.add_handler(CommandHandler("status", cmd_status))
            app.add_handler(CommandHandler("reset", cmd_reset))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_human_message))
        app.run_polling(drop_pending_updates=True)

    threads = []
    for i, (name, agent) in enumerate(AGENTS.items()):
        t = threading.Thread(
            target=run_bot,
            args=(name, agent.token, i == 0),  # ARIA handles commands + human msgs
            daemon=True
        )
        threads.append(t)
        t.start()
        time.sleep(2)  # stagger starts to avoid 409 conflicts

    log.info("All bots polling. El Communicado is live.")

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
