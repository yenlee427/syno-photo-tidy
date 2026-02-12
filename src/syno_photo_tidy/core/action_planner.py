"""Dry-run 行動計畫產生器。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from ..config import ConfigManager
from ..models import ActionItem, FileInfo, ManifestEntry
from ..utils.logger import get_logger
from .manifest import generate_op_id


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
        screenshot_files = sorted(
            [item for item in keepers if item.is_screenshot],
            key=lambda item: (item.timestamp_locked, item.path.name.lower(), str(item.path).lower()),
        )
        if bool(self.config.get("group_screenshots", False)):
            enable_rename = bool(self.config.get("enable_rename", False))
            for index, item in enumerate(screenshot_files, start=1):
                move_dst = self._build_screenshot_destination(item, source_root, output_root)
                move_action = ActionItem(
                    action="MOVE",
                    reason="SCREENSHOT",
                    src_path=item.path,
                    dst_path=move_dst,
                    src_file=item,
                )
                plan.append(move_action)
                if enable_rename:
                    rename_dst = move_dst.with_name(self._build_screenshot_name(item, index))
                    plan.append(
                        ActionItem(
                            action="RENAME",
                            reason="SCREENSHOT_RENAME",
                            src_path=move_dst,
                            dst_path=rename_dst,
                            src_file=item,
                        )
                    )

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

        if bool(self.config.get("move_other_to_keep", False)):
            for item in keepers:
                if item.file_type != "OTHER":
                    continue
                dst_path = self._build_other_destination(item.path, source_root, output_root)
                plan.append(
                    ActionItem(
                        action="MOVE",
                        reason="OTHER_KEEP",
                        src_path=item.path,
                        dst_path=dst_path,
                    )
                )

        manifest_entries = self.build_manifest_entries(plan, keepers + thumbnails + duplicates)

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

    def _build_other_destination(
        self,
        src_path: Path,
        source_root: Path,
        output_root: Path,
    ) -> Path:
        try:
            relative = src_path.relative_to(source_root)
        except ValueError:
            relative = Path(src_path.name)
        return output_root / "KEEP" / "OTHER" / relative

    def _build_screenshot_destination(
        self,
        file_info: FileInfo,
        source_root: Path,
        output_root: Path,
    ) -> Path:
        destination_template = str(
            self.config.get("screenshots_dest", "KEEP/Screenshots/{YYYY}-{MM}/")
        )
        year_month = self._parse_year_month(file_info.timestamp_locked)
        relative_template = destination_template.replace("{YYYY}", year_month[0]).replace("{MM}", year_month[1])
        target_dir = output_root / relative_template
        try:
            relative_name = file_info.path.relative_to(source_root).name
        except ValueError:
            relative_name = file_info.path.name
        return target_dir / relative_name

    def _build_screenshot_name(self, file_info: FileInfo, sequence: int) -> str:
        timestamp = self._parse_datetime(file_info.timestamp_locked)
        if timestamp is None:
            timestamp = datetime(1970, 1, 1, 0, 0, 0)
        return f"IMG_{timestamp:%Y%m%d_%H%M%S}_{sequence:04d}{file_info.path.suffix.lower()}"

    def _parse_year_month(self, timestamp: str) -> tuple[str, str]:
        parsed = self._parse_datetime(timestamp)
        if parsed is None:
            return "unknown", "unknown"
        return parsed.strftime("%Y"), parsed.strftime("%m")

    def _parse_datetime(self, value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def build_manifest_entries(
        self,
        plan: list[ActionItem],
        file_infos: list[FileInfo],
    ) -> list[ManifestEntry]:
        lookup = {item.path: item for item in file_infos}
        entries: list[ManifestEntry] = []
        for entry in plan:
            file_info = entry.src_file or lookup.get(entry.src_path)
            dst_path = entry.dst_path if entry.dst_path else entry.src_path
            op_id = generate_op_id(
                entry.action,
                entry.src_path,
                dst_path,
                {
                    "reason": entry.reason,
                    "new_name": entry.new_name,
                    "rename_base": entry.rename_base,
                },
            )
            entries.append(
                ManifestEntry(
                    op_id=op_id,
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
                    file_type=file_info.file_type if file_info else None,
                    is_live_pair=file_info.is_live_pair if file_info else False,
                    pair_id=file_info.pair_id if file_info else None,
                    pair_confidence=file_info.pair_confidence if file_info else None,
                    is_screenshot=file_info.is_screenshot if file_info else False,
                    screenshot_evidence=file_info.screenshot_evidence if file_info else None,
                )
            )
        return entries
