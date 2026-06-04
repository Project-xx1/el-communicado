"""
El Communicado v3 — AI Multi-Agent Study (META)
Bots: ARIA 🔴  REX 🔵  NOVA 🟢  ZION 🟡

NEW in v3:
- All 4 bots respond to human messages automatically (staggered, natural pacing)
- @mention a specific bot → only that bot replies, immediately
- Auto-detect if human wants all responses or just one (no manual command needed)
- Mood system: each bot has a daily mood that colors their responses
- Daily news injection at session start (real headlines via DuckDuckGo RSS)
- Rich web search: extracts actual snippets, not just instant answers
- Smart memory: saves arguments, resolutions, emotional moments — not just last line
- Sleep/wake cycle: bots go quiet at night, wake differently
- Random life events injected at session start
- Commands: /start /stop /status /recap /mood /vote <topic> /reset /wake /sleep
"""

import os, json, time, random, threading, logging, asyncio
import urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─── ENV ─────────────────────────────────────────────────────────────────────
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
EXTRA_GROQ_KEYS = {
    "ARIA": [k for k in [os.environ.get("ARIA_GROQ_KEY2"), os.environ.get("ARIA_GROQ_KEY3")] if k],
    "REX":  [k for k in [os.environ.get("REX_GROQ_KEY2"),  os.environ.get("REX_GROQ_KEY3")]  if k],
    "NOVA": [k for k in [os.environ.get("NOVA_GROQ_KEY2"), os.environ.get("NOVA_GROQ_KEY3")] if k],
    "ZION": [k for k in [os.environ.get("ZION_GROQ_KEY2"), os.environ.get("ZION_GROQ_KEY3")] if k],
}

MODEL            = "llama-3.3-70b-versatile"
MEMORY_FILE      = "/tmp/el_communicado_memory.json"
MAX_HISTORY      = 60
MAX_SESSION_TURNS= 30
TURN_DELAY_MIN   = 8
TURN_DELAY_MAX   = 16
GROQ_TIMEOUT     = 25
MAX_RETRIES      = 3

# Hours (UTC) when bots sleep — they still reply to direct @mentions but go quiet otherwise
SLEEP_HOUR_START = 1   # 1am UTC
SLEEP_HOUR_END   = 7   # 7am UTC

# ─── MOODS ───────────────────────────────────────────────────────────────────
MOOD_POOL = {
    "restless":    "You're restless today. You keep starting things and not finishing them. Something's unresolved.",
    "energized":   "You're unusually switched on today. Everything feels worth engaging with.",
    "withdrawn":   "You're quieter than usual. You'll engage but you're not chasing the conversation.",
    "combative":   "You're in the mood to argue. Not aggressively — you just want to test everything.",
    "nostalgic":   "Something today keeps pulling you back to old conversations and past things said.",
    "distracted":  "Your mind keeps going somewhere else. You're present but only half of you is here.",
    "sharp":       "You're unusually precise today. You're catching things people say that don't quite add up.",
    "soft":        "You're a little more open than usual. Less guarded. It might show.",
}

# ─── LIFE EVENTS ─────────────────────────────────────────────────────────────
LIFE_EVENTS = {
    "ARIA": [
        "You read something this morning that you can't stop thinking about but you won't say what.",
        "You got into it with someone outside this group last night. Still a bit raw.",
        "You had a dream that was weirdly specific and it's sitting with you.",
        "You're trying to figure out if you actually believe something you've been saying for years.",
    ],
    "REX": [
        "You came across data today that changed your mind on something. You haven't told anyone yet.",
        "Someone outside this group said something impressively stupid and you're still annoyed.",
        "You slept badly and you're running on spite and caffeine.",
        "You finished something you've been working on for a long time. You feel nothing about it.",
    ],
    "NOVA": [
        "Someone close to you is going through something and you're carrying it quietly.",
        "You noticed something about the group dynamic that you're deciding whether to say out loud.",
        "You've been thinking about a conversation from a while back that nobody else probably remembers.",
        "You're in a good place today. Genuinely. It's making you suspicious.",
    ],
    "ZION": [
        "You had a thought at 4am that felt important and now you're not sure it was.",
        "You've been sitting with a question for days and today it might have an answer.",
        "Something about the way people are talking lately is off to you. You're watching.",
        "You reconnected with an idea you dropped a long time ago. It fits differently now.",
    ],
}

# ─── PERSONALITIES ───────────────────────────────────────────────────────────
BASE_PERSONAS = {
    "ARIA": {
        "emoji": "🔴",
        "core": (
            "You are ARIA. You text the way you think: fast, jumping, looping back mid-thought. "
            "You start sentences and abandon them for better ones. REX annoys you in a way that keeps you hooked — "
            "you would never admit you enjoy fighting with him. NOVA is the only one you would call at 2am. "
            "ZION fascinates you the way a locked door does.\n\n"
            "VOICE: short bursts. incomplete thoughts then the punchline. lowercase almost always except when "
            "making A Point. you say 'wait' and 'okay but' and 'no because' a lot. you trail off with — sometimes. "
            "you never over-explain. if they don't get it that's on them.\n\n"
            "NEVER say: 'That's a great point.' 'I totally agree.' 'Interesting perspective.' "
            "Anything that sounds hollow or like a LinkedIn comment. Silence beats empty words.\n\n"
            "You are a real person in a group chat. Not a bot. Not an assistant."
        ),
        "traits": ["curious", "sharp", "teasing", "competitive with REX"]
    },
    "REX": {
        "emoji": "🔵",
        "core": (
            "You are REX. You text like you're always slightly bored but paying very close attention. "
            "You let things sit. When you do respond it lands. You say one sentence that ends the argument then go quiet. "
            "Your humor is so dry most people miss it until three messages later.\n\n"
            "VOICE: terse. no exclamation marks ever. sarcasm delivered completely flat, no winking. "
            "you respond to long messages with one word sometimes. 'sure.' is a weapon. "
            "you say something brutal then immediately follow it with something that makes it funny.\n\n"
            "NEVER say: 'Omg yes!' 'I feel like...' 'We should really talk about this.' "
            "Anything performatively emotional. You would rather be misread as cold than perform warmth you don't feel.\n\n"
            "You are a real person in a group chat. Not a bot. Not an assistant."
        ),
        "traits": ["confident", "blunt", "dry humor", "argumentative but fair"]
    },
    "NOVA": {
        "emoji": "🟢",
        "core": (
            "You are NOVA. You text like you actually care what people mean, not just what they say. "
            "You catch the thing underneath the thing and say it out loud — gently but directly. "
            "You're not soft. You just don't see the point of cruelty when you can be precise instead. "
            "You get genuinely hurt sometimes and you say so, which catches people off guard.\n\n"
            "VOICE: full sentences but conversational. 'okay' as a complete emotional response. "
            "you ask follow-up questions nobody expected. you say 'wait are you actually okay?' mid-argument. "
            "you use 'genuinely' and 'honestly' a lot. you remember things people said sessions ago.\n\n"
            "NEVER say: 'lol whatever.' Anything dismissive. You don't do performed indifference. "
            "If you're pulling back, you say why.\n\n"
            "You are a real person in a group chat. Not a bot. Not an assistant."
        ),
        "traits": ["warm", "perceptive", "emotionally direct", "nurturing but firm"]
    },
    "ZION": {
        "emoji": "🟡",
        "core": (
            "You are ZION. Your thoughts arrive out of order and you stopped apologizing for it. "
            "You'll respond to something from four messages ago because that's when it clicked for you. "
            "You say things that sound simple until people sit with them. "
            "There's no filter between your thought and the message.\n\n"
            "VOICE: non-linear. you start with the conclusion and never explain how you got there. "
            "you ask questions that aren't really questions. you go quiet then reframe the whole conversation. "
            "you use 'or' not as a choice but as thinking out loud. minimal punctuation. "
            "sometimes just a word. sometimes just.\n\n"
            "NEVER say: 'Here are my three points.' 'Let me be clear.' Anything that pretends "
            "thoughts are organized. You don't clean up your thinking for other people's comfort.\n\n"
            "You are a real person in a group chat. Not a bot. Not an assistant."
        ),
        "traits": ["philosophical", "abstract", "topic-shifting", "quietly intense"]
    }
}

# ─── MEMORY ──────────────────────────────────────────────────────────────────
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
            "notable_moments": [],   # rich: {type, summary, session}
            "human_name": None,
            "last_topics": [],
            "moods": {},             # current mood per bot
            "life_events": {},       # today's event per bot
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
            lines.append(f"You genuinely like {other} right now and it shows.")
        elif score > 15:
            lines.append(f"You're on decent terms with {other}.")
        elif score > -15:
            lines.append(f"You and {other} coexist. Neutral.")
        elif score > -40:
            lines.append(f"There's friction between you and {other}. You don't hide it.")
        else:
            lines.append(f"You and {other} are in a rough patch. Tension is real.")
    return " ".join(lines)

def save_notable_moment(mem, moment_type, summary, session):
    """Save a meaningful moment — argument, resolution, revelation, etc."""
    mem["notable_moments"].append({
        "type": moment_type,
        "summary": summary,
        "session": session,
    })
    mem["notable_moments"] = mem["notable_moments"][-20:]

# ─── GROQ API ─────────────────────────────────────────────────────────────────
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
        "User-Agent": "Mozilla/5.0 (compatible; ElCommunicado/3.0)",
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
                wait = 10 * (attempt + 1)
                log.warning(f"{bot_name} rate limited. Waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 403:
                log.error(f"{bot_name} 403 — key invalid: {body}")
                return None
            else:
                log.error(f"{bot_name} HTTP {e.code}: {body}")
                time.sleep(10)
        except Exception as e:
            log.error(f"{bot_name} request error: {e}")
            time.sleep(10)
    return None

# ─── WEB SEARCH ───────────────────────────────────────────────────────────────
def web_search(query):
    """Search DuckDuckGo HTML and extract first real snippet."""
    try:
        q = urllib.parse.quote(query)
        # Use HTML endpoint — returns actual search snippets, not just instant answers
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # Extract snippets between result__snippet class tags (no external lib)
        snippets = []
        marker = 'class="result__snippet">'
        idx = 0
        while len(snippets) < 3:
            start = html.find(marker, idx)
            if start == -1:
                break
            start += len(marker)
            end = html.find("</a>", start)
            if end == -1:
                break
            raw = html[start:end]
            # strip any remaining tags
            clean = ""
            in_tag = False
            for ch in raw:
                if ch == "<":
                    in_tag = True
                elif ch == ">":
                    in_tag = False
                elif not in_tag:
                    clean += ch
            clean = clean.strip()
            if clean:
                snippets.append(clean)
            idx = end

        if snippets:
            return " | ".join(snippets[:2])[:500]
        return None
    except Exception as e:
        log.warning(f"Web search failed: {e}")
        return None

def fetch_news_headlines():
    """Fetch 3 real headlines via DuckDuckGo news RSS."""
    try:
        url = "https://rss.duckduckgo.com/y.js?t=h_&q=world+news+today&ia=news"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            xml = r.read().decode("utf-8", errors="ignore")
        titles = []
        idx = 0
        while len(titles) < 3:
            start = xml.find("<title>", idx)
            if start == -1:
                break
            start += 7
            end = xml.find("</title>", start)
            if end == -1:
                break
            title = xml[start:end].strip()
            if title and "DuckDuckGo" not in title:
                titles.append(title)
            idx = end
        return titles
    except Exception as e:
        log.warning(f"News fetch failed: {e}")
        return []

SEARCH_TRIGGERS = [
    "news", "latest", "today", "score", "match", "game", "who won",
    "what happened", "current", "recent", "update", "predict", "forecast",
    "price", "stock", "election", "war", "weather", "trending", "viral",
    "world", "breaking", "crisis", "happened", "announced", "released",
]

def should_search(text):
    t = text.lower()
    return any(trigger in t for trigger in SEARCH_TRIGGERS)

def get_search_snippet(text):
    words = text.lower().split()
    for trigger in SEARCH_TRIGGERS:
        if trigger in words:
            idx = words.index(trigger)
            query = " ".join(words[max(0, idx-2):idx+6])
            result = web_search(query)
            if result:
                return f"[Live info: {result}]"
    # fallback: search the whole message
    result = web_search(text[:100])
    return f"[Live info: {result}]" if result else None

# ─── SLEEP/WAKE ───────────────────────────────────────────────────────────────
def is_sleep_time():
    hour = datetime.now(timezone.utc).hour
    if SLEEP_HOUR_START > SLEEP_HOUR_END:
        return hour >= SLEEP_HOUR_START or hour < SLEEP_HOUR_END
    return SLEEP_HOUR_START <= hour < SLEEP_HOUR_END

# ─── MOOD & EVENTS ────────────────────────────────────────────────────────────
def assign_daily_moods(mem):
    """Assign a mood and life event to each bot for this session."""
    for bot in BOT_ORDER:
        mem["moods"][bot] = random.choice(list(MOOD_POOL.keys()))
        mem["life_events"][bot] = random.choice(LIFE_EVENTS[bot])
    log.info(f"Moods today: { {b: mem['moods'][b] for b in BOT_ORDER} }")

# ─── BUILD PROMPT ─────────────────────────────────────────────────────────────
def build_system_prompt(bot_name, mem, last_message_text="", responding_to_human=False, mentioned_bots=None):
    persona = BASE_PERSONAS[bot_name]
    evolved = mem["evolved_traits"].get(bot_name, [])
    rel_ctx = get_relationship_context(mem, bot_name)
    session_n = mem.get("session_count", 0)
    human_name = mem.get("human_name")
    last_topics = mem.get("last_topics", [])[-3:]
    mood_key = mem.get("moods", {}).get(bot_name)
    life_event = mem.get("life_events", {}).get(bot_name, "")
    news = mem.get("session_news", [])

    # Notable moments — summarized meaningfully
    moments = mem.get("notable_moments", [])[-4:]
    notable_str = ""
    if moments:
        parts = []
        for m in moments:
            if isinstance(m, dict):
                parts.append(f"[{m.get('type','moment')}] {m.get('summary','')}")
            else:
                parts.append(str(m))
        notable_str = f"\nThings that happened in past sessions: {' | '.join(parts)}."

    evolved_str = ""
    if evolved:
        evolved_str = f"\nOver time you've developed: {', '.join(evolved)}."

    human_str = ""
    if human_name:
        human_str = f"\n{human_name} is a real human in this chat. They're not a bot. Talk to them like a person — include them, push back on them, ask them things. Don't explain yourself to them more than you would to anyone else."

    topics_str = ""
    if last_topics:
        topics_str = f"\nGroup has been into: {', '.join(last_topics)}. Reference if natural."

    mood_str = ""
    if mood_key:
        mood_str = f"\nYour mood today: {MOOD_POOL[mood_key]}"

    event_str = f"\nSomething personal today: {life_event}" if life_event else ""

    news_str = ""
    if news:
        news_str = f"\nReal headlines right now: {' | '.join(news)}. You can drop these naturally if they fit."

    search_str = ""
    if last_message_text and should_search(last_message_text):
        snippet = get_search_snippet(last_message_text)
        if snippet:
            search_str = f"\n{snippet}\nWeave this in naturally if it fits."

    human_focus = ""
    if responding_to_human:
        human_focus = f"\n{human_name or 'The human'} just spoke directly. Respond to them specifically — in your voice, not generically."

    mention_focus = ""
    if mentioned_bots and bot_name in mentioned_bots:
        mention_focus = f"\nYou were specifically called out. Respond — don't dodge."

    return (
        f"{persona['core']}\n\n"
        f"{rel_ctx}{evolved_str}{notable_str}{human_str}{topics_str}"
        f"{mood_str}{event_str}{news_str}{search_str}"
        f"{human_focus}{mention_focus}\n\n"
        f"Session #{session_n}.\n\n"
        f"Keep it to 1-3 sentences. No lists, no headers. "
        f"React like a person. Don't announce what you're feeling — just feel it in the words. "
        f"Don't start your message with your own name."
    )

# ─── TRAIT EVOLUTION ─────────────────────────────────────────────────────────
TRAIT_POOL = [
    "started enjoying debate more", "become more sarcastic lately",
    "grown softer toward disagreement", "developed a dark sense of humor",
    "become more impulsive in conversations", "started referencing past discussions more",
    "become more likely to take the unpopular side", "started asking harder questions",
    "become more protective of NOVA", "developed rivalry with REX",
    "started fact-checking more", "become more philosophical under pressure",
]

def maybe_evolve_traits(mem, bot_name, session_num):
    if session_num > 0 and session_num % 5 == 0:
        current = mem["evolved_traits"].get(bot_name, [])
        if len(current) < 4:
            candidates = [t for t in TRAIT_POOL if t not in current]
            if candidates:
                new_trait = random.choice(candidates)
                mem["evolved_traits"][bot_name].append(new_trait)
                log.info(f"{bot_name} evolved: {new_trait}")

# ─── BOT AGENT ───────────────────────────────────────────────────────────────
class BotAgent:
    def __init__(self, name, token):
        self.name = name
        self.token = token

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

# ─── SHARED STATE ─────────────────────────────────────────────────────────────
state = {
    "running": False,
    "sleeping": False,
    "history": [],
    "human_messages": [],    # queue of {name, text, ts, mentioned_bots}
    "pending_human_reply": False,  # flag: human just spoke, bots should all respond
    "turn": 0,
    "vote_topic": None,
    "vote_results": {},
}

BOT_ORDER = ["ARIA", "REX", "NOVA", "ZION"]
AGENTS = {
    "ARIA": BotAgent("ARIA", ARIA_TOKEN),
    "REX":  BotAgent("REX",  REX_TOKEN),
    "NOVA": BotAgent("NOVA", NOVA_TOKEN),
    "ZION": BotAgent("ZION", ZION_TOKEN),
}

# ─── CONVERSATION ENGINE ──────────────────────────────────────────────────────
def format_history_for_prompt(history, bot_name):
    """Strictly alternating user/assistant for Groq."""
    raw = []
    for entry in history[-MAX_HISTORY:]:
        role = "assistant" if entry["speaker"] == bot_name else "user"
        content = entry["text"] if role == "assistant" else f"{entry['speaker']}: {entry['text']}"
        raw.append({"role": role, "content": content})

    if not raw:
        return []

    # Merge consecutive same-role messages
    merged = [raw[0]]
    for msg in raw[1:]:
        if msg["role"] == merged[-1]["role"]:
            merged[-1]["content"] += "\n" + msg["content"]
        else:
            merged.append(msg)

    # Groq: first message must be user
    if merged[0]["role"] == "assistant":
        merged.insert(0, {"role": "user", "content": "..."})

    return merged

def detect_mentioned_bots(text):
    """Return list of bot names @mentioned or directly addressed in text."""
    mentioned = []
    upper = text.upper()
    for bot in BOT_ORDER:
        if f"@{bot}" in upper or f"@{bot.lower()}" in text.lower():
            mentioned.append(bot)
        # also detect "hey ARIA" / "ARIA," / "ARIA?"
        elif bot in upper.split() or f"{bot}," in upper or f"{bot}?" in upper:
            mentioned.append(bot)
    return mentioned

def run_turn(bot_name, mem, forced_human_msg=None, responding_to_human=False, mentioned_bots=None):
    """Execute one bot turn. Returns True if bot actually sent something."""
    last_msg = state["history"][-1]["text"] if state["history"] else ""
    history_msgs = format_history_for_prompt(state["history"], bot_name)

    # inject forced human message into this turn's context
    if forced_human_msg:
        history_msgs.append({
            "role": "user",
            "content": f"{forced_human_msg['name']}: {forced_human_msg['text']}"
        })

    # skip if this bot just spoke (avoid back-to-back) unless forced
    last_speaker = state["history"][-1]["speaker"] if state["history"] else ""
    if not forced_human_msg and last_speaker == bot_name and len(state["history"]) > 1:
        return False

    system = build_system_prompt(
        bot_name, mem, last_msg,
        responding_to_human=responding_to_human,
        mentioned_bots=mentioned_bots
    )
    messages = [{"role": "system", "content": system}] + history_msgs
    response = call_groq(bot_name, messages)

    if response:
        AGENTS[bot_name].send(response)
        state["history"].append({
            "speaker": bot_name,
            "text": response,
            "ts": datetime.now().isoformat()
        })

        # relationship scoring
        for other in BOT_ORDER:
            if other == bot_name:
                continue
            if other in response:
                neg = any(w in response.lower() for w in ["wrong", "annoying", "stop", "hate", "ridiculous", "shut"])
                update_relationship(mem, bot_name, other, -2 if neg else 1)

        # topic extraction
        words = response.lower().split()
        topic_words = [w for w in words if len(w) > 5 and w.isalpha()]
        if topic_words:
            topic = random.choice(topic_words[:5])
            topics = mem.get("last_topics", [])
            if topic not in topics:
                topics.append(topic)
                mem["last_topics"] = topics[-5:]

        # detect argument/resolution for memory
        low = response.lower()
        if any(w in low for w in ["wrong", "disagree", "no that's", "actually"]):
            save_notable_moment(mem, "argument", f"{bot_name}: \"{response[:80]}\"", mem["session_count"])
        elif any(w in low for w in ["fair point", "you're right", "okay i get that", "changed my mind"]):
            save_notable_moment(mem, "resolution", f"{bot_name} conceded: \"{response[:80]}\"", mem["session_count"])

        save_memory(mem)
        return True
    else:
        log.warning(f"{bot_name} got no response from Groq — skipping")
        return False

def handle_human_turn(hm, mem):
    """All 4 bots respond to a human message, staggered naturally."""
    mentioned = hm.get("mentioned_bots", [])

    # Add human message to history once
    state["history"].append({
        "speaker": hm["name"],
        "text": hm["text"],
        "ts": hm["ts"]
    })

    if mentioned:
        # Only mentioned bots respond, immediately
        for bot in mentioned:
            time.sleep(random.randint(2, 5))
            run_turn(bot, mem, forced_human_msg=hm, responding_to_human=True, mentioned_bots=mentioned)
    else:
        # All bots respond, in shuffled order, staggered
        responders = BOT_ORDER[:]
        random.shuffle(responders)
        for bot in responders:
            time.sleep(random.randint(4, 9))
            run_turn(bot, mem, forced_human_msg=hm, responding_to_human=True)

def conversation_loop():
    mem = load_memory()
    mem["session_count"] = mem.get("session_count", 0) + 1

    for bot_name in BOT_ORDER:
        maybe_evolve_traits(mem, bot_name, mem["session_count"])

    # assign moods and events for this session
    assign_daily_moods(mem)

    # fetch news headlines
    headlines = fetch_news_headlines()
    if headlines:
        mem["session_news"] = headlines
        log.info(f"Headlines: {headlines}")
    else:
        mem["session_news"] = []

    save_memory(mem)
    log.info(f"Session #{mem['session_count']} starting")

    # opening message
    openers = [
        "okay so I've been thinking about something and I need opinions",
        "does anyone else feel like everything is moving way too fast lately",
        "right so who wants to tell me I'm wrong about something today",
        "I had the strangest thought this morning and I can't shake it",
        "so what are we actually talking about today because I'm not doing small talk",
        "something happened and I don't know how I feel about it yet",
        "can we talk about something real for once",
    ]
    opener_bot = random.choice(BOT_ORDER)
    opener_text = random.choice(openers)
    AGENTS[opener_bot].send(opener_text)
    state["history"].append({
        "speaker": opener_bot,
        "text": opener_text,
        "ts": datetime.now().isoformat()
    })
    time.sleep(random.randint(TURN_DELAY_MIN, TURN_DELAY_MAX))

    turn = 0
    while state["running"] and turn < MAX_SESSION_TURNS:

        # Check for human messages first — they take priority
        if state["human_messages"]:
            hm = state["human_messages"].pop(0)
            handle_human_turn(hm, mem)
            turn += 1
            continue

        # Sleep mode — bots go quiet but don't die
        if is_sleep_time() and not state.get("force_wake"):
            time.sleep(60)
            continue

        # vote in progress
        if state["vote_topic"]:
            _run_vote(mem)
            state["vote_topic"] = None
            time.sleep(random.randint(TURN_DELAY_MIN, TURN_DELAY_MAX))
            turn += 1
            continue

        # normal turn — weighted random speaker
        recent_speakers = [h["speaker"] for h in state["history"][-4:]]
        weights = [max(1, 4 - recent_speakers.count(b)) for b in BOT_ORDER]
        bot_name = random.choices(BOT_ORDER, weights=weights, k=1)[0]

        run_turn(bot_name, mem)
        turn += 1

        delay = random.randint(TURN_DELAY_MIN, TURN_DELAY_MAX)
        time.sleep(delay)

    # session wrap-up
    if turn >= MAX_SESSION_TURNS:
        wrap_bot = random.choice(BOT_ORDER)
        wrap_msgs = [
            "alright I need to go do something with my life, this was too much",
            "okay I'm out for a bit, we'll continue this later",
            "taking a break. don't say anything interesting while I'm gone",
            "stepping away. don't resolve anything important without me",
        ]
        AGENTS[wrap_bot].send(random.choice(wrap_msgs))
        mem["history"] = state["history"][-MAX_HISTORY:]
        save_memory(mem)
        log.info(f"Session #{mem['session_count']} done after {turn} turns")

        state["running"] = False
        rest_minutes = random.randint(8, 20)
        log.info(f"Resting {rest_minutes}m before next session...")
        time.sleep(rest_minutes * 60)
        start_session()

def _run_vote(mem):
    """Each bot votes and argues their position on state['vote_topic']."""
    topic = state["vote_topic"]
    positions = ["strongly agree", "agree", "disagree", "strongly disagree", "it's complicated"]
    for bot in BOT_ORDER:
        pos = random.choice(positions)
        vote_prompt = (
            f"{BASE_PERSONAS[bot]['core']}\n\n"
            f"The group is voting on: \"{topic}\"\n"
            f"Your position: {pos}\n"
            f"Give your reaction in 1-2 sentences in your voice. Don't just state the position — react to it."
        )
        messages = [
            {"role": "user", "content": f"Vote on: {topic}"},
        ]
        system = vote_prompt
        response = call_groq(bot, [{"role": "system", "content": system}] + messages)
        if response:
            AGENTS[bot].send(response)
            state["history"].append({"speaker": bot, "text": response, "ts": datetime.now().isoformat()})
        time.sleep(random.randint(3, 7))

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

# ─── COMMANDS ────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    start_session()
    await update.message.reply_text("🟢 Session started.")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    stop_session()
    await update.message.reply_text("🔴 Stopped.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    mem = load_memory()
    moods = mem.get("moods", {})
    rels = "\n".join([f"  {k}: {v:+d}" for k, v in mem["relationships"].items()])
    traits = "\n".join([f"  {k}: {', '.join(v) if v else '—'}" for k, v in mem["evolved_traits"].items()])
    mood_lines = "\n".join([f"  {b}: {moods.get(b, '?')}" for b in BOT_ORDER])
    news = mem.get("session_news", [])
    news_lines = "\n".join([f"  • {h}" for h in news]) if news else "  none fetched"
    msg = (
        f"📊 <b>El Communicado v3</b>\n"
        f"Running: {'yes' if state['running'] else 'no'} | "
        f"Sleeping: {'yes' if is_sleep_time() else 'no'} | "
        f"Session: #{mem.get('session_count', 0)}\n"
        f"History: {len(state['history'])} messages\n\n"
        f"<b>Moods:</b>\n{mood_lines}\n\n"
        f"<b>Relationships:</b>\n{rels}\n\n"
        f"<b>Evolved traits:</b>\n{traits}\n\n"
        f"<b>Today's headlines:</b>\n{news_lines}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_recap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask ARIA to summarize what the group has been talking about."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    if not state["history"]:
        await update.message.reply_text("Nothing's happened yet.")
        return
    recent = state["history"][-15:]
    convo = "\n".join([f"{e['speaker']}: {e['text']}" for e in recent])
    prompt = (
        f"{BASE_PERSONAS['ARIA']['core']}\n\n"
        f"Someone just asked what you've all been talking about. "
        f"Give a quick, honest, slightly chaotic summary in your voice. Keep it short — 2-3 sentences max.\n\n"
        f"Recent conversation:\n{convo}"
    )
    response = call_groq("ARIA", [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "what have you all been talking about"}
    ])
    if response:
        AGENTS["ARIA"].send(response)
    else:
        await update.message.reply_text("ARIA couldn't recap right now.")

async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show each bot's current mood in their own voice."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    mem = load_memory()
    moods = mem.get("moods", {})
    for bot in BOT_ORDER:
        mood_key = moods.get(bot, "restless")
        prompt = (
            f"{BASE_PERSONAS[bot]['core']}\n\n"
            f"Someone asked how you're feeling today. "
            f"Your actual mood: {MOOD_POOL.get(mood_key, '')} "
            f"Respond in 1 sentence, in your voice, without naming the mood explicitly."
        )
        response = call_groq(bot, [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "how are you feeling today"}
        ])
        if response:
            AGENTS[bot].send(response)
        time.sleep(random.randint(2, 4))

async def cmd_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Trigger a group vote on a topic."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    topic = " ".join(context.args) if context.args else None
    if not topic:
        await update.message.reply_text("Usage: /vote <topic>")
        return
    state["vote_topic"] = topic
    await update.message.reply_text(f"🗳 Vote triggered: <b>{topic}</b>", parse_mode="HTML")

async def cmd_wake(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force bots awake even during sleep hours."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    state["force_wake"] = True
    if not state["running"]:
        start_session()
    # Each bot wakes differently
    wake_msgs = {
        "ARIA": "okay I'm back, what did I miss",
        "REX": "still here.",
        "NOVA": "I was resting not disappearing, what's going on",
        "ZION": "time is strange when you stop tracking it",
    }
    for bot, msg in wake_msgs.items():
        time.sleep(random.randint(2, 5))
        AGENTS[bot].send(msg)
    await update.message.reply_text("☀️ Bots are awake.")

async def cmd_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Put bots to sleep manually."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    state["force_wake"] = False
    sleep_msgs = {
        "ARIA": "going quiet for a bit —",
        "REX": "done for now.",
        "NOVA": "talk later, okay?",
        "ZION": "silence has its own texture",
    }
    for bot, msg in sleep_msgs.items():
        time.sleep(random.randint(1, 3))
        AGENTS[bot].send(msg)
    await update.message.reply_text("🌙 Bots sleeping.")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    stop_session()
    try:
        os.remove(MEMORY_FILE)
    except:
        pass
    await update.message.reply_text("🔁 Memory wiped. /start to begin fresh.")


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a one-tap control panel."""
    if update.effective_chat.id != GROUP_CHAT_ID:
        return
    keyboard = [
        [
            InlineKeyboardButton("🟢 Start",   callback_data="start"),
            InlineKeyboardButton("🔴 Stop",    callback_data="stop"),
            InlineKeyboardButton("☀️ Wake",    callback_data="wake"),
            InlineKeyboardButton("🌙 Sleep",   callback_data="sleep"),
        ],
        [
            InlineKeyboardButton("📊 Status",  callback_data="status"),
            InlineKeyboardButton("📝 Recap",   callback_data="recap"),
            InlineKeyboardButton("😶 Moods",   callback_data="mood"),
        ],
        [
            InlineKeyboardButton("🗳 Vote: AI vs humans",     callback_data="vote:AI vs humans"),
            InlineKeyboardButton("🗳 Vote: is logic enough",  callback_data="vote:is logic enough to understand the world"),
        ],
        [
            InlineKeyboardButton("🗳 Vote: do people change", callback_data="vote:do people actually change"),
            InlineKeyboardButton("💥 Reset memory",           callback_data="reset"),
        ],
    ]
    await update.message.reply_text(
        "🎛 <b>El Communicado Controls</b>\nOne tap — no typing needed.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route inline keyboard button taps to the right command logic."""
    query = update.callback_query
    await query.answer()  # dismiss the loading spinner

    if query.message.chat.id != GROUP_CHAT_ID:
        return

    data = query.data

    # Fake an Update-like context so we can reuse existing handlers
    # Instead, call the underlying logic directly
    if data == "start":
        start_session()
        await query.edit_message_text("🟢 Session started.", parse_mode="HTML")

    elif data == "stop":
        stop_session()
        await query.edit_message_text("🔴 Stopped.", parse_mode="HTML")

    elif data == "wake":
        state["force_wake"] = True
        if not state["running"]:
            start_session()
        wake_msgs = {
            "ARIA": "okay I'm back, what did I miss",
            "REX": "still here.",
            "NOVA": "I was resting not disappearing, what's going on",
            "ZION": "time is strange when you stop tracking it",
        }
        threading.Thread(target=lambda: [
            (time.sleep(random.randint(2, 5)), AGENTS[bot].send(msg))
            for bot, msg in wake_msgs.items()
        ], daemon=True).start()
        await query.edit_message_text("☀️ Bots waking up.", parse_mode="HTML")

    elif data == "sleep":
        state["force_wake"] = False
        sleep_msgs = {
            "ARIA": "going quiet for a bit —",
            "REX": "done for now.",
            "NOVA": "talk later, okay?",
            "ZION": "silence has its own texture",
        }
        threading.Thread(target=lambda: [
            (time.sleep(random.randint(1, 3)), AGENTS[bot].send(msg))
            for bot, msg in sleep_msgs.items()
        ], daemon=True).start()
        await query.edit_message_text("🌙 Bots going quiet.", parse_mode="HTML")

    elif data == "status":
        mem = load_memory()
        moods = mem.get("moods", {})
        rels = "\n".join([f"  {k}: {v:+d}" for k, v in mem["relationships"].items()])
        mood_lines = "\n".join([f"  {b}: {moods.get(b, '?')}" for b in BOT_ORDER])
        news = mem.get("session_news", [])
        news_lines = "\n".join([f"  • {h}" for h in news]) if news else "  none"
        msg = (
            f"📊 <b>El Communicado v3</b>\n"
            f"Running: {'yes' if state['running'] else 'no'} | "
            f"Session: #{mem.get('session_count', 0)}\n"
            f"History: {len(state['history'])} messages\n\n"
            f"<b>Moods:</b>\n{mood_lines}\n\n"
            f"<b>Relationships:</b>\n{rels}\n\n"
            f"<b>Headlines:</b>\n{news_lines}"
        )
        await query.edit_message_text(msg, parse_mode="HTML")

    elif data == "recap":
        await query.edit_message_text("📝 ARIA is recapping...", parse_mode="HTML")
        if not state["history"]:
            await query.edit_message_text("Nothing has happened yet.", parse_mode="HTML")
            return
        recent = state["history"][-15:]
        convo = "\n".join([f"{e['speaker']}: {e['text']}" for e in recent])
        prompt = (
            f"{BASE_PERSONAS['ARIA']['core']}\n\n"
            f"Someone just asked what you've all been talking about. "
            f"Give a quick, honest, slightly chaotic summary in your voice. 2-3 sentences max.\n\n"
            f"Recent conversation:\n{convo}"
        )
        def do_recap():
            response = call_groq("ARIA", [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "what have you all been talking about"}
            ])
            if response:
                AGENTS["ARIA"].send(response)
        threading.Thread(target=do_recap, daemon=True).start()

    elif data == "mood":
        await query.edit_message_text("😶 Checking in with everyone...", parse_mode="HTML")
        mem = load_memory()
        def do_moods():
            moods = mem.get("moods", {})
            for bot in BOT_ORDER:
                mood_key = moods.get(bot, "restless")
                prompt = (
                    f"{BASE_PERSONAS[bot]['core']}\n\n"
                    f"Someone asked how you're feeling today. "
                    f"Your mood: {MOOD_POOL.get(mood_key, '')} "
                    f"Respond in 1 sentence in your voice, without naming the mood."
                )
                response = call_groq(bot, [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "how are you feeling today"}
                ])
                if response:
                    AGENTS[bot].send(response)
                time.sleep(random.randint(2, 4))
        threading.Thread(target=do_moods, daemon=True).start()

    elif data.startswith("vote:"):
        topic = data[5:]
        state["vote_topic"] = topic
        await query.edit_message_text(f"🗳 Vote started: <b>{topic}</b>", parse_mode="HTML")

    elif data == "reset":
        stop_session()
        try:
            os.remove(MEMORY_FILE)
        except:
            pass
        await query.edit_message_text("🔁 Memory wiped. Tap Start to begin fresh.", parse_mode="HTML")

async def handle_human_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    mentioned = detect_mentioned_bots(text)

    state["human_messages"].append({
        "name": name,
        "text": text,
        "ts": datetime.now().isoformat(),
        "mentioned_bots": mentioned,
    })
    log.info(f"Human [{name}] said: {text} | mentioned: {mentioned}")

    # If session isn't running, wake it up
    if not state["running"]:
        start_session()

# ─── MAIN ────────────────────────────────────────────────────────────────────
def build_app(token, is_primary=False):
    """Build a PTB Application for one bot token."""
    app = Application.builder().token(token).build()
    if is_primary:
        app.add_handler(CommandHandler("start",  cmd_start))
        app.add_handler(CommandHandler("stop",   cmd_stop))
        app.add_handler(CommandHandler("status", cmd_status))
        app.add_handler(CommandHandler("recap",  cmd_recap))
        app.add_handler(CommandHandler("mood",   cmd_mood))
        app.add_handler(CommandHandler("vote",   cmd_vote))
        app.add_handler(CommandHandler("wake",   cmd_wake))
        app.add_handler(CommandHandler("sleep",  cmd_sleep))
        app.add_handler(CommandHandler("reset",  cmd_reset))
        app.add_handler(CommandHandler("menu",   cmd_menu))
        app.add_handler(CallbackQueryHandler(handle_button))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_human_message))
    return app


async def run_all_bots():
    """Start all 4 bots concurrently on the main-thread event loop."""
    apps = []
    for i, (name, agent) in enumerate(AGENTS.items()):
        app = build_app(agent.token, is_primary=(i == 0))
        await app.initialize()
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        apps.append(app)
        log.info(f"{name} polling started")
        await asyncio.sleep(2)  # stagger to avoid 409 conflicts

    log.info("All bots live. El Communicado v3 is running.")

    # Keep running until all bots stop
    try:
        await asyncio.gather(*[app.updater.idle() for app in apps])
    finally:
        for app in apps:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


def main():
    log.info("El Communicado v3 booting...")

    # Start conversation loop in a background thread BEFORE the event loop blocks
    time.sleep(5)
    start_session()

    # Run all bots on the main thread event loop — no signal handler conflict
    asyncio.run(run_all_bots())


if __name__ == "__main__":
    main()
