"""Configuration loader and settings dataclass for Gemini."""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dotenv import dotenv_values

SETTING_KEYS: List[str] = [
    "TELEGRAM_BOT_TOKEN",
    "OWNER_ID",
    "AUTO_SEND",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_TIMEOUT_SECONDS",
    "LIMIT_COOLDOWN_MINUTES",
    "OWNER_TAKEOVER_MINUTES",
    "HISTORY_LIMIT",
    "DATA_DIR",
    "PROFILE_PATH",
]

TRUTHY_VALUES = {"true", "1", "yes", "on"}
FALSY_VALUES = {"false", "0", "no", "off"}


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""
    bot_token: Optional[str] = field(default=None, repr=False)
    owner_id: Optional[int] = None
    auto_send: bool = False
    gemini_api_key: Optional[str] = field(default=None, repr=False)
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: int = 60
    limit_cooldown_minutes: int = 30
    owner_takeover_minutes: int = 15
    history_limit: int = 30
    data_dir: Path = Path("data")
    profile_path: Path = Path("profile.md")
    from_environment: bool = False

    @property
    def gemini_auth_mode(self) -> str:
        if not self.gemini_api_key:
            return "not configured"
        if self.from_environment:
            return "API key from environment variables"
        return "API key from .env"


def _parse_bool(val: Any, key_name: str, source_desc: str) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in TRUTHY_VALUES:
        return True
    if s in FALSY_VALUES:
        return False
    raise ConfigError(
        f"Invalid boolean value for {key_name} in {source_desc}. "
        f"Allowed values are true/false, 1/0, yes/no, on/off."
    )


def _parse_int(val: Any, key_name: str, min_val: int, source_desc: str) -> int:
    try:
        res = int(str(val).strip())
        if res < min_val:
            raise ValueError()
        return res
    except (ValueError, TypeError):
        raise ConfigError(
            f"Invalid integer value for {key_name} in {source_desc}. "
            f"Expected integer >= {min_val}."
        )


def env_file_warning(path: Union[str, Path]) -> Optional[str]:
    """Return a warning string if the .env file permissions are too open."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        st = p.stat()
        if os.name == "posix":
            if bool(st.st_mode & (stat.S_IRWXG | stat.S_IRWXO)):
                return (
                    f"Permissions for {p} are too open ({oct(st.st_mode)[-3:]}). "
                    f"Run 'chmod 600 {p}' to protect your secrets."
                )
    except OSError:
        pass
    return None


def load_settings(
    env_file: Union[str, Path] = ".env",
    *,
    require_telegram: bool = True,
    overrides: Optional[Dict[str, Any]] = None,
    source: Optional[Dict[str, Any]] = None,
) -> Settings:
    """Load settings from source dict or .env file without modifying os.environ."""
    env_path = Path(env_file)
    from_env = source is not None

    raw: Dict[str, Any] = {}
    if from_env:
        source_desc = "the environment variables"
        raw.update(source)
    else:
        source_desc = str(env_path)
        if not env_path.is_file():
            if require_telegram:
                raise ConfigError(
                    f"Configuration file {env_path} not found. "
                    "Run 'cp .env.example .env && chmod 600 .env' and fill in your settings."
                )
        else:
            raw.update(dotenv_values(env_path))

    if overrides:
        raw.update(overrides)

    base_dir = env_path.parent.resolve() if not from_env else Path.cwd().resolve()

    # 1. TELEGRAM_BOT_TOKEN
    bot_token_raw = raw.get("TELEGRAM_BOT_TOKEN")
    bot_token: Optional[str] = None
    if bot_token_raw is not None and str(bot_token_raw).strip():
        val = str(bot_token_raw).strip()
        parts = val.split(":", 1)
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1]:
            raise ConfigError(
                f"TELEGRAM_BOT_TOKEN must be in format '<numbers>:<token>' in {source_desc}."
            )
        bot_token = val
    elif require_telegram:
        raise ConfigError(
            f"Missing TELEGRAM_BOT_TOKEN in {source_desc}. "
            "Set a valid bot token from @BotFather."
        )

    # 2. OWNER_ID
    owner_id_raw = raw.get("OWNER_ID")
    owner_id: Optional[int] = None
    if owner_id_raw is not None and str(owner_id_raw).strip():
        val_str = str(owner_id_raw).strip()
        if not val_str.isdigit():
            raise ConfigError(
                f"OWNER_ID must contain digits only in {source_desc}."
            )
        owner_id = int(val_str)
    elif require_telegram:
        raise ConfigError(
            f"Missing OWNER_ID in {source_desc}. Set your Telegram user ID."
        )

    # 3. AUTO_SEND
    auto_send = False
    if "AUTO_SEND" in raw and raw["AUTO_SEND"] is not None and str(raw["AUTO_SEND"]).strip():
        auto_send = _parse_bool(raw["AUTO_SEND"], "AUTO_SEND", source_desc)

    # 4. GEMINI_API_KEY
    api_key_raw = raw.get("GEMINI_API_KEY")
    gemini_api_key: Optional[str] = None
    if api_key_raw is not None and str(api_key_raw).strip():
        key_val = str(api_key_raw).strip()
        if key_val.startswith("sk-ant-"):
            raise ConfigError(
                f"GEMINI_API_KEY in {source_desc} appears to be an Anthropic key, "
                "not a Google Gemini API key. Please obtain a key from https://aistudio.google.com"
            )
        if any(c.isspace() for c in key_val):
            raise ConfigError(
                f"Invalid GEMINI_API_KEY in {source_desc}. Token must contain no whitespace."
            )
        gemini_api_key = key_val

    # 5. GEMINI_MODEL
    model_raw = raw.get("GEMINI_MODEL")
    gemini_model = str(model_raw).strip() if model_raw and str(model_raw).strip() else "gemini-3.8-flash"

    # 6. GEMINI_TIMEOUT_SECONDS
    timeout = 60
    if "GEMINI_TIMEOUT_SECONDS" in raw and raw["GEMINI_TIMEOUT_SECONDS"] is not None and str(raw["GEMINI_TIMEOUT_SECONDS"]).strip():
        timeout = _parse_int(raw["GEMINI_TIMEOUT_SECONDS"], "GEMINI_TIMEOUT_SECONDS", 1, source_desc)

    # 7. LIMIT_COOLDOWN_MINUTES
    cooldown = 30
    if "LIMIT_COOLDOWN_MINUTES" in raw and raw["LIMIT_COOLDOWN_MINUTES"] is not None and str(raw["LIMIT_COOLDOWN_MINUTES"]).strip():
        cooldown = _parse_int(raw["LIMIT_COOLDOWN_MINUTES"], "LIMIT_COOLDOWN_MINUTES", 1, source_desc)

    # 8. OWNER_TAKEOVER_MINUTES
    takeover = 15
    if "OWNER_TAKEOVER_MINUTES" in raw and raw["OWNER_TAKEOVER_MINUTES"] is not None and str(raw["OWNER_TAKEOVER_MINUTES"]).strip():
        takeover = _parse_int(raw["OWNER_TAKEOVER_MINUTES"], "OWNER_TAKEOVER_MINUTES", 0, source_desc)

    # 9. HISTORY_LIMIT
    history_lim = 30
    if "HISTORY_LIMIT" in raw and raw["HISTORY_LIMIT"] is not None and str(raw["HISTORY_LIMIT"]).strip():
        history_lim = _parse_int(raw["HISTORY_LIMIT"], "HISTORY_LIMIT", 1, source_desc)

    # 10. DATA_DIR
    data_dir_raw = raw.get("DATA_DIR")
    if data_dir_raw and str(data_dir_raw).strip():
        data_dir = Path(str(data_dir_raw).strip())
        if not data_dir.is_absolute():
            data_dir = (base_dir / data_dir).resolve()
    else:
        data_dir = (base_dir / "data").resolve()

    # 11. PROFILE_PATH
    profile_raw = raw.get("PROFILE_PATH")
    if profile_raw and str(profile_raw).strip():
        profile_path = Path(str(profile_raw).strip())
        if not profile_path.is_absolute():
            profile_path = (base_dir / profile_path).resolve()
    else:
        profile_path = (base_dir / "profile.md").resolve()

    return Settings(
        bot_token=bot_token,
        owner_id=owner_id,
        auto_send=auto_send,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        gemini_timeout_seconds=timeout,
        limit_cooldown_minutes=cooldown,
        owner_takeover_minutes=takeover,
        history_limit=history_lim,
        data_dir=data_dir,
        profile_path=profile_path,
        from_environment=from_env,
    )
