# Task 12 Brief: Gemini AI "Shirinlik Somelyesi" (AI Consultant)

## Goal
Implement the Gemini AI sweet consultant in `services/gemini.py` and `handlers/ai_consultant.py`. Ground the AI strictly with products from the database so it never hallucinates out-of-stock or non-existent items, and provide robust heuristic fallback if API key is not configured or network fails.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `ai_consultant_router`)
- Create: `services/gemini.py`
- Create: `handlers/ai_consultant.py`
- Create: `tests/test_ai_consultant.py`

## Requirements
1. In `services/gemini.py`:
   - `async def get_sweet_recommendation(user_prompt: str, available_products: list[dict], user_lang: str = "uz", api_key: str = "", model_name: str = "gemini-2.5-flash") -> str`:
     * If `api_key` is provided:
       - Uses `from google import genai` (`client = genai.Client(api_key=api_key)`).
       - Prompts model with strict grounding system instructions containing all available products (name, description, weight, price in uz/ru).
       - Returns the generated appetizing recommendation.
     * If `api_key` is missing or Google API call fails (timeout/quota/network error):
       - Falls back to `fallback_sweet_recommendation(user_prompt, available_products, user_lang)` which analyzes keywords (e.g. "tort", "shokolad", "meva", "yengil", "bayram", "kapkeyk") and generates a helpful, localized recommendation based on actual products.
2. In `handlers/ai_consultant.py`:
   - Define `ai_consultant_router = Router(name="ai_consultant")`.
   - `class AIConsultantFSM(StatesGroup)`:
     - `waiting_for_query = State()`
   - Trigger: reply button `.*Shirinlik.*(AI).*` / `.*Сомелье.*(AI).*` or command `/ai` or callback `open_ai_consultant`.
   - Greets user warmly and sets state to `waiting_for_query` with `cancel_kb(lang)`.
   - On message in `waiting_for_query`:
     - Checks if user pressed cancel button -> resets state and restores `main_menu_kb`.
     - Otherwise shows typing action (`await bot.send_chat_action(chat_id, "typing")`).
     - Loads available products via `crud.get_all_available_products(db)`.
     - Generates response via `get_sweet_recommendation`.
     - Sends response with inline keyboard having `[ 🍰 Vitrinani ko'rish ]` (`open_catalog`) and `[ ⬅️ Bosh menyu ]` (`to_main_menu`).
3. In `tests/test_ai_consultant.py`:
   - Unit tests covering:
     * Grounded prompt formatting with database products.
     * Heuristic fallback when API key is empty.
     * Heuristic fallback when Gemini API raises an exception.
     * AI consultant FSM interaction (entering state, typing query, receiving answer, cancelling).
4. TDD:
   - Write tests first and verify failure.
   - Implement `services/gemini.py` and `handlers/ai_consultant.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_ai_consultant.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add services/gemini.py handlers/ai_consultant.py tests/test_ai_consultant.py handlers/__init__.py` with message `feat: implement grounded Gemini AI sweet sommelier consultant`.
