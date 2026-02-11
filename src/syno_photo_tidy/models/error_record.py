"""錯誤與警告記錄。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ErrorLevel(str, Enum):
    INFO = "I"
    RECOVERABLE = "W"
    FATAL = "E"


@dataclass
class ProcessError:
    code: str
    level: ErrorLevel
    message: str
    file_path: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "level": self.level.value,
            "message": self.message,
            "file_path": self.file_path,
        }
