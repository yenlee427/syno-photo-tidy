"""執行階段進度事件模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ProgressEventType(str, Enum):
    PHASE_START = "PHASE_START"
    PHASE_END = "PHASE_END"
    FILE_START = "FILE_START"
    FILE_PROGRESS = "FILE_PROGRESS"
    FILE_DONE = "FILE_DONE"
    HEARTBEAT = "HEARTBEAT"
    SLOW_NETWORK_WARNING = "SLOW_NETWORK_WARNING"


@dataclass
class ProgressEvent:
    event_type: ProgressEventType
    timestamp: datetime = field(default_factory=datetime.now)
    phase_name: Optional[str] = None
    file_path: Optional[str] = None
    op_type: Optional[str] = None
    file_total_bytes: Optional[int] = None
    file_processed_bytes: Optional[int] = None
    run_total_bytes: Optional[int] = None
    run_processed_bytes: Optional[int] = None
    status: Optional[str] = None
    elapsed_ms: Optional[int] = None
    speed_mbps: Optional[float] = None
    evidence: Optional[str] = None
