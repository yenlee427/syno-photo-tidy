"""可協作取消工具。"""

from __future__ import annotations

import threading


class CancelledError(Exception):
    """表示作業已由使用者取消。"""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def set(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()
