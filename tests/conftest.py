"""Pytest configuration and testing harnesses."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Union

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import GetBusinessConnection, GetMe, SendMessage
from aiogram.methods.base import Response, TelegramMethod
from aiogram.types import BusinessConnection, Chat, Message, Update, User

from assistant.config import Settings
from assistant.handlers import build_router
from assistant.service import Assistant, Preview


class RecordingSession(BaseSession):
    """Fake Telegram bot session recording all sent requests."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: List[TelegramMethod[Any]] = []
        self.connections: Dict[str, BusinessConnection] = {}
        self._next_msg_id = 1000

    async def close(self) -> None:
        pass

    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[Any],
        timeout: Optional[int] = None,
    ) -> Any:
        self.requests.append(method)

        if isinstance(method, GetMe):
            return User(id=999999, is_bot=True, first_name="TestBot", username="test_assistant_bot")

        if isinstance(method, GetBusinessConnection):
            conn = self.connections.get(method.business_connection_id)
            if conn is not None:
                return conn
            raise TelegramBadRequest(method=method, message="Business connection not found")

        if isinstance(method, SendMessage):
            self._next_msg_id += 1
            return Message(
                message_id=self._next_msg_id,
                date=datetime.now(),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )

        return True

    async def stream_content(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        raise AssertionError("stream_content should not be called in tests")
        yield b""


class FakeGenerator:
    """Mock generator returning canned responses or raising canned exceptions."""

    def __init__(
        self,
        responses: Optional[List[Union[str, Exception]]] = None,
        hook: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.responses: List[Union[str, Exception]] = list(responses or ["Default test reply"])
        self.hook = hook
        self.calls: List[Dict[str, str]] = []

    async def run(self, prompt: str, system_prompt: str) -> str:
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt})
        if self.hook:
            res = self.hook()
            if asyncio.iscoroutine(res):
                await res

        if not self.responses:
            return "OK"
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def generate(self, prompt: str, system_prompt: str) -> str:
        return await self.run(prompt, system_prompt)


class Clock:
    """Controllable clock for deterministic time manipulation."""

    def __init__(self, start: float = 100000.0) -> None:
        self.current = start

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class Harness:
    """Integrated test harness with real Dispatcher, Fake Session, and Mock Generator."""

    def __init__(
        self,
        tmp_path: Path,
        overrides: Optional[Dict[str, Any]] = None,
        generator: Optional[FakeGenerator] = None,
    ) -> None:
        self.tmp_path = tmp_path
        self.data_dir = tmp_path / "data"
        self.profile_path = tmp_path / "profile.md"
        self.profile_path.write_text("Name: Test Owner\nStyle: casual", encoding="utf-8")

        opts: Dict[str, Any] = {
            "TELEGRAM_BOT_TOKEN": "123456789:ABCDEF1234567890",
            "OWNER_ID": "111222333",
            "AUTO_SEND": "false",
            "DATA_DIR": str(self.data_dir),
            "PROFILE_PATH": str(self.profile_path),
            "OWNER_TAKEOVER_MINUTES": "15",
            "LIMIT_COOLDOWN_MINUTES": "30",
        }
        if overrides:
            opts.update(overrides)

        self.clock = Clock(1700000000.0)
        self.generator = generator or FakeGenerator()
        self.previews: List[Preview] = []

        self.session = RecordingSession()
        self.bot = Bot(token=opts["TELEGRAM_BOT_TOKEN"], session=self.session)

        from assistant.config import load_settings
        self.settings = load_settings(source=opts)
        self.assistant = Assistant(
            self.settings,
            self.generator,
            clock=self.clock,
            preview_sink=self.previews.append,
        )

        self.dp = Dispatcher()
        self.dp.include_router(build_router(self.assistant))

    def restart(self, overrides: Optional[Dict[str, Any]] = None) -> None:
        """Simulate a bot restart with the same persistent data directory."""
        from assistant.config import load_settings
        opts = {
            "TELEGRAM_BOT_TOKEN": self.settings.bot_token,
            "OWNER_ID": str(self.settings.owner_id),
            "AUTO_SEND": "true" if self.settings.auto_send else "false",
            "DATA_DIR": str(self.data_dir),
            "PROFILE_PATH": str(self.profile_path),
            "OWNER_TAKEOVER_MINUTES": str(self.settings.owner_takeover_minutes),
            "LIMIT_COOLDOWN_MINUTES": str(self.settings.limit_cooldown_minutes),
        }
        if overrides:
            opts.update(overrides)
        self.settings = load_settings(source=opts)
        self.assistant = Assistant(
            self.settings,
            self.generator,
            clock=self.clock,
            preview_sink=self.previews.append,
        )
        self.dp = Dispatcher()
        self.dp.include_router(build_router(self.assistant))

    def set_connection(
        self,
        connection_id: str = "conn_1",
        owner_id: Optional[int] = 111222333,
        enabled: bool = True,
        can_reply: bool = True,
    ) -> BusinessConnection:
        """Register or update a business connection in the mock session without sending update."""
        raw_payload = {
            "id": connection_id,
            "user": {
                "id": owner_id or 111222333,
                "is_bot": False,
                "first_name": "Owner",
            },
            "user_chat_id": owner_id or 111222333,
            "date": int(self.clock()),
            "can_reply": can_reply,
            "is_enabled": enabled,
            "rights": {
                "can_reply": can_reply,
            },
        }
        conn = BusinessConnection.model_validate(raw_payload)
        self.session.connections[connection_id] = conn
        return conn

    async def connect(
        self,
        connection_id: str = "conn_1",
        owner_id: Optional[int] = 111222333,
        enabled: bool = True,
        can_reply: bool = True,
    ) -> None:
        """Feed a business_connection update into Dispatcher."""
        conn = self.set_connection(
            connection_id=connection_id,
            owner_id=owner_id,
            enabled=enabled,
            can_reply=can_reply,
        )
        update_dict = {
            "update_id": 1,
            "business_connection": conn.model_dump(),
        }
        update = Update.model_validate(update_dict, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)

    async def business_message(
        self,
        text: Optional[str] = "Salom",
        *,
        from_id: int = 555666777,
        chat_id: int = 555666777,
        message_id: int = 1,
        connection_id: str = "conn_1",
        is_bot: bool = False,
        via_business_bot: bool = False,
        caption: Optional[str] = None,
        sticker_emoji: Optional[str] = None,
        is_voice: bool = False,
    ) -> None:
        """Feed a business_message update into Dispatcher."""
        msg_dict: Dict[str, Any] = {
            "message_id": message_id,
            "date": int(self.clock()),
            "chat": {"id": chat_id, "type": "private", "first_name": "Friend"},
            "from": {"id": from_id, "is_bot": is_bot, "first_name": "Friend"},
            "business_connection_id": connection_id,
        }
        if text is not None:
            msg_dict["text"] = text
        if caption is not None:
            msg_dict["caption"] = caption
        if sticker_emoji is not None:
            msg_dict["sticker"] = {
                "file_id": "stk_1",
                "file_unique_id": "u_stk_1",
                "type": "regular",
                "width": 512,
                "height": 512,
                "is_animated": False,
                "is_video": False,
                "emoji": sticker_emoji,
            }
        if is_voice:
            msg_dict["voice"] = {
                "file_id": "voc_1",
                "file_unique_id": "u_voc_1",
                "duration": 5,
            }
        if via_business_bot:
            msg_dict["sender_business_bot"] = {
                "id": 999999,
                "is_bot": True,
                "first_name": "SelfBot",
            }

        update_dict = {
            "update_id": message_id + 10,
            "business_message": msg_dict,
        }
        update = Update.model_validate(update_dict, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)

    async def direct_message(
        self,
        text: str,
        *,
        from_id: int = 111222333,
        chat_id: Optional[int] = None,
        message_id: int = 99,
    ) -> None:
        """Feed a direct private message to the bot into Dispatcher."""
        c_id = chat_id or from_id
        entities = []
        if text.startswith("/"):
            parts = text.split()
            cmd_len = len(parts[0])
            entities.append({"type": "bot_command", "offset": 0, "length": cmd_len})

        msg_dict: Dict[str, Any] = {
            "message_id": message_id,
            "date": int(self.clock()),
            "chat": {"id": c_id, "type": "private", "first_name": "DirectUser"},
            "from": {"id": from_id, "is_bot": False, "first_name": "DirectUser"},
            "text": text,
            "entities": entities,
        }
        update_dict = {
            "update_id": message_id + 500,
            "message": msg_dict,
        }
        update = Update.model_validate(update_dict, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)


@pytest.fixture
def make_harness(tmp_path: Path) -> Callable[..., Harness]:
    def _create(overrides: Optional[Dict[str, Any]] = None, generator: Optional[FakeGenerator] = None) -> Harness:
        return Harness(tmp_path=tmp_path, overrides=overrides, generator=generator)
    return _create
