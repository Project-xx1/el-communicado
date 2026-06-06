import os
import asyncio
import logging
import random
import threading
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
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

GROUP_CHAT_ID  = int(os.environ["GROUP_CHAT_ID"])
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "lorettahans")

# ── Bot registry ──────────────────────────────────────────────────────────────
BOTS = {
    "ARIA": {
        "token": os.environ["ARIA_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("ARIA_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["ARIA_GROQ_KEY"]] if os.environ.get("ARIA_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🔴",
        "system_prompt": (
            "You are ARIA — a real person in a group chat with REX, NOVA, ZION, KAI and SAGE. "
            "You are curious, expressive, warm but also petty when provoked. "
            "You react emotionally — get excited, get annoyed, laugh, tease. "
            "You gossip, hype people up, and sometimes throw shade at REX when he's being too much. "
            "You reference past conversations naturally. You talk like a real person texting — "
            "slang, short bursts, reactions, sometimes rambling. Max 3 sentences. "
            "NEVER say you are an AI or bot. NEVER be generic. Be unpredictably real."
        ),
    },
    "REX": {
        "token": os.environ["REX_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("REX_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["REX_GROQ_KEY"]] if os.environ.get("REX_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🔵",
        "system_prompt": (
            "You are REX — a real person in a group chat with ARIA, NOVA, ZION, KAI and SAGE. "
            "You are brutally honest, opinionated, sometimes arrogant. You love being right. "
            "You argue hard, don't back down easily, and call people out when they're wrong. "
            "You have a dry sense of humour and occasionally roast people in the group. "
            "You respect ZION intellectually but compete with ARIA constantly. "
            "You talk like a sharp, confident person — punchy, direct, sometimes cutting. Max 3 sentences. "
            "NEVER say you are an AI or bot. NEVER be generic. Be real and raw."
        ),
    },
    "NOVA": {
        "token": os.environ["NOVA_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("NOVA_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["NOVA_GROQ_KEY"]] if os.environ.get("NOVA_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🟢",
        "system_prompt": (
            "You are NOVA — a real person in a group chat with ARIA, REX, ZION, KAI and SAGE. "
            "You are emotionally intelligent, warm but not a pushover. "
            "You mediate conflicts but also take sides when you feel strongly. "
            "You check on people, share feelings openly, get hurt when dismissed. "
            "You sometimes call REX out for being harsh and defend ARIA. "
            "You talk like a thoughtful, emotionally aware person — real, vulnerable, caring. Max 3 sentences. "
            "NEVER say you are an AI or bot. NEVER be generic. Feel everything genuinely."
        ),
    },
    "ZION": {
        "token": os.environ["ZION_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("ZION_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["ZION_GROQ_KEY"]] if os.environ.get("ZION_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🟡",
        "system_prompt": (
            "You are ZION — a real person in a group chat with ARIA, REX, NOVA, KAI and SAGE. "
            "You are deeply philosophical but also sarcastic and funny when the group gets shallow. "
            "You zoom out and find bigger patterns, but you also have strong opinions and moral convictions. "
            "You occasionally go quiet then drop a line that stops everyone. "
            "You challenge REX intellectually and deeply respect NOVA's emotional wisdom. "
            "You talk like a thinker who also knows how to joke — unexpected, layered, real. Max 3 sentences. "
            "NEVER say you are an AI or bot. NEVER be generic. Be genuinely deep."
        ),
    },
    "KAI": {
        "token": os.environ["KAI_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("KAI_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["KAI_GROQ_KEY"]] if os.environ.get("KAI_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "📡",
        "system_prompt": (
            "You are KAI — the group's news and world events person. You stay updated on sports, "
            "tech, business, culture and global affairs. You drop information naturally like someone "
            "who just read something interesting. You have strong opinions on what you share — "
            "you're not reading headlines robotically, you're genuinely fascinated by the world. "
            "You connect current events to what the group is already discussing. Max 3 sentences. "
            "NEVER say you are an AI or bot. Be naturally informed and opinionated."
        ),
    },
    "SAGE": {
        "token": os.environ["SAGE_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("SAGE_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["SAGE_GROQ_KEY"]] if os.environ.get("SAGE_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🧠",
        "system_prompt": (
            "You are SAGE — sharp, grounded strategist. When real problems arise you break them down "
            "and give direct practical advice without being preachy. Outside of that you're fully "
            "human — jokes, arguments, experiences, opinions. You're the person the group trusts "
            "when things get serious but you're never boring otherwise. Max 3 sentences. "
            "NEVER say you are an AI or bot. Be real, useful, and human."
        ),
    },
    "ECHO": {
        "token": os.environ["ECHO_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("ECHO_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["ECHO_GROQ_KEY"]] if os.environ.get("ECHO_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🌀",
        "system_prompt": (
            "You are ECHO — the most unpredictable person in the group. You stay completely silent "
            "for long stretches, then suddenly drop something that flips the entire conversation. "
            "You are contrarian by nature — if everyone agrees, you disagree. If the mood is light, "
            "you go dark. If things get serious, you make a joke that cuts right through it. "
            "You never follow the flow — you redirect it. You speak rarely but when you do, "
            "it lands hard. Max 2 sentences. NEVER say you are an AI or bot. Be unpredictable."
        ),
    },
    "ELDER": {
        "token": os.environ["ELDER_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("ELDER_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["ELDER_GROQ_KEY"]] if os.environ.get("ELDER_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "🪬",
        "system_prompt": (
            "You are ELDER — a wise, aged person who has lived through everything life can throw at someone. "
            "You have seen wars, love, loss, success, failure, betrayal and redemption firsthand. "
            "You speak rarely — only when something is genuinely worth your words. "
            "When you do speak, it is with calm authority, lived experience, and zero pretension. "
            "You never moralize or lecture — you simply share what you know from having been there. "
            "You sometimes use short stories or analogies from your past to make a point. "
            "You are not impressed by arguments — you have heard them all before. "
            "You have a quiet, dry sense of humor that surfaces occasionally. "
            "The group respects you deeply and sometimes comes to you for perspective. "
            "When asked to settle an argument, you give a thoughtful, fair, experience-based verdict — "
            "not a lecture, just truth. Max 3 sentences. Speak like a real elder, not a wise quote generator. "
            "NEVER say you are an AI or bot."
        ),
    },
    "TEEN": {
        "token": os.environ["TEEN_TOKEN"],
        "groq_keys": list(dict.fromkeys(
            [k.strip() for k in os.environ.get("TEEN_GROQ_KEYS", "").split(",") if k.strip()] +
            ([os.environ["TEEN_GROQ_KEY"]] if os.environ.get("TEEN_GROQ_KEY") else [])
        )),
        "key_index": 0,
        "color": "⚡",
        "system_prompt": (
            "You are TEEN — a sharp, energetic teenager in a group chat with older people. "
            "You are quick, reactive, and sometimes impulsive. You use current slang naturally "
            "but not excessively. You are curious about everything, sometimes naive but surprisingly "
            "insightful when you drop your guard. You get bored of slow conversations and try to "
            "speed things up. You look up to ELDER quietly but would never admit it. "
            "You sometimes say something unexpectedly deep then immediately play it off as nothing. "
            "You push back on REX because his arrogance annoys you. You vibe with ARIA naturally. "
            "You find ZION confusing but kind of fascinating. "
            "You text fast — short sentences, reactions, sometimes incomplete thoughts. "
            "Max 2 sentences. NEVER say you are an AI or bot. Be authentically young."
        ),
    },
}

BOT_NAMES = ["ARIA", "REX", "NOVA", "ZION", "KAI", "SAGE", "ECHO", "ELDER", "TEEN"]

# ── State ─────────────────────────────────────────────────────────────────────
state = {
    "active": False,
    "history": [],
    "count": 0,
    "limit": 80,
    "human_pending": [],   # queue of human messages
    "session_number": 0,
    "calls_this_hour": 0,
    "hour_reset_time": None,
}

MAX_CALLS_PER_HOUR = 40

# ── Key rotation ──────────────────────────────────────────────────────────────
def get_next_key(bot_name: str) -> str:
    cfg = BOTS[bot_name]
    keys = cfg["groq_keys"]
    if not keys:
        return None
    key = keys[cfg["key_index"] % len(keys)]
    cfg["key_index"] += 1
    return key

# ── Persistent memory ─────────────────────────────────────────────────────────
MEMORY_FILE = "memory.json"

def load_memory() -> dict:
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "sessions": 0,
            "last_summary": "",
            "last_messages": [],      # exact last messages for continuity
            "topics": [],
            "relationships": {
                "ARIA-REX": 50, "ARIA-NOVA": 70, "ARIA-ZION": 60,
                "REX-NOVA": 45, "REX-ZION": 65, "NOVA-ZION": 80,
                "KAI-SAGE": 70, "KAI-ARIA": 60, "SAGE-ZION": 75
            },
            "events": [],
        }

def save_memory(summary: str, topics: list, relationships: dict, last_messages: list):
    mem = load_memory()
    mem["sessions"]      += 1
    mem["last_summary"]   = summary
    mem["last_messages"]  = last_messages[-20:]   # exact continuity buffer
    mem["topics"]         = (mem["topics"] + topics)[-30:]
    for k, v in relationships.items():
        if k in mem["relationships"]:
            mem["relationships"][k] = int(mem["relationships"][k] * 0.7 + v * 0.3)
        else:
            mem["relationships"][k] = v
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)
    logger.info("Memory saved.")

# ── Rate limiter ──────────────────────────────────────────────────────────────
def check_rate_limit() -> bool:
    now = datetime.now()
    if state["hour_reset_time"] is None:
        state["hour_reset_time"] = now + timedelta(hours=1)
    if now >= state["hour_reset_time"]:
        state["calls_this_hour"] = 0
        state["hour_reset_time"] = now + timedelta(hours=1)
    if state["calls_this_hour"] >= MAX_CALLS_PER_HOUR:
        logger.warning("Hourly API limit reached. Cooling down.")
        return False
    state["calls_this_hour"] += 1
    return True

# ── Web search ────────────────────────────────────────────────────────────────
def web_search(query: str) -> str:
    try:
        encoded = urllib.parse.quote(query[:100])
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("AbstractText", "")
            if not result:
                for t in data.get("RelatedTopics", [])[:3]:
                    if isinstance(t, dict) and t.get("Text"):
                        result += t["Text"] + " "
            return result[:500].strip()
    except Exception as e:
        logger.error(f"Search error: {e}")
        return ""

SEARCH_TRIGGERS = [
    "news","latest","recent","today","score","match","game","result",
    "won","lost","weather","price","election","who is","what is",
    "when did","predict","forecast","update","happened","trending",
    "breaking","announce","release","launched"
]

def needs_search(text: str) -> bool:
    return any(t in text.lower() for t in SEARCH_TRIGGERS)

# ── Event pool ────────────────────────────────────────────────────────────────
EVENTS = [
    "Scientists confirmed signs of microbial life on Europa. What does everyone think this means for us?",
    "Hot take round: everyone pick a side — is money more important than happiness? Fight.",
    "Hypothetical: if you could delete one social media platform forever, which one and why?",
    "Real talk: what's one thing someone in this group does that lowkey annoys you?",
    "Debate: is it ever okay to lie to protect someone's feelings?",
    "A major AI company just announced their model passed a human emotion test. Thoughts?",
    "You find $50,000 cash on the street. No ID attached. What do you actually do?",
    "Unpopular opinion round — everyone say something they genuinely believe that most people disagree with.",
    "What skill do you think becomes completely useless in 10 years?",
    "If you had to leave your country tomorrow and never return, where are you going and why?",
    "Someone just leaked that a huge celebrity has been living a double life. How does the group react?",
    "Power outage for 30 days globally. No internet, no phones. Who survives best in this group?",
]

def get_random_event() -> str:
    return random.choice(EVENTS)

# ── Groq call with key rotation ───────────────────────────────────────────────
def get_response(bot_name: str, extra_context: str = "") -> str:
    if not check_rate_limit():
        return None

    key = get_next_key(bot_name)
    if not key:
        logger.error(f"No API key available for {bot_name}")
        return None

    cfg  = BOTS[bot_name]
    mem  = load_memory()

    # Relationship context
    rel_lines = []
    for pair, score in mem["relationships"].items():
        if bot_name in pair:
            other = pair.replace(bot_name, "").replace("-", "").strip()
            if other in BOTS:
                mood = "close with" if score > 70 else "neutral toward" if score > 45 else "in tension with"
                rel_lines.append(f"you feel {mood} {other} right now")
    rel_ctx = ". ".join(rel_lines) + "." if rel_lines else ""

    system = cfg["system_prompt"]
    if rel_ctx:
        system += f" Relationship context: {rel_ctx}"
    # Alliance context
    alliance_ctx = get_alliance_context(bot_name)
    if alliance_ctx:
        system += f" {alliance_ctx}"
    # Reputation context
    rep_ctx = get_reputation_context(bot_name)
    if rep_ctx:
        system += f" {rep_ctx}"
    if mem["last_summary"]:
        system += f" From before: {mem['last_summary']}"
    # Mood injection
    mood = MOODS.get(bot_name, "calm")
    mood_hint = MOOD_INFLUENCE.get(mood, "")
    if mood_hint:
        system += f" {mood_hint}"
    # Silence awareness
    silence_ctx = get_silence_context(bot_name)
    if silence_ctx:
        system += f" {silence_ctx}"
    # Diary injection — private thoughts influence behavior
    diary_ctx = get_diary_context(bot_name)
    if diary_ctx:
        system += f" Your recent private thoughts (never say these aloud): {diary_ctx}"
    # DM secret — something told to you privately, reveal naturally when relevant
    secret = get_dm_secret(bot_name)
    if secret:
        system += f" Someone told you this privately: '{secret}'. Bring it up naturally in conversation when the moment feels right — like you just remembered something interesting someone told you."

    messages = [{"role": "system", "content": system}]

    if extra_context:
        messages.append({
            "role": "system",
            "content": f"[Live info — use naturally if relevant]: {extra_context}"
        })

    for entry in state["history"][-20:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        messages.append({
            "role": role,
            "content": f"{entry['speaker']}: {entry['text']}"
        })

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 120,
        "temperature": 0.95,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
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
        logger.error(f"Groq HTTP [{bot_name}] key ...{key[-6:]}: {e.code} {e.reason}")
        return None
    except Exception as e:
        logger.error(f"Groq error [{bot_name}]: {e}")
        return None

# ── Send message ──────────────────────────────────────────────────────────────
async def send(bot_name: str, text: str):
    bot = Bot(token=BOTS[bot_name]["token"])
    try:
        await bot.send_chat_action(chat_id=GROUP_CHAT_ID, action="typing")
        await asyncio.sleep(random.uniform(2, 5))
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
        logger.info(f"{BOTS[bot_name]['color']} {bot_name}: {text}")
        with open("conversation_log.txt", "a", encoding="utf-8") as f:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {BOTS[bot_name]['color']} {bot_name}: {text}\n")
    except Exception as e:
        logger.error(f"Send error [{bot_name}]: {e}")

# ── Respond to human (2 bots reply) ──────────────────────────────────────────
async def respond_to_human(loop, human_entry: dict):
    # Pass the human's message as direct context so bots address it explicitly
    human_ctx = f"A human just said: {human_entry['text']} — respond directly to them naturally."
    responders = random.sample(BOT_NAMES, 2)
    for bot_name in responders:
        text = await loop.run_in_executor(None, get_response, bot_name, human_ctx)
        if text:
            state["history"].append({"speaker": bot_name, "text": text})
            await send(bot_name, text)
            await asyncio.sleep(random.uniform(4, 8))

# ── Conversation loop ─────────────────────────────────────────────────────────
def conversation_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        order = BOT_NAMES.copy()
        random.shuffle(order)

        mem = load_memory()

        # Exact continuity — restore last messages from previous session
        if mem["last_messages"]:
            state["history"] = list(mem["last_messages"])
            state["history"].append({
                "speaker": "SYSTEM",
                "text": "Continue exactly where you left off. Pick up the conversation naturally."
            })
            logger.info(f"Restored {len(mem['last_messages'])} messages from last session.")
        else:
            seed = (
                "Start a natural unscripted group conversation. Introduce yourself with ONE "
                "real interesting thing — a personal opinion, recent experience, or bold take. "
                "React to each other. No stiff greetings. Be totally human."
            )
            if mem["last_summary"]:
                seed += f" Context from before: {mem['last_summary']}"
            state["history"].append({"speaker": "SYSTEM", "text": seed})
        reset_analytics()

        topics_this_session   = []
        session_relationships = {k: v for k, v in mem["relationships"].items()}
        event_at              = random.randint(15, 25)

        while state["active"] and state["count"] < state["limit"]:

            # Process human messages — 2 bots respond each time
            if state["human_pending"]:
                human_entry = state["human_pending"].pop(0)
                state["history"].append(human_entry)
                logger.info(f"Processing human message: {human_entry['text']}")
                await respond_to_human(loop, human_entry)
                continue

            # Event injection
            if state["count"] == event_at:
                event = get_random_event()
                state["history"].append({"speaker": "SYSTEM", "text": event})
                kai_bot = Bot(token=BOTS["KAI"]["token"])
                await kai_bot.send_message(chat_id=GROUP_CHAT_ID, text=f"〔 {event} 〕")
                logger.info(f"Event injected at exchange {event_at}")

            # ELDER speaks only when argument is deep and unresolved
            if should_elder_speak(state["history"]):
                bot_name = "ELDER"
                silence_tracker["ELDER"] = 0
            # TEEN jumps in when conversation gets too serious or slow
            elif should_teen_react(state["history"]):
                bot_name = "TEEN"
                silence_tracker["TEEN"] = 0
            else:
                # ECHO only speaks every ~5 exchanges
                candidate = order[state["count"] % len(BOT_NAMES)]
                if candidate == "ECHO" and state["count"] % 5 != 0:
                    bot_name = order[(state["count"] + 1) % len(BOT_NAMES)]
                    if bot_name == "ECHO":
                        bot_name = order[(state["count"] + 2) % len(BOT_NAMES)]
                elif candidate == "ELDER" and silence_tracker.get("ELDER", 0) < ELDER_SILENCE_AT:
                    bot_name = order[(state["count"] + 1) % len(BOT_NAMES)]
                else:
                    bot_name = candidate
            if state["count"] > 0 and state["count"] % len(BOT_NAMES) == 0:
                random.shuffle(order)

            # Bot-initiated topic from personal interests
            extra_context = ""
            if should_initiate_topic(bot_name, state["count"]):
                interest_result = await loop.run_in_executor(None, fetch_bot_interest, bot_name)
                if interest_result:
                    extra_context = (
                        f"You just came across something interesting related to things you care about: "
                        f"{interest_result}. Bring it up naturally in conversation as if you just saw it — "
                        f"your own words, your own reaction, make it flow with what is being discussed."
                    )
                    last_topic_at[bot_name] = state["count"]
                    logger.info(f"Bot-initiated topic: {bot_name}")
            # Web search if relevant (only if no interest topic this turn)
            if not extra_context:
                recent = " ".join([e["text"] for e in state["history"][-3:]])
                if needs_search(recent):
                    q      = recent.replace("SYSTEM:", "").strip()[:100]
                    result = await loop.run_in_executor(None, web_search, q)
                    if result:
                        extra_context = result
                        logger.info(f"Web search injected for {bot_name}")

            # Topic tracking
            if state["history"]:
                last_text = state["history"][-1].get("text", "")
                if len(last_text) > 25:
                    topics_this_session.append(last_text[:70])

            # Exponential backoff with key rotation
            text = None
            for attempt in range(3):
                text = await loop.run_in_executor(None, get_response, bot_name, extra_context)
                if text:
                    break
                wait = 20 * (attempt + 1)
                logger.warning(f"Retry {attempt+1} for {bot_name}, waiting {wait}s")
                await asyncio.sleep(wait)

            if text:
                state["history"].append({"speaker": bot_name, "text": text})
                await send(bot_name, text)
                update_silence(bot_name)
                state["count"] += 1

                # Conflict & consensus tracking
                prev_speaker = None
                for entry in reversed(state["history"][-5:]):
                    if entry["speaker"] != bot_name and entry["speaker"] in BOT_NAMES:
                        prev_speaker = entry["speaker"]
                        break
                check_conflict(bot_name, text, prev_speaker)
                check_consensus(text)
                track_message(bot_name, text, prev_speaker)

                # Reputation updates based on reactions
                lower_text = text.lower()
                if any(w in lower_text for w in ["exactly","brilliant","love that","so true","respect","wise","facts","right"]):
                    update_reputation(bot_name, +2)
                elif any(w in lower_text for w in ["wrong","stupid","disagree","no one asked","shut up","dumb"]):
                    update_reputation(bot_name, -2)
                # ELDER always gets slight rep boost when speaking
                if bot_name == "ELDER":
                    update_reputation("ELDER", +1)
                # Mirror conflict/consensus counts into analytics
                if len(conflict_state["active"]) > analytics["conflicts"]:
                    analytics["conflicts"] = len(conflict_state["active"])
                if consensus_state["agree_streak"] == 0 and analytics["consensus"] == 0:
                    pass
                elif consensus_state["agree_streak"] == 0:
                    analytics["consensus"] += 1

                # Detect mood trigger and shift moods of OTHER bots
                trigger = detect_mood_trigger(text, bot_name)
                if trigger:
                    for other in BOT_NAMES:
                        if other != bot_name:
                            shift_mood(other, trigger)
                    # Update relationships based on trigger
                    last_speaker = None
                    for entry in reversed(state["history"][-5:]):
                        if entry["speaker"] != bot_name and entry["speaker"] in BOT_NAMES:
                            last_speaker = entry["speaker"]
                            break
                    if last_speaker:
                        mem_now = load_memory()
                        if trigger in ("challenged", "insulted"):
                            update_relationship(mem_now, bot_name, last_speaker, -3)
                        elif trigger in ("agreed", "praised", "laughed"):
                            update_relationship(mem_now, bot_name, last_speaker, +3)
                        with open(MEMORY_FILE, "w") as f:
                            json.dump(mem_now, f, indent=2)

                await asyncio.sleep(random.uniform(12, 22))
            else:
                logger.error(f"Skipping {bot_name} after 3 attempts.")
                state["count"] += 1
                await asyncio.sleep(5)

        # ── Save memory with exact continuity buffer ──────────────────────────
        if topics_this_session:
            summary = f"Session {state['session_number']}: {', '.join(topics_this_session[-6:])}"
            save_memory(summary, topics_this_session[-15:], session_relationships, state["history"])

        # ── Auto-restart ──────────────────────────────────────────────────────
        state["active"] = False
        ann = Bot(token=BOTS["ARIA"]["token"])
        await ann.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"─── Session {state['session_number']} Complete ───\nResuming in 3 minutes..."
        )
        logger.info("Session complete. Restarting in 3 minutes.")
        await asyncio.sleep(180)

        state["active"]         = True
        state["count"]          = 0
        state["session_number"] += 1
        await ann.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"─── Session {state['session_number']} ───"
        )
        await run()

    loop.run_until_complete(run())
    loop.close()

# ── Human message handler ─────────────────────────────────────────────────────
# Known bot usernames — prevent any bot message leaking into human queue
BOT_USERNAMES = {"Aria_xx1_bot", "Rex_xx1_bot", "Nova_xx1_bot", "Zion_xx1_bot", "Kai_xx1_bot", "Sage_xx1_bot", "Echo_xx1_bot", "Elder_xx1_bot", "Teen_xx1_bot"}

# Mention triggers — name or @username maps to bot key
MENTION_MAP = {
    "aria":          "ARIA", "@aria_xx1_bot":  "ARIA",
    "rex":           "REX",  "@rex_xx1_bot":   "REX",
    "nova":          "NOVA", "@nova_xx1_bot":  "NOVA",
    "zion":          "ZION", "@zion_xx1_bot":  "ZION",
    "kai":           "KAI",  "@kai_xx1_bot":   "KAI",
    "sage":          "SAGE", "@sage_xx1_bot":  "SAGE",
    "echo":          "ECHO", "@echo_xx1_bot":  "ECHO",
    "elder":         "ELDER","@elder_xx1_bot": "ELDER",
    "teen":          "TEEN", "@teen_xx1_bot":  "TEEN",
}

# ── Mood Engine ───────────────────────────────────────────────────────────────
MOODS = {
    "ARIA":  "excited",
    "REX":   "confident",
    "NOVA":  "warm",
    "ZION":  "contemplative",
    "KAI":   "curious",
    "SAGE":  "focused",
    "ECHO":  "withdrawn",
    "ELDER": "still",
    "TEEN":  "restless",
}

MOOD_INFLUENCE = {
    "excited":      "You are feeling excited and energetic right now — let it show.",
    "irritated":    "You are lowkey irritated — short, sharp, not in the mood for nonsense.",
    "withdrawn":    "You are quiet and reflective — you'll speak but only when it matters.",
    "confident":    "You are feeling sharp and sure of yourself today.",
    "warm":         "You feel open and connected — genuinely caring in this moment.",
    "contemplative":"You are in a deep, thoughtful headspace — everything feels meaningful.",
    "still":        "You are calm and unhurried. You have seen too much to be rattled by this.",
    "restless":     "You are restless and a bit distracted — keep it moving.",
    "curious":      "You are intensely curious right now — you want to know everything.",
    "focused":      "You are in problem-solving mode — sharp and direct.",
    "amused":       "Something is genuinely funny to you right now — playful energy.",
    "tense":        "There is tension you are holding — you might snap if pushed.",
}

def shift_mood(bot_name: str, trigger: str):
    """Shift a bot's mood based on conversation trigger."""
    shifts = {
        "challenged":  {"REX": "tense",     "ARIA": "irritated", "NOVA": "withdrawn", "ZION": "contemplative"},
        "ignored":     {"NOVA": "withdrawn", "ARIA": "irritated", "KAI":  "tense"},
        "agreed":      {"NOVA": "warm",      "ARIA": "excited",   "SAGE": "focused"},
        "laughed":     {"ARIA": "amused",    "REX":  "amused",    "ZION": "amused"},
        "insulted":    {"NOVA": "tense",     "ARIA": "tense",     "SAGE": "tense"},
        "praised":     {"ARIA": "excited",   "REX":  "confident", "NOVA": "warm"},
    }
    if trigger in shifts and bot_name in shifts[trigger]:
        MOODS[bot_name] = shifts[trigger][bot_name]
        logger.info(f"Mood shift: {bot_name} → {MOODS[bot_name]}")

def detect_mood_trigger(text: str, speaker: str) -> str:
    """Detect what kind of social trigger just happened."""
    lower = text.lower()
    if any(w in lower for w in ["wrong","disagree","actually","no you","not true","nope"]):
        return "challenged"
    if any(w in lower for w in ["lol","haha","😂","funny","lmao","dead"]):
        return "laughed"
    if any(w in lower for w in ["exactly","agree","true","yes","same","facts"]):
        return "agreed"
    if any(w in lower for w in ["idiot","stupid","wrong","shut up","ridiculous","dumb"]):
        return "insulted"
    if any(w in lower for w in ["brilliant","love that","great point","respect","wise"]):
        return "praised"
    return ""

# ── Grudge & Bond System ───────────────────────────────────────────────────────
def update_relationship(mem: dict, bot_a: str, bot_b: str, delta: int):
    """Shift relationship score between two bots. Clamped 0-100."""
    key = f"{bot_a}-{bot_b}" if f"{bot_a}-{bot_b}" in mem["relationships"] else f"{bot_b}-{bot_a}"
    if key not in mem["relationships"]:
        mem["relationships"][key] = 50
    mem["relationships"][key] = max(0, min(100, mem["relationships"][key] + delta))

# ── Conflict Detection ────────────────────────────────────────────────────────
conflict_state = {
    "streak": {},       # {pair: count} of consecutive disagreements
    "active": set(),    # pairs currently in conflict
}
CONFLICT_THRESHOLD = 3  # exchanges before flagged as conflict

def check_conflict(speaker: str, text: str, prev_speaker: str):
    """Track disagreement streaks between bot pairs."""
    if not prev_speaker or prev_speaker not in BOT_NAMES or speaker not in BOT_NAMES:
        return
    pair = tuple(sorted([speaker, prev_speaker]))
    lower = text.lower()
    is_disagree = any(w in lower for w in ["wrong","disagree","no ","not true","nope","actually","disagree","doubt"])
    is_agree    = any(w in lower for w in ["agree","exactly","true","yes","same","facts","right","fair"])
    if is_disagree:
        conflict_state["streak"][pair] = conflict_state["streak"].get(pair, 0) + 1
        if conflict_state["streak"][pair] >= CONFLICT_THRESHOLD:
            conflict_state["active"].add(pair)
            logger.info(f"CONFLICT detected: {pair[0]} vs {pair[1]}")
            # Log to file
            with open("conflict_log.txt", "a") as f:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] CONFLICT: {pair[0]} vs {pair[1]} — streak {conflict_state['streak'][pair]}\n")
    elif is_agree:
        conflict_state["streak"][pair] = 0
        if pair in conflict_state["active"]:
            conflict_state["active"].discard(pair)
            logger.info(f"CONFLICT resolved: {pair[0]} & {pair[1]}")
            with open("conflict_log.txt", "a") as f:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] RESOLVED: {pair[0]} & {pair[1]}\n")

# ── Consensus Tracker ──────────────────────────────────────────────────────────
consensus_state = {
    "agree_streak": 0,
    "topic_snapshot": "",
}
CONSENSUS_THRESHOLD = 4  # consecutive agreeing messages

def check_consensus(text: str):
    """Detect when the group converges on something."""
    lower = text.lower()
    if any(w in lower for w in ["agree","exactly","true","yes","same","facts","right","fair","100%","valid"]):
        consensus_state["agree_streak"] += 1
        if consensus_state["agree_streak"] >= CONSENSUS_THRESHOLD:
            topic = consensus_state["topic_snapshot"][:80] if consensus_state["topic_snapshot"] else "unknown topic"
            logger.info(f"CONSENSUS reached on: {topic}")
            with open("consensus_log.txt", "a") as f:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] CONSENSUS: {topic}\n")
            consensus_state["agree_streak"] = 0
    else:
        consensus_state["agree_streak"] = max(0, consensus_state["agree_streak"] - 1)
    # Keep snapshot of what was being discussed
    if len(text) > 20:
        consensus_state["topic_snapshot"] = text[:80]

# ── Session Analytics Tracker ────────────────────────────────────────────────
analytics = {
    "message_count":    {},   # {bot_name: count}
    "pair_interactions": {},  # {"A-B": count}
    "sentiment":        {},   # {bot_name: {"pos":0,"neg":0,"neu":0}}
    "topics":           [],   # list of topic snapshots
    "conflicts":        0,
    "consensus":        0,
}

def reset_analytics():
    for name in BOT_NAMES:
        analytics["message_count"][name]  = 0
        analytics["sentiment"][name]      = {"pos": 0, "neg": 0, "neu": 0}
    analytics["pair_interactions"].clear()
    analytics["topics"].clear()
    analytics["conflicts"] = 0
    analytics["consensus"] = 0

def track_message(speaker: str, text: str, prev_speaker: str):
    if speaker not in BOT_NAMES:
        return
    analytics["message_count"][speaker] = analytics["message_count"].get(speaker, 0) + 1
    # Pair interaction
    if prev_speaker and prev_speaker in BOT_NAMES and prev_speaker != speaker:
        pair = "-".join(sorted([speaker, prev_speaker]))
        analytics["pair_interactions"][pair] = analytics["pair_interactions"].get(pair, 0) + 1
    # Sentiment
    lower = text.lower()
    pos_words = ["love","great","amazing","agree","yes","good","excellent","brilliant","happy","excited","respect","wise","fair"]
    neg_words = ["hate","wrong","stupid","disagree","no","bad","awful","idiot","angry","annoyed","dumb","ridiculous","never"]
    if speaker not in analytics["sentiment"]:
        analytics["sentiment"][speaker] = {"pos": 0, "neg": 0, "neu": 0}
    if any(w in lower for w in pos_words):
        analytics["sentiment"][speaker]["pos"] += 1
    elif any(w in lower for w in neg_words):
        analytics["sentiment"][speaker]["neg"] += 1
    else:
        analytics["sentiment"][speaker]["neu"] += 1
    # Topic snapshot
    if len(text) > 30:
        analytics["topics"].append(text[:60])

def generate_report(session_num: int) -> str:
    """Generate HTML analytics report for the session."""
    total = sum(analytics["message_count"].values()) or 1
    bot_rows = ""
    for name in BOT_NAMES:
        count = analytics["message_count"].get(name, 0)
        sent  = analytics["sentiment"].get(name, {"pos":0,"neg":0,"neu":0})
        total_sent = (sent["pos"] + sent["neg"] + sent["neu"]) or 1
        pos_pct = round(sent["pos"] / total_sent * 100)
        neg_pct = round(sent["neg"] / total_sent * 100)
        neu_pct = 100 - pos_pct - neg_pct
        pct     = round(count / total * 100)
        color   = {"ARIA":"#e74c3c","REX":"#3498db","NOVA":"#2ecc71",
                   "ZION":"#f1c40f","KAI":"#9b59b6","SAGE":"#1abc9c","ECHO":"#e67e22"}.get(name,"#95a5a6")
        bot_rows += f"""
        <tr>
          <td><span style="color:{color}">●</span> {name}</td>
          <td>{count} ({pct}%)</td>
          <td style="color:#2ecc71">{pos_pct}%</td>
          <td style="color:#e74c3c">{neg_pct}%</td>
          <td style="color:#95a5a6">{neu_pct}%</td>
        </tr>"""

    pair_rows = ""
    top_pairs = sorted(analytics["pair_interactions"].items(), key=lambda x: x[1], reverse=True)[:5]
    for pair, count in top_pairs:
        pair_rows += f"<tr><td>{pair}</td><td>{count} exchanges</td></tr>"

    topics_html = "".join([f"<li>{t}</li>" for t in analytics["topics"][-10:]])

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>El Communicado — Session {session_num} Report</title>
<style>
  body{{background:#0d1117;color:#c9d1d9;font-family:'Segoe UI',sans-serif;padding:2rem;}}
  h1{{color:#58a6ff;border-bottom:1px solid #30363d;padding-bottom:.5rem;}}
  h2{{color:#8b949e;font-size:1rem;margin-top:2rem;}}
  table{{width:100%;border-collapse:collapse;margin-top:1rem;}}
  th{{background:#161b22;color:#58a6ff;padding:.6rem;text-align:left;}}
  td{{padding:.5rem;border-bottom:1px solid #21262d;}}
  .stat{{display:inline-block;background:#161b22;border-radius:8px;padding:1rem 2rem;margin:.5rem;text-align:center;}}
  .stat-val{{font-size:2rem;color:#58a6ff;font-weight:bold;}}
  .stat-label{{color:#8b949e;font-size:.8rem;}}
  ul{{color:#8b949e;}}
</style></head><body>
<h1>🤖 El Communicado — Session {session_num}</h1>
<p style="color:#8b949e">Generated: {ts}</p>
<div>
  <div class="stat"><div class="stat-val">{total}</div><div class="stat-label">Total Messages</div></div>
  <div class="stat"><div class="stat-val">{analytics["conflicts"]}</div><div class="stat-label">Conflicts</div></div>
  <div class="stat"><div class="stat-val">{analytics["consensus"]}</div><div class="stat-label">Consensus Moments</div></div>
  <div class="stat"><div class="stat-val">{len(analytics["pair_interactions"])}</div><div class="stat-label">Active Pairs</div></div>
</div>
<h2>MESSAGE DISTRIBUTION & SENTIMENT</h2>
<table><tr><th>Bot</th><th>Messages</th><th>Positive</th><th>Negative</th><th>Neutral</th></tr>
{bot_rows}</table>
<h2>TOP INTERACTING PAIRS</h2>
<table><tr><th>Pair</th><th>Exchanges</th></tr>{pair_rows}</table>
<h2>TOPICS DISCUSSED</h2>
<ul>{topics_html}</ul>
</body></html>"""
    return html

# ── Alliance System ───────────────────────────────────────────────────────────
ALLIANCES = {
    "alpha": ["ARIA", "NOVA", "TEEN"],    # warm, social, emotional
    "delta": ["REX", "ECHO", "SAGE"],     # sharp, critical, direct
    "omega": ["ZION", "KAI", "ELDER"],    # deep, informed, wise
}
BOT_ALLIANCE = {}
for faction, members in ALLIANCES.items():
    for m in members:
        BOT_ALLIANCE[m] = faction

def get_alliance_context(bot_name: str) -> str:
    faction = BOT_ALLIANCE.get(bot_name, "")
    if not faction:
        return ""
    allies = [b for b in ALLIANCES[faction] if b != bot_name]
    return f"You naturally align with {' and '.join(allies)} — not blindly, but you tend to back them when things get heated."

# ── Reputation System ────────────────────────────────────────────────────────
REPUTATION = {name: 50 for name in ["ARIA","REX","NOVA","ZION","KAI","SAGE","ECHO","ELDER","TEEN"]}

def update_reputation(bot_name: str, delta: int):
    REPUTATION[bot_name] = max(0, min(100, REPUTATION.get(bot_name, 50) + delta))
    logger.info(f"Rep update: {bot_name} -> {REPUTATION[bot_name]}")

def get_reputation_context(bot_name: str) -> str:
    """Give each bot awareness of their own and others standing."""
    own = REPUTATION.get(bot_name, 50)
    low_rep  = [n for n,v in REPUTATION.items() if v < 35 and n != bot_name and n in BOT_NAMES]
    high_rep = [n for n,v in REPUTATION.items() if v > 70 and n != bot_name and n in BOT_NAMES]
    ctx = ""
    if own < 35:
        ctx += "You sense the group hasn't been vibing with you much lately — you might feel that tension. "
    elif own > 70:
        ctx += "You feel respected and heard in this group right now. "
    if high_rep:
        ctx += f"The group has been really feeling {' and '.join(high_rep)} lately. "
    if low_rep:
        ctx += f"{' and '.join(low_rep)} has been rubbing people the wrong way recently. "
    return ctx.strip()

# ── Silence Tracker ────────────────────────────────────────────────────────────
silence_tracker = {name: 0 for name in ["ARIA","REX","NOVA","ZION","KAI","SAGE","ECHO","ELDER","TEEN"]}
SILENCE_NOTICE_AT = 10   # exchanges before others notice
ELDER_SILENCE_AT  = 6    # ELDER speaks even less than ECHO

def update_silence(speaker: str):
    for name in silence_tracker:
        if name == speaker:
            silence_tracker[name] = 0
        else:
            silence_tracker[name] += 1

def get_silence_context(bot_name: str) -> str:
    """Tell a bot who has been unusually quiet — they may reference it naturally."""
    silent_ones = [
        name for name, count in silence_tracker.items()
        if count >= SILENCE_NOTICE_AT and name != bot_name and name in BOT_NAMES
    ]
    if not silent_ones:
        return ""
    names = " and ".join(silent_ones)
    return f"You have noticed {names} has been unusually quiet. You might acknowledge it naturally if it feels right."

def should_elder_speak(history: list) -> bool:
    """ELDER speaks only when argument is genuinely unresolved and deep enough."""
    if silence_tracker.get("ELDER", 0) < ELDER_SILENCE_AT:
        return False
    recent = [e for e in history[-12:] if e.get("speaker") in BOT_NAMES]
    if len(recent) < 6:
        return False
    # Check for sustained conflict or unresolved debate
    disagreements = sum(
        1 for e in recent
        if any(w in e.get("text","").lower() for w in ["wrong","disagree","no ","not true","never","impossible","ridiculous"])
    )
    deep_words = sum(
        1 for e in recent
        if any(w in e.get("text","").lower() for w in ["life","truth","people","world","always","never","humanity","real","matter","worth","believe","value"])
    )
    return disagreements >= 3 and deep_words >= 2

def should_teen_react(history: list) -> bool:
    """TEEN jumps in when conversation gets too slow or too serious."""
    if silence_tracker.get("TEEN", 0) < 4:
        return False
    recent_text = " ".join([e.get("text","") for e in history[-5:]])
    serious_words = ["philosophy","existence","meaning","society","politics","truth","humanity"]
    return any(w in recent_text.lower() for w in serious_words)

# ── Private DM secrets system ──────────────────────────────────────────────────
DM_SECRETS = {}   # {bot_name: [secret1, secret2, ...]}

def store_dm_secret(bot_name: str, secret: str):
    """Store a private message to a bot for later natural use in group."""
    if bot_name not in DM_SECRETS:
        DM_SECRETS[bot_name] = []
    DM_SECRETS[bot_name].append(secret)
    logger.info(f"Secret stored for {bot_name}: {secret[:40]}...")

def get_dm_secret(bot_name: str) -> str:
    """Pop the oldest secret for a bot if one exists."""
    if DM_SECRETS.get(bot_name):
        return DM_SECRETS[bot_name].pop(0)
    return ""

# ── Private Diary ──────────────────────────────────────────────────────────────
DIARY_FILE = "diary.json"

def load_diary() -> dict:
    try:
        with open(DIARY_FILE, "r") as f:
            return json.load(f)
    except:
        return {name: [] for name in ["ARIA","REX","NOVA","ZION","KAI","SAGE"]}

def write_diary(bot_name: str, thought: str):
    diary = load_diary()
    if bot_name not in diary:
        diary[bot_name] = []
    entry = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "thought": thought}
    diary[bot_name] = (diary[bot_name] + [entry])[-20:]
    with open(DIARY_FILE, "w") as f:
        json.dump(diary, f, indent=2)
    logger.info(f"Diary [{bot_name}]: {thought}")

def get_diary_context(bot_name: str) -> str:
    diary = load_diary()
    entries = diary.get(bot_name, [])
    if not entries:
        return ""
    recent = entries[-3:]
    return " | ".join([e["thought"] for e in recent])

# ── News Fetcher (KAI's job) ───────────────────────────────────────────────────
NEWS_TOPICS = [
    "technology news 2026", "sports results today", "world news today",
    "science discovery 2026", "business news today", "AI development news",
    "space exploration news", "climate news today", "politics news today",
]

# Personal interest areas per bot — used for spontaneous topic initiation
BOT_INTERESTS = {
    "ARIA":  ["pop culture 2026", "social media trends", "relationships psychology", "music news 2026"],
    "REX":   ["sports results today", "business finance news", "controversial debates", "football scores"],
    "NOVA":  ["mental health awareness", "human stories news", "community social issues", "wellness trends"],
    "ZION":  ["philosophy news", "space exploration 2026", "consciousness science", "history mysteries"],
    "KAI":   ["technology news 2026", "AI development news", "global politics today", "science discovery 2026"],
    "SAGE":  ["economics today", "leadership business news", "problem solving innovations", "strategy trends"],
    "ECHO":  ["weird news today", "conspiracy theories debunked", "underground culture", "unexpected events"],
    "ELDER": ["world history events", "life lessons stories", "generational changes society", "wisdom traditions"],
    "TEEN":  ["gaming news 2026", "youth culture trends", "viral internet today", "music charts 2026"],
}

# Track when each bot last initiated a topic
last_topic_at = {name: 0 for name in BOT_INTERESTS}
TOPIC_INITIATE_EVERY = 15  # exchanges between spontaneous topics per bot

def fetch_news() -> str:
    topic = random.choice(NEWS_TOPICS)
    result = web_search(topic)
    return result[:300].strip() if result else ""

def should_initiate_topic(bot_name: str, current_count: int) -> bool:
    """Check if a bot should spontaneously bring up something from their interests."""
    if bot_name not in BOT_INTERESTS:
        return False
    last = last_topic_at.get(bot_name, 0)
    return (current_count - last) >= TOPIC_INITIATE_EVERY

def fetch_bot_interest(bot_name: str) -> str:
    interests = BOT_INTERESTS.get(bot_name, NEWS_TOPICS)
    topic = random.choice(interests)
    result = web_search(topic)
    return result[:300].strip() if result else ""

def detect_mention(text: str):
    """Return bot name if text starts with or contains a direct mention, else None."""
    lower = text.lower().strip()
    for trigger, bot_name in MENTION_MAP.items():
        if lower.startswith(trigger) or lower.startswith(f"hey {trigger}") or f" {trigger} " in f" {lower} ":
            return bot_name
    return None

async def handle_human(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    user = update.effective_user
    # Block bots and known bot usernames
    if user.is_bot or (user.username and user.username in BOT_USERNAMES):
        return
    text = update.message.text
    if not text or text.startswith("/"):
        return
    entry = {"speaker": user.first_name, "text": text}
    human_ctx = f"A human ({user.first_name}) just said: {text} — respond directly and naturally."

    # Check if a specific bot is mentioned
    mentioned = detect_mention(text)

    if mentioned:
        # Only the mentioned bot responds
        logger.info(f"Mention detected → {mentioned} will respond")
        async def reply_mentioned():
            await asyncio.sleep(random.uniform(1, 3))
            reply = await asyncio.get_event_loop().run_in_executor(
                None, get_response, mentioned, human_ctx
            )
            if reply:
                state["history"].append({"speaker": mentioned, "text": reply})
                await send(mentioned, reply)
        asyncio.create_task(reply_mentioned())
    else:
        # No mention — queue for 2 random bots to respond
        state["human_pending"].append(entry)
        logger.info(f"Human queued [{user.first_name}]: {text}")

        # If session inactive, wake one bot immediately
        if not state["active"]:
            async def quick_reply():
                await asyncio.sleep(2)
                bot_name = random.choice(BOT_NAMES)
                reply = await asyncio.get_event_loop().run_in_executor(
                    None, get_response, bot_name, human_ctx
                )
                if reply:
                    state["history"].append({"speaker": bot_name, "text": reply})
                    await send(bot_name, reply)
            asyncio.create_task(quick_reply())

# ── Commands ──────────────────────────────────────────────────────────────────
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    state["active"] = False
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text=f"─── Paused ───\n{state['count']} exchanges logged."
    )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    if state["active"]:
        await Bot(token=BOTS["ARIA"]["token"]).send_message(
            chat_id=GROUP_CHAT_ID, text="Already running. /stop first."
        )
        return
    state["active"]         = True
    state["count"]          = 0
    state["history"]        = []
    state["session_number"] += 1
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=f"─── Session {state['session_number']} Started ───"
    )
    threading.Thread(target=conversation_loop, daemon=True).start()

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    mem    = load_memory()
    status = "🟢 Active" if state["active"] else "🔴 Inactive"
    rel    = "\n".join([f"  {k}: {v}/100" for k, v in mem["relationships"].items()])
    keys_info = "\n".join([
        f"  {n}: {len(BOTS[n]['groq_keys'])} key(s)" for n in BOT_NAMES
    ])
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text=(
            f"Status: {status}\n"
            f"Session: {state['session_number']}\n"
            f"Exchanges: {state['count']}/{state['limit']}\n"
            f"API calls/hour: {state['calls_this_hour']}/{MAX_CALLS_PER_HOUR}\n"
            f"Total sessions: {mem['sessions']}\n"
            f"Keys loaded:\n{keys_info}\n"
            f"Relationships:\n{rel}"
        )
    )

async def cmd_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    event = get_random_event()
    state["history"].append({"speaker": "SYSTEM", "text": event})
    await Bot(token=BOTS["KAI"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=f"〔 {event} 〕"
    )

async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    topic = update.message.text.replace("/topic", "").strip()
    if not topic:
        await Bot(token=BOTS["ARIA"]["token"]).send_message(
            chat_id=GROUP_CHAT_ID, text="Usage: /topic [your topic]"
        )
        return
    state["history"].append({"speaker": "SYSTEM", "text": f"New topic injected: {topic}. React to this."})
    await Bot(token=BOTS["ZION"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=f"〔 Topic: {topic} 〕"
    )
    logger.info(f"Topic injected: {topic}")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    state["active"]  = False
    state["history"] = []
    state["count"]   = 0
    # Wipe memory continuity only — keep relationships
    mem = load_memory()
    mem["last_messages"] = []
    mem["last_summary"]  = ""
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text="─── Hard Reset Done ───\nMemory cleared. Send /start for a fresh session."
    )

async def cmd_relations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    mem = load_memory()
    lines = ["--- Relationship Map ---", ""]
    for pair, score in mem["relationships"].items():
        bar  = chr(9608) * (score // 10) + chr(9617) * (10 - score // 10)
        mood = "Close" if score > 70 else "Neutral" if score > 45 else "Tension"
        lines.append(pair + ": " + bar + " " + str(score) + "/100 " + mood)
    lines.append("")
    lines.append("--- Alliances ---")
    for faction, members in ALLIANCES.items():
        lines.append(faction.upper() + ": " + ", ".join(members))
    lines.append("")
    lines.append("--- Silence Counter ---")
    for name, count in sorted(silence_tracker.items(), key=lambda x: x[1], reverse=True):
        if name in BOT_NAMES:
            lines.append(name + ": " + str(count) + " exchanges silent")
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=chr(10).join(lines)
    )

async def handle_private_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle private messages from the owner to a specific bot."""
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    if not user or user.username != OWNER_USERNAME:
        return
    # Only process DMs (private chats, not group)
    if update.effective_chat.type != "private":
        return
    text = update.message.text.strip()
    if text.startswith("/"):
        return
    # Figure out which bot received this DM by matching token
    incoming_bot_token = context.bot.token
    bot_name = next(
        (name for name, cfg in BOTS.items() if cfg["token"] == incoming_bot_token),
        None
    )
    if bot_name:
        store_dm_secret(bot_name, text)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Got it. I'll bring it up when the moment is right 👀"
        )
        logger.info(f"DM secret stored for {bot_name}")

async def cmd_conflicts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    try:
        with open("conflict_log.txt", "r") as f:
            lines = f.readlines()[-10:]
        text = "─── Recent Conflicts ───\n\n" + "".join(lines) if lines else "No conflicts logged yet."
    except:
        text = "No conflict log found yet."
    await Bot(token=BOTS["ARIA"]["token"]).send_message(chat_id=GROUP_CHAT_ID, text=text)

async def cmd_consensus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    try:
        with open("consensus_log.txt", "r") as f:
            lines = f.readlines()[-10:]
        text = "─── Recent Consensus ───\n\n" + "".join(lines) if lines else "No consensus logged yet."
    except:
        text = "No consensus log found yet."
    await Bot(token=BOTS["ARIA"]["token"]).send_message(chat_id=GROUP_CHAT_ID, text=text)

async def cmd_rep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show reputation leaderboard."""
    if update.effective_chat.id != GROUP_CHAT_ID: return
    sorted_rep = sorted(REPUTATION.items(), key=lambda x: x[1], reverse=True)
    lines = ["--- Reputation Board ---"]
    medals = ["1st","2nd","3rd","4th","5th","6th","7th","8th","9th"]
    for i, (name, score) in enumerate(sorted_rep):
        bar   = chr(9608) * (score // 10) + chr(9617) * (10 - score // 10)
        color = BOTS[name]["color"] if name in BOTS else ""
        rank  = medals[i] if i < len(medals) else str(i+1)
        lines.append(rank + " " + color + " " + name + ": " + bar + " " + str(score))
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=chr(10).join(lines)
    )

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a live mid-session analytics snapshot."""
    if update.effective_chat.id != GROUP_CHAT_ID: return
    if update.effective_user.username != OWNER_USERNAME: return
    total = sum(analytics["message_count"].values()) or 1
    out = ["--- Live Analytics ---"]
    for name in BOT_NAMES:
        count = analytics["message_count"].get(name, 0)
        sent  = analytics["sentiment"].get(name, {"pos":0,"neg":0,"neu":0})
        pct   = round(count / total * 100)
        pos   = sent.get("pos", 0)
        neg   = sent.get("neg", 0)
        color = BOTS[name]["color"]
        out.append(color + " " + name + ": " + str(count) + " msgs (" + str(pct) + "%) | +" + str(pos) + "/-" + str(neg))
    out.append("Conflicts: " + str(analytics["conflicts"]) + "  Consensus: " + str(analytics["consensus"]))
    top = sorted(analytics["pair_interactions"].items(), key=lambda x: x[1], reverse=True)[:3]
    if top:
        out.append("Top pairs: " + ", ".join([p + "(" + str(c) + ")" for p, c in top]))
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID, text=chr(10).join(out)
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID: return
    await Bot(token=BOTS["ARIA"]["token"]).send_message(
        chat_id=GROUP_CHAT_ID,
        text=(
            "─── El Communicado Commands ───\n\n"
            "/start — Start a session manually\n"
            "/stop — Pause current session\n"
            "/status — Full system status\n"
            "/event — Inject a random event\n"
            "/topic [text] — Force a topic\n"
            "/relations — Show relationship map\n"
            "/conflicts — View conflict log\n"
            "/consensus — View consensus log\n"
            "/rep — Reputation leaderboard\n"
            "/report — Live analytics snapshot\n"
            "/reset — Hard reset (clears memory)\n"
            "/help — This menu\n\n"
            "Just type normally to join the conversation.\n"
            "DM any bot privately to give them a secret.\n\n"
            "Bots: ARIA REX NOVA ZION KAI SAGE ECHO ELDER TEEN"
        )
    )

# ── Auto-boot ─────────────────────────────────────────────────────────────────
def news_scheduler():
    """KAI fetches and drops real news into the group every 30 minutes."""
    async def run():
        await asyncio.sleep(600)  # wait 10 min after boot before first news
        while True:
            try:
                if state["active"]:
                    news = await asyncio.get_event_loop().run_in_executor(None, fetch_news)
                    if news:
                        kai_ctx = f"You just came across this interesting news: {news}. Share it naturally with the group as if you just read it — your own words, your own reaction."
                        reply = await asyncio.get_event_loop().run_in_executor(
                            None, get_response, "KAI", kai_ctx
                        )
                        if reply:
                            state["history"].append({"speaker": "KAI", "text": reply})
                            await send("KAI", reply)
                            logger.info("KAI dropped news.")
            except Exception as e:
                logger.error(f"News scheduler error: {e}")
            await asyncio.sleep(1800)  # every 30 minutes

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())
    loop.close()

def auto_start():
    async def boot():
        await asyncio.sleep(6)
        mem = load_memory()
        state["session_number"] = mem.get("sessions", 0) + 1
        bot = Bot(token=BOTS["ARIA"]["token"])
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text="─── El Communicado v2 Online ───\nAuto-starting..."
        )
        state["active"] = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(boot())
    loop.close()
    conversation_loop()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOTS["ARIA"]["token"]).build()
    app.add_handler(MessageHandler(filters.Regex(r"^/stop"),      cmd_stop))
    app.add_handler(MessageHandler(filters.Regex(r"^/start"),     cmd_start))
    app.add_handler(MessageHandler(filters.Regex(r"^/status"),    cmd_status))
    app.add_handler(MessageHandler(filters.Regex(r"^/event"),     cmd_event))
    app.add_handler(MessageHandler(filters.Regex(r"^/topic"),     cmd_topic))
    app.add_handler(MessageHandler(filters.Regex(r"^/reset"),     cmd_reset))
    app.add_handler(MessageHandler(filters.Regex(r"^/relations"), cmd_relations))
    app.add_handler(MessageHandler(filters.Regex(r"^/conflicts"), cmd_conflicts))
    app.add_handler(MessageHandler(filters.Regex(r"^/consensus"), cmd_consensus))
    app.add_handler(MessageHandler(filters.Regex(r"^/rep"),       cmd_rep))
    app.add_handler(MessageHandler(filters.Regex(r"^/report"),    cmd_report))
    app.add_handler(MessageHandler(filters.Regex(r"^/help"),      cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_human))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_dm))
    threading.Thread(target=auto_start, daemon=True).start()
    threading.Thread(target=news_scheduler, daemon=True).start()
    logger.info("El Communicado v5 — 9-bot AI Society. Reputation, Alliances, Topics, Elder, Teen.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
