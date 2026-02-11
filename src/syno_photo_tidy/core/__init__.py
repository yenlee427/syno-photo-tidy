"""核心流程模組。"""

from .action_planner import ActionPlanner
from .archiver import Archiver
from .exact_deduper import ExactDeduper
from .executor import PlanExecutor
from .manifest import (
    ManifestContext,
    ManifestWriter,
    append_manifest_entries,
    read_manifest_records,
)
from .renamer import Renamer
from .rollback import RollbackRunner
from .scanner import FileScanner
from .thumbnail_detector import ThumbnailDetector
from .visual_deduper import VisualDeduper

__all__ = [
    "ActionPlanner",
    "Archiver",
    "ExactDeduper",
    "FileScanner",
    "PlanExecutor",
    "ManifestContext",
    "ManifestWriter",
    "append_manifest_entries",
    "Renamer",
    "RollbackRunner",
    "ThumbnailDetector",
    "VisualDeduper",
    "read_manifest_records",
]
