"""核心流程模組。"""

from .action_planner import ActionPlanner
from .archiver import Archiver
from .exact_deduper import ExactDeduper
from .executor import PlanExecutor
from .manifest import (
    ManifestContext,
    ManifestWriter,
    append_manifest_entries,
    generate_op_id,
    load_manifest_with_status,
    read_manifest_records,
    update_manifest_status,
)
from .live_photo_matcher import LivePhotoMatcher
from .pipeline import Pipeline
from .renamer import Renamer
from .resume_manager import ResumeManager, ValidationResult, build_actions_from_manifest
from .rollback import RollbackRunner
from .scanner import FileScanner
from .screenshot_detector import ScreenshotDetector
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
    "generate_op_id",
    "LivePhotoMatcher",
    "load_manifest_with_status",
    "Pipeline",
    "Renamer",
    "ResumeManager",
    "RollbackRunner",
    "ScreenshotDetector",
    "ThumbnailDetector",
    "VisualDeduper",
    "read_manifest_records",
    "update_manifest_status",
    "ValidationResult",
    "build_actions_from_manifest",
]
