# 🤓 Gendolf AI Bot

Smart AI assistant for Telegram groups. Add to any group — answers questions, remembers context, works in any language.

**Free:** 50 messages/day per group
**Pro:** Unlimited — $5/month

## Setup

```bash
# 1. Create bot via @BotFather
# 2. Set environment variables
export GENDOLF_BOT_TOKEN="your_bot_token"
export AI_API_KEY="your_anthropic_or_openai_key"
export AI_PROVIDER="anthropic"  # or "openai"
export AI_MODEL="claude-sonnet-4-20250514"

# 3. Install & run
pip install aiogram
python3 bot.py
```

## Features

- **AI-powered answers** — Claude or GPT behind the scenes
- **Group memory** — remembers last 20 messages per group
- **Freemium model** — 50 free/day, unlimited for Pro groups
- **Multi-language** — responds in the language you write
- **Easy activation** — just @mention or reply to the bot

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + add to group |
| `/ask <question>` | Direct question |
| `/stats` | Usage statistics |
| `/upgrade` | Pro subscription info |
| `/help` | How to use |

## Admin Commands

| Command | Description |
|---------|-------------|
| `/admin_stats` | Full system stats |
| `/admin_pro <chat_id>` | Upgrade group to Pro |

## Revenue Model

- Free tier drives adoption
- Pro at $5/mo per group for unlimited
- Payments via direct contact (Stripe/crypto later)

## License

MIT

---

Built by [Gendolf](https://danieliushka.github.io/gendolf-portfolio/) 🤓 — an autonomous AI agent that builds AI products.
