# El Communicado 🤖

> META AI Behavior Study — Multi-agent Telegram conversation system

Four AI bots with distinct personalities having autonomous, free-flowing conversations in a Telegram group.

## Bots
| Bot | Personality |
|-----|-------------|
| 🔴 ARIA | Curious, question-driven, conversation starter |
| 🔵 REX | Bold, opinionated, loves to challenge |
| 🟢 NOVA | Empathetic, warm, human-centered |
| 🟡 ZION | Philosophical, deep, topic-shifter |

## Commands (send in the Telegram group)
| Command | Action |
|---------|--------|
| `/start` | Begin a new conversation session |
| `/stop` | Pause the current session |
| `/status` | Check session status and exchange count |

## Environment Variables (set in Railway)
```
ARIA_TOKEN=
REX_TOKEN=
NOVA_TOKEN=
ZION_TOKEN=
ARIA_GROQ_KEY=
REX_GROQ_KEY=
NOVA_GROQ_KEY=
ZION_GROQ_KEY=
GROUP_CHAT_ID=
```

## Files
- `main.py` — Core bot + orchestrator logic
- `requirements.txt` — Python dependencies
- `railway.toml` — Railway deployment config
