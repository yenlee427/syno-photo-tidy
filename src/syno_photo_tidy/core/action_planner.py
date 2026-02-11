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
        duplicates: list[FileInfo] | None = None,
        duplicates_with_reason: list[tuple[FileInfo, str]] | None = None,
    ) -> PlanResult:
        plan: list[ActionItem] = []
        duplicates = duplicates or []
        if duplicates_with_reason is None:
            duplicates_with_reason = [(item, "DUPLICATE_HASH") for item in duplicates]
        else:
            duplicates = [item for item, _ in duplicates_with_reason]
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

        for item, reason in duplicates_with_reason:
            dst_path = self._build_duplicate_destination(item.path, source_root, output_root)
            plan.append(
                ActionItem(
                    action="MOVE",
                    reason=reason,
                    src_path=item.path,
                    dst_path=dst_path,
                )
            )

        manifest_entries = self.build_manifest_entries(plan, thumbnails + duplicates)

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

    def _build_duplicate_destination(
        self, src_path: Path, source_root: Path, output_root: Path
    ) -> Path:
        try:
            relative = src_path.relative_to(source_root)
        except ValueError:
            relative = Path(src_path.name)
        return output_root / "TO_DELETE" / "DUPLICATES" / relative

    def build_manifest_entries(
        self,
        plan: list[ActionItem],
        file_infos: list[FileInfo],
    ) -> list[ManifestEntry]:
        lookup = {item.path: item for item in file_infos}
        entries: list[ManifestEntry] = []
        for entry in plan:
            file_info = lookup.get(entry.src_path)
            entries.append(
                ManifestEntry(
                    action=entry.action,
                    src_path=str(entry.src_path),
                    dst_path=str(entry.dst_path) if entry.dst_path else None,
                    status="PLANNED",
                    reason=entry.reason,
                    size_bytes=file_info.size_bytes if file_info else None,
                    resolution=file_info.resolution if file_info else None,
                    hash_md5=file_info.hash_md5 if file_info else None,
                    hash_sha256=file_info.hash_sha256 if file_info else None,
                    timestamp_locked=file_info.timestamp_locked if file_info else None,
                    timestamp_source=file_info.timestamp_source if file_info else None,
                )
            )
        return entries
