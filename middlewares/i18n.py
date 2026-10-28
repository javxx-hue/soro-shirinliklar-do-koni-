"""
Internationalization (i18n) middleware and localization utilities.
Supports Uzbek ('uz') and Russian ('ru') languages with fallback and safe string interpolation.
"""
from __future__ import annotations

import json
from pathlib import Path
import string
from typing import Any, Awaitable, Callable, Dict, Optional, Union
import aiosqlite
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.crud import get_user


class SafeFormatter(string.Formatter):
    """
    Formatter that preserves unprovided placeholders instead of raising KeyError,
    and ignores extra kwargs without error.
    """

    def get_value(self, key: Any, args: tuple, kwargs: dict) -> Any:
        if isinstance(key, str):
            if key in kwargs:
                return kwargs[key]
            return f"{{{key}}}"
        return super().get_value(key, args, kwargs)

    def format_field(self, value: Any, format_spec: str) -> str:
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            return value
        try:
            return super().format_field(value, format_spec)
        except Exception:
            return str(value)


_SAFE_FORMATTER = SafeFormatter()
LOCALES_CACHE: Dict[str, Dict[str, str]] = {}


def load_locales(locales_dir: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, str]]:
    """
    Loads JSON translation dictionaries from the locales directory into memory.
    """
    global LOCALES_CACHE
    if locales_dir is None:
        locales_dir = Path(__file__).resolve().parent.parent / "locales"
    else:
        locales_dir = Path(locales_dir)

    loaded: Dict[str, Dict[str, str]] = {}
    for lang in ("uz", "ru"):
        filepath = locales_dir / f"{lang}.json"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                loaded[lang] = json.load(f)
        else:
            loaded[lang] = {}

    LOCALES_CACHE = loaded
    return loaded


def get_text(key: str, lang: Optional[str] = "uz", **kwargs: Any) -> str:
    """
    Retrieves localized text for given key and language.
    If the key is missing in the chosen language, falls back to 'uz'.
    If still missing, returns key.
    Safely substitutes {placeholder} variables from kwargs.
    """
    if not LOCALES_CACHE:
        load_locales()

    target_lang = lang if lang in ("uz", "ru") else "uz"

    # Try requested language
    raw_text = LOCALES_CACHE.get(target_lang, {}).get(key)

    # Fallback to default Uzbek if not found
    if raw_text is None and target_lang != "uz":
        raw_text = LOCALES_CACHE.get("uz", {}).get(key)

    # If key is missing entirely, return key name
    if raw_text is None:
        return key

    if not kwargs:
        return raw_text

    try:
        return _SAFE_FORMATTER.format(raw_text, **kwargs)
    except Exception:
        # Fallback to best-effort string replacement
        result = raw_text
        for k, v in kwargs.items():
            result = result.replace(f"{{{k}}}", str(v))
        return result


class I18nMiddleware(BaseMiddleware):
    """
    Aiogram middleware that determines the user's language preference
    (from the database or Telegram language_code), and injects `lang` and
    `_t` helper into the handler data context.
    """

    def __init__(
        self,
        db: Optional[aiosqlite.Connection] = None,
        default_lang: str = "uz",
    ) -> None:
        super().__init__()
        self.db = db
        self.default_lang = default_lang

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None) or data.get("event_from_user")
        lang = self.default_lang

        if from_user:
            user_id = getattr(from_user, "id", None)
            db = data.get("db") or self.db

            user_db_lang = None
            if db is not None and user_id is not None:
                try:
                    user_record = await get_user(db, user_id)
                    if user_record and user_record.get("language"):
                        user_db_lang = user_record["language"]
                except Exception:
                    user_db_lang = None

            if user_db_lang in ("uz", "ru"):
                lang = user_db_lang
            else:
                # Detect from Telegram user language_code
                tg_code = getattr(from_user, "language_code", None)
                if tg_code:
                    code_prefix = str(tg_code).lower()[:2]
                    if code_prefix == "ru":
                        lang = "ru"
                    elif code_prefix == "uz":
                        lang = "uz"
                    else:
                        lang = self.default_lang
                else:
                    lang = self.default_lang

        def _t(k: str, **kwargs: Any) -> str:
            target_lang = kwargs.pop("lang", lang)
            return get_text(k, lang=target_lang, **kwargs)

        data["lang"] = lang
        data["_t"] = _t

        return await handler(event, data)
