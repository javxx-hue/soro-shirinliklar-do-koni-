"""Core assistant logic, business update routing, and reply generation using Gemini."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Union

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BusinessConnection, Message

from assistant.config import Settings
from assistant.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiLimitError,
)
from assistant.language import detect_language
from assistant.prompts import SKIP_TOKEN, build_system_prompt, build_user_prompt
from assistant.store import (
    HistoryStore,
    RuntimeState,
    SeenMessages,
    ensure_private_dir,
)

logger = logging.getLogger(__name__)


class Outcome(str, Enum):
    PREVIEWED = "previewed"
    SENT = "sent"
    DUPLICATE = "duplicate"
    IGNORED_BOT = "ignored_bot"
    NO_CONNECTION = "no_connection"
    FOREIGN_CONNECTION = "foreign_connection"
    CONNECTION_DISABLED = "connection_disabled"
    UNSUPPORTED = "unsupported"
    OWNER_MESSAGE = "owner_message"
    OWNER_ACTIVE = "owner_active"
    PAUSED = "paused"
    LIMITED = "limited"
    SKIPPED = "skipped"
    PERMISSION_DENIED = "permission_denied"
    ERROR = "error"


@dataclass
class Preview:
    connection_id: str
    chat_id: int
    chat_name: str
    language: Optional[str]
    incoming: str
    reply: str
    note: Optional[str] = None


def print_preview(preview: Preview) -> None:
    lines = [
        "--- [PREVIEW, not sent] ---",
        f"Chat: {preview.chat_name} (ID: {preview.chat_id}, Connection: {preview.connection_id})",
        f"Language: {preview.language or 'unknown'}",
        f"Incoming: {preview.incoming}",
        f"Generated Reply: {preview.reply}",
    ]
    if preview.note:
        lines.append(f"Note: {preview.note}")
    lines.append("---------------------------")
    print("\n".join(lines))


def describe(message: Message) -> Optional[str]:
    """Extract a text description from message text or media captions."""
    if message.text:
        return message.text.strip()

    caption = message.caption.strip() if message.caption else ""

    if message.voice:
        return f"[voice message] {caption}".strip()
    if message.photo:
        return f"[photo] {caption}".strip()
    if message.video:
        return f"[video] {caption}".strip()
    if message.document:
        return f"[document] {caption}".strip()
    if message.sticker:
        emoji = message.sticker.emoji or ""
        return f"[sticker] {emoji}".strip()
    if message.audio:
        return f"[audio] {caption}".strip()
    if message.animation:
        return f"[animation] {caption}".strip()
    if message.video_note:
        return "[video note]"

    return None


def can_reply(connection: Any) -> bool:
    """Check whether bot has rights to send messages in business connection."""
    if hasattr(connection, "rights") and connection.rights is not None:
        return getattr(connection.rights, "can_reply", False)
    return getattr(connection, "can_reply", False)


def read_profile(path: Path) -> str:
    """Read profile markdown file, stripping HTML comments."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def split_chunks(text: str, max_length: int = 4000) -> List[str]:
    """Split text into chunks not exceeding max_length."""
    if len(text) <= max_length:
        return [text]
    chunks: List[str] = []
    curr = text
    while curr:
        if len(curr) <= max_length:
            chunks.append(curr)
            break
        split_idx = curr.rfind("\n", 0, max_length)
        if split_idx == -1:
            split_idx = curr.rfind(" ", 0, max_length)
        if split_idx == -1:
            split_idx = max_length
        chunks.append(curr[:split_idx].strip())
        curr = curr[split_idx:].strip()
    return chunks


class Assistant:
    """Orchestrates Telegram Business messaging and Gemini generation."""

    def __init__(
        self,
        settings: Settings,
        generator: Any,
        *,
        clock: Callable[[], float] = time.time,
        preview_sink: Callable[[Preview], None] = print_preview,
    ) -> None:
        self.settings = settings
        self.generator = generator
        self.clock = clock
        self.preview_sink = preview_sink

        ensure_private_dir(self.settings.data_dir)
        self.history = HistoryStore(
            self.settings.data_dir / "history.json",
            limit=self.settings.history_limit,
        )
        self.seen = SeenMessages(self.settings.data_dir / "seen.json")
        self.state = RuntimeState(self.settings.data_dir / "state.json")
        self.previews_path = self.settings.data_dir / "previews.jsonl"

        self.connection_cache: Dict[str, Any] = {}
        self.outcomes: Deque[Outcome] = deque(maxlen=100)
        self._takeovers: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._last_error_notify: float = 0.0

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _append_preview_log(self, preview: Preview) -> None:
        try:
            line = json.dumps(asdict(preview), ensure_ascii=False)
            parent = ensure_private_dir(self.previews_path.parent)
            is_new = not self.previews_path.exists()
            with open(self.previews_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            if is_new and os.name == "posix":
                try:
                    os.chmod(self.previews_path, 0o600)
                except OSError:
                    pass
        except OSError as e:
            logger.error(f"Failed to append to previews.jsonl: {e}")

    async def _notify_owner(self, bot: Bot, text: str) -> None:
        if not self.settings.owner_id:
            return
        try:
            await bot.send_message(chat_id=self.settings.owner_id, text=text)
        except Exception as e:
            logger.warning(f"Could not notify owner: {e}")

    def on_business_connection(self, connection: BusinessConnection) -> None:
        """Handle incoming business connection updates and cache them."""
        conn_id = connection.id
        self.connection_cache[conn_id] = connection

        user_id = connection.user.id if connection.user else None
        if user_id != self.settings.owner_id:
            logger.warning(
                f"Business connection {conn_id} received for foreign user={user_id} "
                f"(expected owner={self.settings.owner_id})"
            )
            return

        can_rep = can_reply(connection)
        logger.info(
            f"Business connection {conn_id}: user={user_id} enabled={connection.is_enabled} "
            f"can_reply={can_rep}"
        )

    async def on_business_message(self, bot: Bot, message: Message) -> Outcome:
        """Process business messages following the strict 12-step sequence."""
        now = self.clock()

        # Step 1: Check business connection ID
        conn_id = message.business_connection_id
        if not conn_id:
            self.outcomes.append(Outcome.NO_CONNECTION)
            return Outcome.NO_CONNECTION

        # Step 2: Deduplication before any await
        chat_id = message.chat.id
        msg_id = message.message_id
        dup_key = f"{conn_id}:{chat_id}:{msg_id}"
        if not self.seen.first_time(dup_key):
            self.outcomes.append(Outcome.DUPLICATE)
            return Outcome.DUPLICATE

        # Step 3: Ignore bot messages
        if getattr(message, "sender_business_bot", None) is not None or (
            message.from_user and message.from_user.is_bot
        ):
            self.outcomes.append(Outcome.IGNORED_BOT)
            return Outcome.IGNORED_BOT

        # Step 4: Resolve connection from cache or Telegram
        conn = self.connection_cache.get(conn_id)
        if conn is None:
            try:
                conn = await bot.get_business_connection(conn_id)
                self.connection_cache[conn_id] = conn
            except TelegramAPIError as e:
                logger.warning(f"Failed to fetch connection {conn_id}: {e}")
                self.outcomes.append(Outcome.NO_CONNECTION)
                return Outcome.NO_CONNECTION

        user_id = conn.user.id if conn.user else None
        if user_id != self.settings.owner_id:
            self.outcomes.append(Outcome.FOREIGN_CONNECTION)
            return Outcome.FOREIGN_CONNECTION

        if not conn.is_enabled:
            self.outcomes.append(Outcome.CONNECTION_DISABLED)
            return Outcome.CONNECTION_DISABLED

        # Step 5: Check message description
        incoming_desc = describe(message)
        if incoming_desc is None:
            self.outcomes.append(Outcome.UNSUPPORTED)
            return Outcome.UNSUPPORTED

        chat_key = f"{conn_id}:{chat_id}"
        is_from_owner = message.from_user and message.from_user.id == self.settings.owner_id

        # Step 6: Owner messages
        if is_from_owner:
            self.history.add(chat_key, {
                "role": "owner",
                "name": "You",
                "text": incoming_desc,
                "lang": None,
                "ts": now,
            })
            if self.settings.owner_takeover_minutes > 0:
                self._takeovers[chat_key] = now + self.settings.owner_takeover_minutes * 60
            self.outcomes.append(Outcome.OWNER_MESSAGE)
            return Outcome.OWNER_MESSAGE

        # Step 7: Language detection and history recording for other user
        sender_name = message.from_user.full_name if message.from_user else "User"
        text_for_lang = re.sub(
            r"^\[(voice message|photo|video|document|sticker|audio|animation|video note)\]\s*",
            "",
            incoming_desc,
            flags=re.IGNORECASE,
        ).strip()
        lang = detect_language(text_for_lang) or self.history.last_language(chat_key)
        self.history.add(chat_key, {
            "role": "other",
            "name": sender_name,
            "text": incoming_desc,
            "lang": lang,
            "ts": now,
        })

        # Step 8: Check blockades under per-chat lock
        lock = self._get_lock(chat_key)
        async with lock:
            if self.state.is_paused():
                self.outcomes.append(Outcome.PAUSED)
                return Outcome.PAUSED

            if self.state.get_limit_until() > now:
                self.outcomes.append(Outcome.LIMITED)
                return Outcome.LIMITED

            if self._takeovers.get(chat_key, 0) > now:
                self.outcomes.append(Outcome.OWNER_ACTIVE)
                return Outcome.OWNER_ACTIVE

            # Step 9: Generate reply via Gemini
            profile_content = read_profile(self.settings.profile_path)
            sys_prompt = build_system_prompt(profile_content, now)
            history_items = self.history.get(chat_key)
            user_prompt = build_user_prompt(history_items, lang)

            try:
                if hasattr(self.generator, "run"):
                    reply = await self.generator.run(user_prompt, sys_prompt)
                elif hasattr(self.generator, "generate"):
                    reply = await self.generator.generate(user_prompt, sys_prompt)
                else:
                    reply = await self.generator(user_prompt, sys_prompt)
            except GeminiLimitError as e:
                until = e.resets_at if e.resets_at and e.resets_at > now else now + self.settings.limit_cooldown_minutes * 60
                self.state.set_limit_until(until)
                logger.warning(f"Gemini quota or rate limit reached: {e.detail or e}")
                if self.settings.auto_send:
                    reset_msg = e.reset_text or "bir ozdan so'ng"
                    await self._notify_owner(bot, f"⚠️ Gemini kvota limiti tugadi. Qayta tiklanish: {reset_msg}.")
                self.outcomes.append(Outcome.LIMITED)
                return Outcome.LIMITED
            except GeminiError as e:
                logger.error(f"Gemini error: {e}")
                if self.settings.auto_send and (now - self._last_error_notify > 600):
                    self._last_error_notify = now
                    await self._notify_owner(bot, f"⚠️ Gemini bilan aloqada xatolik yuz berdi: {e}")
                self.outcomes.append(Outcome.ERROR)
                return Outcome.ERROR

            # Step 10: Check empty or SKIP token
            if not reply or reply.strip() == SKIP_TOKEN:
                self.outcomes.append(Outcome.SKIPPED)
                return Outcome.SKIPPED

            clean_reply = reply.strip()

            # Step 11: Preview mode
            if not self.settings.auto_send:
                preview = Preview(
                    connection_id=conn_id,
                    chat_id=chat_id,
                    chat_name=sender_name,
                    language=lang,
                    incoming=incoming_desc,
                    reply=clean_reply,
                )
                self.preview_sink(preview)
                self._append_preview_log(preview)
                self.outcomes.append(Outcome.PREVIEWED)
                return Outcome.PREVIEWED

            # Step 12: Auto-send mode
            if self._takeovers.get(chat_key, 0) > now:
                preview = Preview(
                    connection_id=conn_id,
                    chat_id=chat_id,
                    chat_name=sender_name,
                    language=lang,
                    incoming=incoming_desc,
                    reply=clean_reply,
                    note="owner active before send",
                )
                self.preview_sink(preview)
                self._append_preview_log(preview)
                self.outcomes.append(Outcome.OWNER_ACTIVE)
                return Outcome.OWNER_ACTIVE

            try:
                fresh_conn = await bot.get_business_connection(conn_id)
                self.connection_cache[conn_id] = fresh_conn
            except TelegramAPIError as e:
                logger.warning(f"Failed to re-fetch business connection: {e}")
                self.outcomes.append(Outcome.ERROR)
                return Outcome.ERROR

            fresh_user = fresh_conn.user.id if fresh_conn.user else None
            if fresh_user != self.settings.owner_id or not fresh_conn.is_enabled or not can_reply(fresh_conn):
                preview = Preview(
                    connection_id=conn_id,
                    chat_id=chat_id,
                    chat_name=sender_name,
                    language=lang,
                    incoming=incoming_desc,
                    reply=clean_reply,
                    note="permission denied or connection disabled",
                )
                self.preview_sink(preview)
                self._append_preview_log(preview)
                self.outcomes.append(Outcome.PERMISSION_DENIED)
                return Outcome.PERMISSION_DENIED

            chunks = split_chunks(clean_reply, 4000)
            try:
                for chunk in chunks:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=chunk,
                        business_connection_id=conn_id,
                    )
            except TelegramAPIError as e:
                logger.error(f"Failed to send reply to chat {chat_id}: {e}")
                self.outcomes.append(Outcome.ERROR)
                return Outcome.ERROR

            self.history.add(chat_key, {
                "role": "owner",
                "name": "You",
                "text": clean_reply,
                "lang": lang,
                "ts": self.clock(),
            })
            self.outcomes.append(Outcome.SENT)
            return Outcome.SENT

    def pause(self) -> None:
        self.state.set_paused(True)

    def resume(self) -> None:
        self.state.set_paused(False)
        self.state.clear_limit()
        self._takeovers.clear()

    def status_text(self) -> str:
        """Return status overview in English."""
        now = self.clock()
        mode_str = "AUTO-SEND" if self.settings.auto_send else "PREVIEW (replies are only shown in the logs)"
        paused_str = "PAUSED" if self.state.is_paused() else "RUNNING"
        limit_until = self.state.get_limit_until()
        limit_str = f"Limited until {time.ctime(limit_until)}" if limit_until > now else "None"
        chats_count = self.history.chat_count()

        return (
            f"Mode: {mode_str}\n"
            f"Status: {paused_str}\n"
            f"Rate Limit: {limit_str}\n"
            f"Tracked Chats: {chats_count}\n"
            f"Gemini Model: {self.settings.gemini_model}\n"
            f"Gemini Auth: {self.settings.gemini_auth_mode}"
        )

    def start_text(self) -> str:
        """Return owner welcome text and onboarding instructions in Uzbek."""
        mode = "AUTO-SEND (xabarlar avtomatik yuboriladi)" if self.settings.auto_send else "PREVIEW (javoblar faqat loglarda ko'rsatiladi)"
        status = "Vaqtinchalik to'xtatilgan (pauza)" if self.state.is_paused() else "Faol ishlamoqda"

        return f"""Assalomu alaykum! Bu sizning shaxsiy Telegram Business assistent botingiz (Gemini orqali).

🤖 **Bot nima qiladi?**
Telegram Business orqali shaxsiy akkauntingizga ulangan holda, boshqalar yozgan xabarlarga profilingiz (`profile.md`) asosida, sizning uslubingizda javob tayyorlaydi.

📊 **Hozirgi holat:**
- Rejim: {mode}
- Holat: {status}
- Model: {self.settings.gemini_model}
- Ulanish: {self.settings.gemini_auth_mode}

⚙️ **Akkauntga qanday ulanadi?**
1. Telegram ilovasida: *Sozlamalar (Settings) → Telegram Business → Chatbots* bo'limiga kiring (Telegram Premium kerak bo'ladi).
2. Ushbu botning username'ini kiriting va ulanishga ruxsat bering.
3. Bot qaysi chatlarni ko'rishi kerakligini belgilang.
4. "Xabarlarga javob berish" (Reply to messages) ruxsatini yoqing.

🕹 **Boshqaruv buyruqlari:**
- `/status` — Botning joriy holati va statistikasini ko'rish.
- `/pause` — Botni vaqtincha to'xtatib turish.
- `/resume` — Bot faoliyatini qayta tiklash (limit va taymerlarni ham tozalaydi).

💡 **Muhim eslatmalar:**
- Agar biror chatda o'zingiz yozsangiz, bot {self.settings.owner_takeover_minutes} daqiqa davomida u chatga aralashmaydi.
- Bot hech qachon pul, qarz, uchrashuv yoki shaxsiy xavfsizlik ma'lumotlariga rozilik bermaydi.
- Assistent yaxshiroq ishlashi uchun `profile.md` faylini to'ldirish kerak.
- Agar javoblar ma'qul kelsa, sozlamalarda `AUTO_SEND=true` qilib avtomatik yuborishni yoqishingiz mumkin.
"""


def make_gemini_client(settings: Settings) -> GeminiClient:
    """Create a configured GeminiClient instance based on Settings."""
    return GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout=settings.gemini_timeout_seconds,
        auth_label=settings.gemini_auth_mode,
    )


def build_assistant(settings: Settings, **kwargs: Any) -> Assistant:
    """Factory function to build an Assistant with default or custom client."""
    if "generator" not in kwargs:
        kwargs["generator"] = make_gemini_client(settings)
    return Assistant(settings, **kwargs)
