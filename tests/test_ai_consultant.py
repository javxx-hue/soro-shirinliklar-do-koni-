"""
Unit and integration tests for grounded Gemini AI "Shirinlik Somelyesi" sweet consultant
(services/gemini.py and handlers/ai_consultant.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message

from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from keyboards.reply import cancel_kb, main_menu_kb


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with sample categories and products."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


def fake_t(lang="uz"):
    """Helper to mock i18n translation callable."""
    return lambda key, **kwargs: get_text(key, lang=kwargs.pop("lang", lang), **kwargs)


def make_fsm_context(user_id: int = 3001, chat_id: int = 3001) -> FSMContext:
    """Creates a real FSMContext with in-memory storage."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


SAMPLE_PRODUCTS = [
    {
        "id": 1,
        "category_id": 1,
        "name_uz": "Shokoladli Trufel Torti",
        "name_ru": "Шоколадный Трюфельный Торт",
        "description_uz": "Belgiya shokoladi va nozik ganash bilan to'yingan shirinlik",
        "description_ru": "Насыщенный торт с бельгийским шоколадом и нежным ганашем",
        "price": 180000,
        "weight": "1.2 kg",
        "photo_id": "photo_1",
        "is_available": 1,
    },
    {
        "id": 2,
        "category_id": 1,
        "name_uz": "Mevali Qulupnayli Biskvit",
        "name_ru": "Клубничный Бисквитный Торт",
        "description_uz": "Yengil qaymoqli krem va yangi pishgan qulupnaylar bilan",
        "description_ru": "Легкий сливочный крем со свежей сочной клубникой",
        "price": 150000,
        "weight": "1.0 kg",
        "photo_id": "photo_2",
        "is_available": 1,
    },
    {
        "id": 3,
        "category_id": 2,
        "name_uz": "Fransuz Kapkeyklari (6 dona)",
        "name_ru": "Французские Капкейки (6 шт)",
        "description_uz": "Vanilli va karamelli nozik kapkeyklar to'plami",
        "description_ru": "Набор нежных капкейков с ванилью и карамелью",
        "price": 95000,
        "weight": "450 g",
        "photo_id": "photo_3",
        "is_available": 1,
    },
]


# ============================================================================
# 1. Router & FSM Definition Tests
# ============================================================================

def test_ai_consultant_router_and_fsm_definition():
    """Verify ai_consultant_router and AIConsultantFSM states exist and are exported."""
    from handlers.ai_consultant import ai_consultant_router, AIConsultantFSM
    from handlers import ai_consultant_router as exported_router

    assert isinstance(ai_consultant_router, Router)
    assert ai_consultant_router.name == "ai_consultant"
    assert exported_router is ai_consultant_router

    assert hasattr(AIConsultantFSM, "waiting_for_query")


# ============================================================================
# 2. Grounded System Prompt Tests
# ============================================================================

def test_grounded_system_prompt_formatting():
    """Verify strict grounding instructions and product catalog inclusion in system prompt."""
    from services.gemini import build_grounded_system_prompt

    prompt_uz = build_grounded_system_prompt(SAMPLE_PRODUCTS, user_lang="uz")
    assert "Shirinlik Somelyesi" in prompt_uz or "Somelye" in prompt_uz
    assert "Shokoladli Trufel Torti" in prompt_uz
    assert "180 000" in prompt_uz or "180000" in prompt_uz
    assert "1.2 kg" in prompt_uz
    # Strict grounding instructions
    assert "faqat" in prompt_uz.lower() or "ground" in prompt_uz.lower() or "mavjud" in prompt_uz.lower()

    prompt_ru = build_grounded_system_prompt(SAMPLE_PRODUCTS, user_lang="ru")
    assert "Шоколадный Трюфельный Торт" in prompt_ru
    assert "Французские Капкейки" in prompt_ru


# ============================================================================
# 3. Gemini API Call with Mocked Client
# ============================================================================

@pytest.mark.asyncio
async def test_get_sweet_recommendation_gemini_success():
    """Verify successful Gemini call with grounded prompt and model return."""
    from services.gemini import get_sweet_recommendation

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "🍰 Sizga ajoyib Belgiya shokoladli Trufel tortimizni tavsiya qilaman! Narxi: 180,000 so'm."
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    with patch("google.genai.Client", return_value=mock_client) as mock_client_cls:
        result = await get_sweet_recommendation(
            user_prompt="Shokoladli nima bor?",
            available_products=SAMPLE_PRODUCTS,
            user_lang="uz",
            api_key="valid_test_key",
            model_name="gemini-2.5-flash",
        )

        mock_client_cls.assert_called_once_with(api_key="valid_test_key")
        mock_client.aio.models.generate_content.assert_called_once()
        call_kwargs = mock_client.aio.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"
        assert call_kwargs["contents"] == "Shokoladli nima bor?"
        assert result == mock_response.text


# ============================================================================
# 4. Heuristic Fallback when API key is empty
# ============================================================================

@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_when_api_key_empty_uz():
    """Verify heuristic fallback triggers when api_key is empty and matches chocolate keywords in Uzbek."""
    from services.gemini import get_sweet_recommendation, fallback_sweet_recommendation

    result = await get_sweet_recommendation(
        user_prompt="Menga shokoladli shirinlik tavsiya qiling",
        available_products=SAMPLE_PRODUCTS,
        user_lang="uz",
        api_key="",
    )

    assert "Shokoladli Trufel Torti" in result
    assert "180" in result
    assert "tavsiya" in result.lower() or "somelye" in result.lower()


@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_when_api_key_empty_ru():
    """Verify heuristic fallback in Russian when api_key is empty."""
    from services.gemini import get_sweet_recommendation

    result = await get_sweet_recommendation(
        user_prompt="Посоветуйте капкейки или десерты к чаю",
        available_products=SAMPLE_PRODUCTS,
        user_lang="ru",
        api_key="",
    )

    assert "Французские Капкейки" in result or "Капкейки" in result
    assert "сум" in result or "95" in result


@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_fruit_keyword():
    """Verify keyword matching for light or fruit desserts."""
    from services.gemini import fallback_sweet_recommendation

    result = fallback_sweet_recommendation(
        user_prompt="Bolalar uchun mevali va yengil tort bormi?",
        available_products=SAMPLE_PRODUCTS,
        user_lang="uz",
    )

    assert "Mevali Qulupnayli Biskvit" in result


@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_when_no_products():
    """Verify polite message when available products list is empty."""
    from services.gemini import fallback_sweet_recommendation

    result_uz = fallback_sweet_recommendation("Tort bormi?", [], "uz")
    assert "mavjud" in result_uz.lower() or "shirinlik" in result_uz.lower()

    result_ru = fallback_sweet_recommendation("Есть торт?", [], "ru")
    assert "наличии" in result_ru.lower() or "каталог" in result_ru.lower() or "сладост" in result_ru.lower()


# ============================================================================
# 5. Heuristic Fallback when Gemini API raises an exception
# ============================================================================

@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_on_gemini_exception():
    """Verify fallback activates gracefully when Gemini client throws network/quota/auth exception."""
    from services.gemini import get_sweet_recommendation

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("Google Quota Exhausted 429"))

    with patch("google.genai.Client", return_value=mock_client):
        result = await get_sweet_recommendation(
            user_prompt="Tug'ilgan kunga shokoladli tort",
            available_products=SAMPLE_PRODUCTS,
            user_lang="uz",
            api_key="valid_key",
        )

        # Must not crash, should return heuristic recommendation
        assert "Shokoladli Trufel Torti" in result


@pytest.mark.asyncio
async def test_sweet_recommendation_fallback_on_empty_gemini_response():
    """Verify fallback activates if Gemini returns empty or whitespace-only response."""
    from services.gemini import get_sweet_recommendation

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "   "
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    with patch("google.genai.Client", return_value=mock_client):
        result = await get_sweet_recommendation(
            user_prompt="Kapkeyk bormi?",
            available_products=SAMPLE_PRODUCTS,
            user_lang="uz",
            api_key="valid_key",
        )

        assert "Kapkeyk" in result


# ============================================================================
# 6. FSM Handlers: Entry, Typing, Query, Cancellation
# ============================================================================

@pytest.mark.asyncio
async def test_open_ai_consultant_via_reply_button(memory_db):
    """Verify entering AI consultant mode sets state to waiting_for_query with cancel keyboard."""
    from handlers.ai_consultant import open_ai_consultant_message, AIConsultantFSM

    state = make_fsm_context()
    message = MagicMock()
    message.text = get_text("btn_ai_consultant", "uz")
    message.from_user = MagicMock(id=3001)
    message.answer = AsyncMock()

    await open_ai_consultant_message(message, state=state, lang="uz", _t=fake_t("uz"))

    # Assert state is now waiting_for_query
    current_state = await state.get_state()
    assert current_state == AIConsultantFSM.waiting_for_query.state

    # Assert intro message was sent with cancel_kb
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("ai_consultant_intro", "uz") in args[0]
    assert "reply_markup" in kwargs
    kb = kwargs["reply_markup"]
    assert any(btn.text == get_text("cancel_btn", "uz") for row in kb.keyboard for btn in row)


@pytest.mark.asyncio
async def test_open_ai_consultant_via_callback(memory_db):
    """Verify opening AI consultant via callback query."""
    from handlers.ai_consultant import open_ai_consultant_callback, AIConsultantFSM

    state = make_fsm_context()
    callback = MagicMock()
    callback.data = "open_ai_consultant"
    callback.from_user = MagicMock(id=3001)
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    await open_ai_consultant_callback(callback, state=state, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    current_state = await state.get_state()
    assert current_state == AIConsultantFSM.waiting_for_query.state
    callback.message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_ai_consultant_cancel_message():
    """Verify user pressing cancel button resets FSM state and restores main menu."""
    from handlers.ai_consultant import process_ai_query, AIConsultantFSM

    state = make_fsm_context()
    await state.set_state(AIConsultantFSM.waiting_for_query)

    message = MagicMock()
    message.text = get_text("cancel_btn", "uz")
    message.from_user = MagicMock(id=3001)
    message.answer = AsyncMock()

    await process_ai_query(message, state=state, lang="uz", _t=fake_t("uz"))

    # Verify state was cleared
    current_state = await state.get_state()
    assert current_state is None

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("action_cancelled", "uz") in args[0]
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_ai_consultant_query_flow(memory_db):
    """Verify user typing question generates recommendation and sends inline result keyboard."""
    from handlers.ai_consultant import process_ai_query, AIConsultantFSM
    from shop_config import Config

    # Seed products into memory_db
    cat_id = await crud.add_category(memory_db, "Tortlar", "Торты")
    await crud.add_product(
        memory_db,
        category_id=cat_id,
        name_uz="Shokoladli Trufel Torti",
        name_ru="Шоколадный Трюфель",
        description_uz="Mazali Belgiya shokoladli",
        description_ru="Вкусный шоколадный торт",
        price=180000,
        weight="1.2 kg",
        is_available=1,
    )

    state = make_fsm_context()
    await state.set_state(AIConsultantFSM.waiting_for_query)

    message = MagicMock()
    message.text = "Shokoladli tort tavsiya qiling"
    message.chat = MagicMock(id=3001)
    message.from_user = MagicMock(id=3001)
    message.bot = MagicMock()
    message.bot.send_chat_action = AsyncMock()
    message.answer = AsyncMock()

    dummy_cfg = Config(bot_token="test", gemini_api_key="")
    with patch("handlers.ai_consultant.load_config", return_value=dummy_cfg):
        await process_ai_query(
            message,
            state=state,
            db=memory_db,
            lang="uz",
            _t=fake_t("uz"),
        )

    # Check typing indicator
    message.bot.send_chat_action.assert_called_once_with(chat_id=3001, action="typing")

    # Check answer
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    reply_text = args[0]
    assert "Shokoladli Trufel Torti" in reply_text

    # Check result inline keyboard: open_catalog and to_main_menu
    kb = kwargs.get("reply_markup")
    assert kb is not None
    callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "open_catalog" in callbacks
    assert "to_main_menu" in callbacks


@pytest.mark.asyncio
async def test_ai_consultant_query_flow_with_gemini(memory_db):
    """Verify query flow end-to-end when Gemini returns response."""
    from handlers.ai_consultant import process_ai_query, AIConsultantFSM
    from shop_config import Config

    cat_id = await crud.add_category(memory_db, "Tortlar", "Торты")
    await crud.add_product(
        memory_db,
        category_id=cat_id,
        name_uz="Shokoladli Trufel Torti",
        name_ru="Шоколадный Трюфель",
        description_uz="Mazali Belgiya shokoladli",
        description_ru="Вкусный шоколадный торт",
        price=180000,
        weight="1.2 kg",
        is_available=1,
    )

    state = make_fsm_context()
    await state.set_state(AIConsultantFSM.waiting_for_query)

    message = MagicMock()
    message.text = "Qaysi tort eng shirin?"
    message.chat = MagicMock(id=3001)
    message.from_user = MagicMock(id=3001)
    message.bot = MagicMock()
    message.bot.send_chat_action = AsyncMock()
    message.answer = AsyncMock()

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "🍰 Sizga Belgiya shokoladli tortini tavsiya etaman!"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_resp)

    dummy_cfg = Config(bot_token="test", gemini_api_key="valid_key")
    with patch("handlers.ai_consultant.load_config", return_value=dummy_cfg), \
         patch("google.genai.Client", return_value=mock_client):
        await process_ai_query(
            message,
            state=state,
            db=memory_db,
            lang="uz",
            _t=fake_t("uz"),
        )

    message.answer.assert_called_once()
    assert "Belgiya shokoladli" in message.answer.call_args[0][0]



@pytest.mark.asyncio
async def test_ai_consultant_inline_open_catalog(memory_db):
    """Verify clicking [ Vitrinani ko'rish ] from recommendation clears state and opens catalog."""
    from handlers.ai_consultant import handle_ai_open_catalog, AIConsultantFSM

    state = make_fsm_context()
    await state.set_state(AIConsultantFSM.waiting_for_query)

    callback = MagicMock()
    callback.data = "open_catalog"
    callback.from_user = MagicMock(id=3001)
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    await handle_ai_open_catalog(callback, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    assert (await state.get_state()) is None
    callback.message.answer.assert_called_once()
    args, kwargs = callback.message.answer.call_args
    assert get_text("select_category", "uz") in args[0]


@pytest.mark.asyncio
async def test_ai_consultant_inline_to_main_menu():
    """Verify clicking [ Bosh menyu ] from recommendation clears state and sends main menu."""
    from handlers.ai_consultant import handle_ai_to_main_menu, AIConsultantFSM

    state = make_fsm_context()
    await state.set_state(AIConsultantFSM.waiting_for_query)

    callback = MagicMock()
    callback.data = "to_main_menu"
    callback.from_user = MagicMock(id=3001)
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    await handle_ai_to_main_menu(callback, state=state, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    assert (await state.get_state()) is None
    callback.message.answer.assert_called_once()
    args, kwargs = callback.message.answer.call_args
    assert get_text("main_menu", "uz") in args[0]
