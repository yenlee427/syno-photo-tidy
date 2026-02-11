"""設定管理器。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from . import defaults
from .schema import validate_config


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_nested(config: dict[str, Any], key: str, default: Any = None) -> Any:
    current: Any = config
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _set_nested(config: dict[str, Any], key: str, value: Any) -> None:
    current = config
    parts = key.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class ConfigManager:
    """三層設定管理：預設、使用者、執行期。"""

    def __init__(self, user_config_path: Optional[Path] = None) -> None:
        self._defaults = self._load_default_config()
        self._user = self._load_user_config(user_config_path) if user_config_path else {}
        self._runtime: dict[str, Any] = {}
        self._config = _deep_merge(self._defaults, self._user)

    def _load_default_config(self) -> dict[str, Any]:
        default_path = _project_root() / "config" / "default_config.json"
        if default_path.exists():
            return _load_json(default_path)
        return defaults.DEFAULT_CONFIG

    def _load_user_config(self, path: Path) -> dict[str, Any]:
        if path.exists():
            return _load_json(path)
        return {}

    def get(self, key: str, default: Any = None) -> Any:
        return _get_nested(self._config, key, default)

    def set(self, key: str, value: Any) -> None:
        _set_nested(self._runtime, key, value)
        self._config = _deep_merge(self._config, self._runtime)

    def validate_config(self) -> list[str]:
        return validate_config(self._config)

    def validate_dict(self, config_dict: dict[str, Any]) -> list[str]:
        return validate_config(config_dict)

    def replace_config(self, config_dict: dict[str, Any]) -> None:
        self._user = copy.deepcopy(config_dict)
        self._runtime = {}
        self._config = _deep_merge(self._defaults, self._user)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def save_user_config(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self._config, handle, ensure_ascii=False, indent=2)
