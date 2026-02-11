"""錯誤收集與報告工具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..models.error_record import ErrorLevel, ProcessError


@dataclass
class ErrorHandler:
    """集中管理錯誤與警告。"""

    errors: List[ProcessError] = field(default_factory=list)

    def add(self, error: ProcessError) -> None:
        self.errors.append(error)

    def add_info(self, code: str, message: str) -> None:
        self.add(ProcessError(code=code, level=ErrorLevel.INFO, message=message))

    def add_warning(self, code: str, message: str) -> None:
        self.add(ProcessError(code=code, level=ErrorLevel.RECOVERABLE, message=message))

    def add_fatal(self, code: str, message: str) -> None:
        self.add(ProcessError(code=code, level=ErrorLevel.FATAL, message=message))

    def get_by_level(self, level: ErrorLevel) -> List[ProcessError]:
        return [error for error in self.errors if error.level == level]

    def to_dicts(self) -> List[dict[str, object]]:
        return [error.to_dict() for error in self.errors]
