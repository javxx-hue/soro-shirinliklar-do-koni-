"""Persistent storage for conversation history, deduplication, and runtime state."""
from __future__ import annotations

import json
import os
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def ensure_private_dir(path: Union[str, Path]) -> Path:
    """Ensure directory exists and has 0700 permissions."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(p, 0o700)
        except OSError:
            pass
    return p


class JsonFile:
    """Atomically read and write JSON data to disk."""

    def __init__(self, path: Union[str, Path], default: Any = None) -> None:
        self.path = Path(path)
        self.default = default if default is not None else {}

    def read(self) -> Any:
        if not self.path.is_file():
            return self.default
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return self.default

    def write(self, data: Any) -> None:
        parent = ensure_private_dir(self.path.parent)
        # Atomic write via tempfile in same dir
        fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".tmp_", suffix=".json", text=True)
        try:
            if os.name == "posix":
                try:
                    os.chmod(tmp_path, 0o600)
                except OSError:
                    pass
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


class HistoryStore:
    """Store message history partitioned by connection_id and chat_id."""

    def __init__(self, path: Union[str, Path], limit: int = 30) -> None:
        self.limit = max(1, limit)
        self._file = JsonFile(path, default={})
        self._data: Dict[str, List[Dict[str, Any]]] = self._file.read()

    def get(self, key: str) -> List[Dict[str, Any]]:
        return list(self._data.get(key, []))

    def add(self, key: str, item: Dict[str, Any]) -> None:
        entry = {
            "role": item.get("role", "other"),
            "name": str(item.get("name", "User")),
            "text": str(item.get("text", "")),
            "lang": item.get("lang"),
            "ts": float(item.get("ts", time.time())),
        }
        chat_history = self._data.setdefault(key, [])
        chat_history.append(entry)
        if len(chat_history) > self.limit:
            self._data[key] = chat_history[-self.limit:]
        self._file.write(self._data)

    def last_language(self, key: str) -> Optional[str]:
        chat_history = self._data.get(key, [])
        for entry in reversed(chat_history):
            if entry.get("lang"):
                return entry["lang"]
        return None

    def chat_count(self) -> int:
        return len(self._data)


class SeenMessages:
    """Track processed message IDs across restarts using an OrderedDict."""

    def __init__(self, path: Union[str, Path], capacity: int = 5000) -> None:
        self.capacity = max(100, capacity)
        self._file = JsonFile(path, default=[])
        raw_list = self._file.read()
        self._seen: OrderedDict[str, bool] = OrderedDict()
        if isinstance(raw_list, list):
            for k in raw_list[-self.capacity:]:
                if isinstance(k, str):
                    self._seen[k] = True

    def first_time(self, key: str) -> bool:
        """Return True if message key has not been seen yet, recording it."""
        if key in self._seen:
            self._seen.move_to_end(key)
            return False

        self._seen[key] = True
        if len(self._seen) > self.capacity:
            self._seen.popitem(last=False)
        self._file.write(list(self._seen.keys()))
        return True


class RuntimeState:
    """Persist pause and rate limit cooldown state across restarts."""

    def __init__(self, path: Union[str, Path]) -> None:
        self._file = JsonFile(path, default={"paused": False, "limit_until": 0.0})
        self._data: Dict[str, Any] = self._file.read()
        if not isinstance(self._data, dict):
            self._data = {"paused": False, "limit_until": 0.0}

    def is_paused(self) -> bool:
        return bool(self._data.get("paused", False))

    def set_paused(self, paused: bool) -> None:
        self._data["paused"] = paused
        self._file.write(self._data)

    def get_limit_until(self) -> float:
        return float(self._data.get("limit_until", 0.0))

    def set_limit_until(self, until_ts: float) -> None:
        self._data["limit_until"] = float(until_ts)
        self._file.write(self._data)

    def clear_limit(self) -> None:
        self._data["limit_until"] = 0.0
        self._file.write(self._data)
