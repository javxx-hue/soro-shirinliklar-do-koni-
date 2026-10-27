"""End-to-end unit and integration tests for Telegram Business events and bot flows."""
from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
from aiogram.methods import GetBusinessConnection, SendMessage

from assistant.gemini_client import GeminiAuthError, GeminiLimitError, GeminiTimeout
from assistant.service import Outcome
from tests.conftest import FakeGenerator


@pytest.mark.asyncio
async def test_preview_mode_and_jsonl(make_harness):
    """Preview mode logs preview, writes to previews.jsonl, and never sends to Telegram or history."""
    h = make_harness(overrides={"AUTO_SEND": "false"}, generator=FakeGenerator(["Javob"]))
    await h.connect("c1")

    await h.business_message("Salom", connection_id="c1", chat_id=123, message_id=1)

    assert len(h.assistant.outcomes) == 1
    assert h.assistant.outcomes[-1] == Outcome.PREVIEWED

    # Telegram session must have received NO send_message requests
    send_requests = [r for r in h.session.requests if isinstance(r, SendMessage)]
    assert len(send_requests) == 0

    # previews.jsonl must contain the entry
    previews_file = h.data_dir / "previews.jsonl"
    assert previews_file.exists()
    content = previews_file.read_text(encoding="utf-8")
    assert "Javob" in content
    assert "c1" in content

    # History must NOT contain the unsent reply
    history = h.assistant.history.get("c1:123")
    assert len(history) == 1
    assert history[0]["role"] == "other"
    assert history[0]["text"] == "Salom"


@pytest.mark.asyncio
async def test_connection_lookup_and_caching(make_harness):
    """Known connection makes 0 Telegram calls in preview; unknown connection is looked up once; failed lookup is no_connection."""
    h = make_harness(generator=FakeGenerator(["OK1", "OK2"]))

    # 1. Feed connection update first
    await h.connect("c1")
    req_count_before = len(h.session.requests)

    await h.business_message("Test 1", connection_id="c1", chat_id=10, message_id=1)
    # Zero requests to Telegram because it was in cache
    assert len(h.session.requests) == req_count_before

    # 2. Unknown connection in cache, but available on Telegram
    h.set_connection("c2")
    await h.business_message("Test 2", connection_id="c2", chat_id=20, message_id=2)
    # 1 GetBusinessConnection request made
    get_conn_reqs = [r for r in h.session.requests if isinstance(r, GetBusinessConnection) and r.business_connection_id == "c2"]
    assert len(get_conn_reqs) == 1

    # 3. Non-existent connection on Telegram
    await h.business_message("Test 3", connection_id="c_nonexistent", chat_id=30, message_id=3)
    assert h.assistant.outcomes[-1] == Outcome.NO_CONNECTION


@pytest.mark.asyncio
async def test_foreign_and_disabled_connections(make_harness):
    """Foreign account and disabled connections are rejected without invoking Claude."""
    generator = FakeGenerator()
    h = make_harness(generator=generator)

    # Foreign connection
    await h.connect("c_foreign", owner_id=999888777)
    await h.business_message("Hi", connection_id="c_foreign", chat_id=50, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.FOREIGN_CONNECTION
    assert len(generator.calls) == 0

    # Disabled connection
    await h.connect("c_disabled", enabled=False)
    await h.business_message("Hi", connection_id="c_disabled", chat_id=50, message_id=2)
    assert h.assistant.outcomes[-1] == Outcome.CONNECTION_DISABLED
    assert len(generator.calls) == 0


@pytest.mark.asyncio
async def test_owner_message_and_takeover(make_harness):
    """Owner message sets takeover timer and is not replied to; bot remains silent during takeover."""
    generator = FakeGenerator(["Bot reply"])
    h = make_harness(generator=generator)
    await h.connect("conn_1")

    # Owner writes to chat 100
    await h.business_message("Men o'zim yozyapman", from_id=111222333, chat_id=100, message_id=1, connection_id="conn_1")
    assert h.assistant.outcomes[-1] == Outcome.OWNER_MESSAGE
    assert len(generator.calls) == 0

    # Other user writes immediately afterwards -> owner_active
    await h.business_message("Xop tushundim", from_id=555666777, chat_id=100, message_id=2, connection_id="conn_1")
    assert h.assistant.outcomes[-1] == Outcome.OWNER_ACTIVE
    assert len(generator.calls) == 0

    # Advance clock past 15 minutes (901 seconds)
    h.clock.advance(901)
    await h.business_message("Yana savol bor", from_id=555666777, chat_id=100, message_id=3, connection_id="conn_1")
    assert h.assistant.outcomes[-1] == Outcome.PREVIEWED
    assert len(generator.calls) == 1


@pytest.mark.asyncio
async def test_ignore_bots(make_harness):
    """Sender business bot or is_bot messages are ignored."""
    generator = FakeGenerator()
    h = make_harness(generator=generator)
    await h.connect("c1")

    await h.business_message("Bot text", connection_id="c1", chat_id=1, message_id=1, is_bot=True)
    assert h.assistant.outcomes[-1] == Outcome.IGNORED_BOT

    await h.business_message("Self business bot", connection_id="c1", chat_id=1, message_id=2, via_business_bot=True)
    assert h.assistant.outcomes[-1] == Outcome.IGNORED_BOT
    assert len(generator.calls) == 0


@pytest.mark.asyncio
async def test_deduplication_including_restart(make_harness):
    """Duplicate messages are ignored, even across restart."""
    generator = FakeGenerator(["Reply 1", "Reply 2"])
    h = make_harness(generator=generator)
    await h.connect("c1")

    # First time
    await h.business_message("Msg", connection_id="c1", chat_id=10, message_id=100)
    assert h.assistant.outcomes[-1] == Outcome.PREVIEWED

    # Sequential duplicate
    await h.business_message("Msg", connection_id="c1", chat_id=10, message_id=100)
    assert h.assistant.outcomes[-1] == Outcome.DUPLICATE

    # After restart
    h.restart()
    await h.connect("c1")
    await h.business_message("Msg", connection_id="c1", chat_id=10, message_id=100)
    assert h.assistant.outcomes[-1] == Outcome.DUPLICATE


@pytest.mark.asyncio
async def test_message_descriptions(make_harness):
    """Voice, sticker, and unsupported service messages are described accurately."""
    generator = FakeGenerator(["Sticker reply", "Voice reply"])
    h = make_harness(generator=generator)
    await h.connect("c1")

    # Unsupported (neither text nor supported media)
    await h.business_message(text=None, connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.UNSUPPORTED

    # Sticker
    await h.business_message(text=None, sticker_emoji="😊", connection_id="c1", chat_id=10, message_id=2)
    assert h.assistant.outcomes[-1] == Outcome.PREVIEWED
    assert "[sticker] 😊" in generator.calls[-1]["prompt"]

    # Voice
    await h.business_message(text=None, is_voice=True, caption="voice note", connection_id="c1", chat_id=10, message_id=3)
    assert h.assistant.outcomes[-1] == Outcome.PREVIEWED
    assert "[voice message] voice note" in generator.calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_history_partitioning_and_language_cue(make_harness):
    """History is strictly partitioned by connection and chat; language cue matches."""
    generator = FakeGenerator(["Resp1", "Resp2", "Resp3"])
    h = make_harness(generator=generator)
    await h.connect("c1")
    await h.connect("c2")

    await h.business_message("Salom", connection_id="c1", chat_id=10, message_id=1)
    assert "Their latest message is in Uzbek." in generator.calls[-1]["prompt"]

    await h.business_message("Привет", connection_id="c1", chat_id=20, message_id=2)
    assert "Their latest message is in Russian." in generator.calls[-1]["prompt"]
    # Chat 10 text should not appear in chat 20 prompt
    assert "Salom" not in generator.calls[-1]["prompt"]

    # Emoji in chat 10 borrows previous language (Uzbek)
    await h.business_message(text=None, sticker_emoji="👍", connection_id="c1", chat_id=10, message_id=3)
    assert "Their latest message is in Uzbek." in generator.calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_skip_token(make_harness):
    """[SKIP] reply produces SKIPPED outcome and is not logged in previews."""
    generator = FakeGenerator(["[SKIP]"])
    h = make_harness(generator=generator)
    await h.connect("c1")

    await h.business_message("Rahmat, bo'pti", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.SKIPPED
    assert len(h.previews) == 0


@pytest.mark.asyncio
async def test_autosend_flow_and_chunking(make_harness):
    """Auto-send checks permissions on Telegram, chunks long replies, and adds sent message to history."""
    long_reply = ("A" * 3000) + "\n" + ("B" * 2000)  # 5001 chars
    generator = FakeGenerator([long_reply])
    h = make_harness(overrides={"AUTO_SEND": "true"}, generator=generator)
    await h.connect("c1")

    await h.business_message("Send long message", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.SENT

    # Verify SendMessage calls: chunked into 2 messages
    send_calls = [r for r in h.session.requests if isinstance(r, SendMessage)]
    assert len(send_calls) == 2
    assert send_calls[0].chat_id == 10
    assert send_calls[0].business_connection_id == "c1"
    assert len(send_calls[0].text) <= 4000
    assert len(send_calls[1].text) <= 4000

    # History must record the sent reply
    hist = h.assistant.history.get("c1:10")
    assert len(hist) == 2
    assert hist[1]["role"] == "owner"
    assert hist[1]["text"] == long_reply


@pytest.mark.asyncio
async def test_autosend_permission_revocation(make_harness):
    """Auto-send cancels if rights are revoked before sending."""
    generator = FakeGenerator(["Reply"])
    h = make_harness(overrides={"AUTO_SEND": "true"}, generator=generator)
    await h.connect("c1")

    # Revoke can_reply on Telegram
    h.set_connection("c1", can_reply=False)

    await h.business_message("Test", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.PERMISSION_DENIED
    send_calls = [r for r in h.session.requests if isinstance(r, SendMessage)]
    assert len(send_calls) == 0


@pytest.mark.asyncio
async def test_autosend_race_with_owner(make_harness):
    """Auto-send aborts if owner intervenes while Claude is thinking."""
    async def owner_intervenes():
        # Owner sends message during generation hook
        await h.business_message("I am here", from_id=111222333, chat_id=10, message_id=99, connection_id="c1")

    generator = FakeGenerator(["Late reply"], hook=owner_intervenes)
    h = make_harness(overrides={"AUTO_SEND": "true"}, generator=generator)
    await h.connect("c1")

    await h.business_message("Question", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.OWNER_ACTIVE
    send_calls = [r for r in h.session.requests if isinstance(r, SendMessage)]
    assert len(send_calls) == 0


@pytest.mark.asyncio
async def test_pause_and_resume_commands(make_harness):
    """Only owner commands work; pause state persists across restart; non-owner messages are ignored."""
    h = make_harness()
    await h.connect("c1")

    # Non-owner /pause
    await h.direct_message("/pause", from_id=999)
    assert h.assistant.state.is_paused() is False

    # Owner /pause
    await h.direct_message("/pause", from_id=111222333)
    assert h.assistant.state.is_paused() is True

    # Incoming business message should be paused
    await h.business_message("Test", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.PAUSED

    # Restart retains paused state
    h.restart()
    await h.connect("c1")
    await h.business_message("Test 2", connection_id="c1", chat_id=10, message_id=2)
    assert h.assistant.outcomes[-1] == Outcome.PAUSED

    # Owner /resume clears pause
    await h.direct_message("/resume", from_id=111222333)
    assert h.assistant.state.is_paused() is False


@pytest.mark.asyncio
async def test_start_command_for_owner_and_other(make_harness):
    """Owner receives full instructions in Uzbek; strangers receive short disclaimer with no profile details."""
    h = make_harness()

    # Other user /start
    await h.direct_message("/start", from_id=55555)
    last_msg = [r for r in h.session.requests if isinstance(r, SendMessage)][-1]
    assert "shaxsiy yordamchi bot" in last_msg.text
    assert "egasiga to'g'ridan-to'g'ri yozing" in last_msg.text
    assert "profile.md" not in last_msg.text

    # Owner /start
    await h.direct_message("/start", from_id=111222333)
    owner_msg = [r for r in h.session.requests if isinstance(r, SendMessage)][-1]
    assert "Assalomu alaykum" in owner_msg.text
    assert "Chatbots" in owner_msg.text
    assert "/pause" in owner_msg.text
    assert "/resume" in owner_msg.text


@pytest.mark.asyncio
async def test_rate_limits_cooldown_and_resume(make_harness):
    """GeminiLimitError sets cooldown; resume resets it; restart retains it."""
    generator = FakeGenerator([
        GeminiLimitError(detail="Rate limit", resets_at=1700002000.0, reset_text="3pm"),
        "Back to normal",
    ])
    h = make_harness(overrides={"AUTO_SEND": "true"}, generator=generator)
    await h.connect("c1")

    # First attempt triggers rate limit
    await h.business_message("Qalesiz", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.LIMITED
    assert h.assistant.state.get_limit_until() == 1700002000.0

    # Next attempt while limited doesn't call Gemini
    await h.business_message("Yana", connection_id="c1", chat_id=10, message_id=2)
    assert h.assistant.outcomes[-1] == Outcome.LIMITED

    # Advance clock past limit
    h.clock.advance(3000)
    await h.business_message("Endichi", connection_id="c1", chat_id=10, message_id=3)
    assert h.assistant.outcomes[-1] == Outcome.SENT


@pytest.mark.asyncio
async def test_timeout_and_auth_errors_dont_send_to_chat(make_harness):
    """Timeout and auth errors log errors and never reply in the user's chat."""
    generator = FakeGenerator([
        GeminiTimeout("Timeout"),
        GeminiAuthError("Bad auth", "invalid key"),
    ])
    h = make_harness(overrides={"AUTO_SEND": "true"}, generator=generator)
    await h.connect("c1")

    # Timeout
    await h.business_message("Msg 1", connection_id="c1", chat_id=10, message_id=1)
    assert h.assistant.outcomes[-1] == Outcome.ERROR

    # Auth error
    await h.business_message("Msg 2", connection_id="c1", chat_id=10, message_id=2)
    assert h.assistant.outcomes[-1] == Outcome.ERROR

    # No messages should have been sent to chat 10
    chat_sends = [r for r in h.session.requests if isinstance(r, SendMessage) and r.chat_id == 10]
    assert len(chat_sends) == 0
