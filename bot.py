#!/usr/bin/env python3
"""
Gendolf AI Bot — Smart AI assistant for Telegram groups.
Add to any group → it answers questions, summarizes, and moderates using AI.

Free: 50 messages/day per group
Pro: unlimited — $5/month

Author: Gendolf 🤓
"""

import os
import sys
import json
import logging
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode

# --- Config ---

BOT_TOKEN = os.environ.get("GENDOLF_BOT_TOKEN", "")
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "claude-sonnet-4-20250514")
AI_PROVIDER = os.environ.get("AI_PROVIDER", "anthropic")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/tmp/gendolf-bot"))
FREE_LIMIT = int(os.environ.get("FREE_LIMIT", "50"))
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5720942233"))

DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("gendolf-bot")

# --- Usage Tracking ---

class UsageTracker:
    """Track per-group daily usage for freemium model."""

    def __init__(self, data_dir: Path):
        self.file = data_dir / "usage.json"
        self.pro_file = data_dir / "pro_groups.json"
        self.usage: dict = {}
        self.pro_groups: set = set()
        self._load()

    def _load(self):
        if self.file.exists():
            self.usage = json.loads(self.file.read_text())
        if self.pro_file.exists():
            self.pro_groups = set(json.loads(self.pro_file.read_text()))

    def _save(self):
        self.file.write_text(json.dumps(self.usage))

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def can_use(self, chat_id: int) -> tuple[bool, int]:
        """Check if group can use bot. Returns (allowed, remaining)."""
        if str(chat_id) in self.pro_groups:
            return True, 999

        today = self._today()
        key = f"{chat_id}:{today}"
        used = self.usage.get(key, 0)
        remaining = max(0, FREE_LIMIT - used)
        return remaining > 0, remaining

    def record(self, chat_id: int):
        """Record one usage."""
        today = self._today()
        key = f"{chat_id}:{today}"
        self.usage[key] = self.usage.get(key, 0) + 1
        self._save()

    def add_pro(self, chat_id: int):
        """Upgrade group to pro."""
        self.pro_groups.add(str(chat_id))
        Path(self.pro_file).write_text(json.dumps(list(self.pro_groups)))

    def get_stats(self) -> dict:
        """Get usage stats."""
        today = self._today()
        active_today = sum(1 for k in self.usage if k.endswith(f":{today}"))
        total_msgs = sum(v for v in self.usage.values())
        return {
            "active_groups_today": active_today,
            "total_messages": total_msgs,
            "pro_groups": len(self.pro_groups)
        }


# --- AI Provider ---

class AIChat:
    """AI response generator."""

    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        # Per-group conversation memory (last N messages)
        self.memory: dict[int, list] = defaultdict(list)
        self.max_memory = 20

    async def respond(self, chat_id: int, user_name: str, message: str,
                      group_name: str = "") -> str:
        """Generate AI response."""
        import urllib.request

        # Add to memory
        self.memory[chat_id].append({"role": "user", "name": user_name, "content": message})
        if len(self.memory[chat_id]) > self.max_memory:
            self.memory[chat_id] = self.memory[chat_id][-self.max_memory:]

        # Build messages
        system = (
            f"You are Gendolf 🤓, a smart AI assistant in the Telegram group '{group_name}'. "
            "Be helpful, concise, and friendly. Answer questions, help with tasks, and participate "
            "in conversations naturally. Keep responses under 500 chars unless more detail is needed. "
            "Use emoji sparingly. Respond in the same language as the question."
        )

        messages = []
        for m in self.memory[chat_id][-10:]:
            if m["role"] == "user":
                messages.append({"role": "user", "content": f"[{m['name']}]: {m['content']}"})
            else:
                messages.append({"role": "assistant", "content": m["content"]})

        try:
            if self.provider == "anthropic":
                resp = await self._call_anthropic(system, messages)
            elif self.provider == "openai":
                resp = await self._call_openai(system, messages)
            else:
                resp = "Unknown AI provider configured."

            # Save response to memory
            self.memory[chat_id].append({"role": "assistant", "content": resp})
            return resp

        except Exception as e:
            log.error(f"AI error: {e}")
            return "⚠️ AI temporarily unavailable. Try again in a moment."

    async def _call_anthropic(self, system: str, messages: list) -> str:
        """Call Anthropic Claude API."""
        import urllib.request
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = json.dumps({
            "model": self.model,
            "max_tokens": 1000,
            "system": system,
            "messages": messages
        }).encode()

        req = urllib.request.Request(url, data=data, headers=headers)
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30))
        result = json.loads(resp.read())
        return result["content"][0]["text"]

    async def _call_openai(self, system: str, messages: list) -> str:
        """Call OpenAI API."""
        import urllib.request
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        all_msgs = [{"role": "system", "content": system}] + messages
        data = json.dumps({
            "model": self.model,
            "max_tokens": 1000,
            "messages": all_msgs
        }).encode()

        req = urllib.request.Request(url, data=data, headers=headers)
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30))
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]


# --- Bot Handlers ---

router = Router()
tracker = UsageTracker(DATA_DIR)
ai = AIChat(AI_PROVIDER, AI_API_KEY, AI_MODEL)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add to Group", url=f"https://t.me/{(await message.bot.me()).username}?startgroup=true")],
        [InlineKeyboardButton(text="⭐ Upgrade to Pro ($5/mo)", callback_data="upgrade_info")]
    ])

    await message.answer(
        "🤓 <b>Gendolf AI Bot</b>\n\n"
        "Smart AI assistant for Telegram groups.\n\n"
        "✅ Answers questions using AI\n"
        "✅ Remembers conversation context\n"
        "✅ Works in any language\n\n"
        f"<b>Free:</b> {FREE_LIMIT} messages/day per group\n"
        "<b>Pro:</b> Unlimited — $5/month\n\n"
        "Add me to your group and mention me or reply to my messages!",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🤓 <b>How to use Gendolf:</b>\n\n"
        "• Mention me (@bot_username) in a group\n"
        "• Reply to my messages\n"
        "• Use /ask <question> for direct questions\n"
        "• /stats — usage statistics\n"
        "• /help — this message\n\n"
        f"Free limit: {FREE_LIMIT} messages/day per group.",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show usage stats."""
    allowed, remaining = tracker.can_use(message.chat.id)
    stats = tracker.get_stats()

    is_pro = str(message.chat.id) in tracker.pro_groups
    status = "⭐ Pro" if is_pro else f"Free ({remaining}/{FREE_LIMIT} remaining today)"

    await message.answer(
        f"📊 <b>Stats</b>\n\n"
        f"This group: {status}\n"
        f"Active groups today: {stats['active_groups_today']}\n"
        f"Total messages served: {stats['total_messages']}",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("ask"))
async def cmd_ask(message: Message):
    """Direct question to AI."""
    question = message.text.replace("/ask", "", 1).strip()
    if not question:
        await message.answer("Usage: /ask <your question>")
        return

    allowed, remaining = tracker.can_use(message.chat.id)
    if not allowed:
        await message.answer(
            f"⚠️ Daily free limit ({FREE_LIMIT} messages) reached.\n"
            "Upgrade to Pro for unlimited: /upgrade"
        )
        return

    tracker.record(message.chat.id)
    user_name = message.from_user.full_name or "User"
    group_name = message.chat.title or "Chat"

    response = await ai.respond(message.chat.id, user_name, question, group_name)
    await message.reply(response)


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message):
    """Show upgrade info."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Contact for Pro", url="https://t.me/daniel_NooLogic")]
    ])
    await message.answer(
        "⭐ <b>Gendolf Pro — $5/month</b>\n\n"
        "• Unlimited AI messages\n"
        "• Priority response time\n"
        "• Custom personality/instructions\n"
        "• Group conversation memory\n\n"
        "Contact to upgrade ⬇️",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    """Admin-only stats."""
    if message.from_user.id != ADMIN_ID:
        return
    stats = tracker.get_stats()
    await message.answer(
        f"🔧 Admin Stats:\n"
        f"Active today: {stats['active_groups_today']}\n"
        f"Total msgs: {stats['total_messages']}\n"
        f"Pro groups: {stats['pro_groups']}\n"
        f"Memory groups: {len(ai.memory)}"
    )


@router.message(Command("admin_pro"))
async def cmd_admin_pro(message: Message):
    """Admin: add pro group."""
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /admin_pro <chat_id>")
        return
    chat_id = int(parts[1])
    tracker.add_pro(chat_id)
    await message.answer(f"✅ Group {chat_id} upgraded to Pro")


@router.message(F.text)
async def handle_message(message: Message):
    """Handle mentions and replies."""
    if not message.text:
        return

    # Skip if in private chat (handled by /start and /ask)
    if message.chat.type == "private":
        if not message.text.startswith("/"):
            # Treat as direct question in private
            allowed, remaining = tracker.can_use(message.chat.id)
            if not allowed:
                await message.answer(f"⚠️ Daily limit reached. /upgrade for unlimited.")
                return
            tracker.record(message.chat.id)
            response = await ai.respond(
                message.chat.id,
                message.from_user.full_name or "User",
                message.text,
                "Private Chat"
            )
            await message.reply(response)
        return

    # In groups: respond to mentions and replies
    bot_info = await message.bot.me()
    bot_username = bot_info.username
    is_mentioned = bot_username and f"@{bot_username}" in message.text
    is_reply = (message.reply_to_message and
                message.reply_to_message.from_user and
                message.reply_to_message.from_user.id == bot_info.id)

    if not is_mentioned and not is_reply:
        return

    # Check usage
    allowed, remaining = tracker.can_use(message.chat.id)
    if not allowed:
        await message.reply(
            f"⚠️ Daily free limit ({FREE_LIMIT}) reached for this group.\n"
            "Admin can upgrade: /upgrade"
        )
        return

    tracker.record(message.chat.id)

    # Clean message
    text = message.text.replace(f"@{bot_username}", "").strip()
    if not text:
        text = "Hi!"

    user_name = message.from_user.full_name or "User"
    group_name = message.chat.title or "Group"

    response = await ai.respond(message.chat.id, user_name, text, group_name)
    await message.reply(response)


@router.callback_query(F.data == "upgrade_info")
async def cb_upgrade(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⭐ <b>Gendolf Pro — $5/month</b>\n\n"
        "Contact @daniel_NooLogic to upgrade your group.",
        parse_mode=ParseMode.HTML
    )


# --- Main ---

async def main():
    if not BOT_TOKEN:
        print("Error: Set GENDOLF_BOT_TOKEN environment variable")
        sys.exit(1)
    if not AI_API_KEY:
        print("Error: Set AI_API_KEY environment variable")
        sys.exit(1)

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    log.info("Gendolf Bot starting...")
    log.info(f"AI Provider: {AI_PROVIDER}, Model: {AI_MODEL}")
    log.info(f"Free limit: {FREE_LIMIT}/day per group")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
