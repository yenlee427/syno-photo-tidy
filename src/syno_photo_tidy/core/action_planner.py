"""Dry-run 行動計畫產生器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..config import ConfigManager
from ..models import ActionItem, FileInfo, ManifestEntry
from ..utils.logger import get_logger


@dataclass
class PlanResult:
    plan: List[ActionItem]
    manifest_entries: List[ManifestEntry]


class ActionPlanner:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.config = config
        self.logger = logger or get_logger(self.__class__.__name__)

    def generate_plan(
        self,
        keepers: list[FileInfo],
        thumbnails: list[FileInfo],
        source_root: Path,
        output_root: Path,
    ) -> PlanResult:
        plan: list[ActionItem] = []
        for item in thumbnails:
            dst_path = self._build_thumbnail_destination(item.path, source_root, output_root)
            plan.append(
                ActionItem(
                    action="MOVE",
                    reason="THUMBNAIL",
                    src_path=item.path,
                    dst_path=dst_path,
                )
            )

        manifest_entries = [
            ManifestEntry(
                action=entry.action,
                src_path=str(entry.src_path),
                dst_path=str(entry.dst_path) if entry.dst_path else None,
                status="PLANNED",
                reason=entry.reason,
            )
            for entry in plan
        ]

        return PlanResult(plan=plan, manifest_entries=manifest_entries)

    def is_no_changes_needed(self, plan: list[ActionItem]) -> bool:
        return len(plan) == 0

    def _build_thumbnail_destination(
        self, src_path: Path, source_root: Path, output_root: Path
    ) -> Path:
        try:
            relative = src_path.relative_to(source_root)
        except ValueError:
            relative = Path(src_path.name)
        return output_root / "TO_DELETE" / "THUMBNAILS" / relative
