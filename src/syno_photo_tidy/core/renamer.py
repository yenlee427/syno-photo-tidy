"""Synology Photos style renaming plan generator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Iterable, List

from ..config import ConfigManager
from ..models import ActionItem, FileInfo
from ..utils.logger import get_logger


@dataclass
class RenameResult:
    plan: List[ActionItem]
    skipped: List[FileInfo]


class Renamer:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.config = config
        self.logger = logger or get_logger(self.__class__.__name__)
        self.sequence_digits = max(4, int(config.get("rename.sequence_digits", 4)))

    def generate_plan(self, files: Iterable[FileInfo], progress_callback=None) -> RenameResult:
        items = list(files)
        enabled = bool(self.config.get("enable_rename", self.config.get("rename.enabled", False)))
        if not enabled:
            return RenameResult(plan=[], skipped=items)

        sorted_items = sorted(
            items,
            key=lambda item: (
                item.timestamp_locked,
                item.path.name.lower(),
                str(item.path).lower(),
            ),
        )

        pair_time_map: dict[str, datetime] = {}
        for item in sorted_items:
            if not item.is_live_pair or not item.pair_id:
                continue
            ts = self._parse_timestamp(item.timestamp_locked)
            if ts is None:
                continue
            current = pair_time_map.get(item.pair_id)
            if current is None or ts < current:
                pair_time_map[item.pair_id] = ts

        plan: list[ActionItem] = []
        skipped: list[FileInfo] = []
        planned_names: dict[Path, set[str]] = {}
        group_sequence: dict[str, int] = {}
        seq_counter = 1

        processed = 0
        for item in sorted_items:
            group_key = item.pair_id if item.is_live_pair and item.pair_id else f"single:{item.path}"
            if group_key not in group_sequence:
                group_sequence[group_key] = seq_counter
                seq_counter += 1

            target = self._build_target_path(
                item,
                planned_names,
                sequence=group_sequence[group_key],
                pair_timestamp=pair_time_map.get(item.pair_id or ""),
            )
            if target is None:
                skipped.append(item)
                continue
            rename_base = target.stem
            plan.append(
                ActionItem(
                    action="RENAME",
                    reason="RENAME",
                    src_path=item.path,
                    dst_path=target,
                    new_name=target.name,
                    rename_base=rename_base,
                    src_file=item,
                )
            )
            processed += 1
            if progress_callback is not None:
                progress_callback(processed)
        return RenameResult(plan=plan, skipped=skipped)

    def _build_target_path(
        self,
        item: FileInfo,
        planned_names: dict[Path, set[str]],
        *,
        sequence: int,
        pair_timestamp: datetime | None,
    ) -> Path | None:
        base = self._build_base_name(item, sequence=sequence, pair_timestamp=pair_timestamp)
        ext = item.path.suffix
        parent = item.path.parent
        planned = planned_names.setdefault(parent, set())

        candidate = parent / f"{base}{ext.lower()}"
        if self._is_same_path(candidate, item.path):
            return None
        resolved = self.resolve_name_conflict(parent, candidate.name, planned_names=planned, src_path=item.path)
        return resolved

    def _build_base_name(
        self,
        item: FileInfo,
        *,
        sequence: int,
        pair_timestamp: datetime | None,
    ) -> str:
        timestamp = pair_timestamp if pair_timestamp is not None else self._parse_timestamp(item.timestamp_locked)
        if timestamp is None:
            timestamp = datetime(1970, 1, 1, 0, 0, 0)

        prefix = "IMG"
        if item.file_type == "VIDEO" and not item.is_live_pair:
            prefix = "VID"

        return f"{prefix}_{timestamp:%Y%m%d_%H%M%S}_{sequence:0{self.sequence_digits}d}"

    def _parse_timestamp(self, timestamp: str) -> datetime | None:
        try:
            return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    def resolve_name_conflict(
        self,
        dst_dir: Path,
        filename: str,
        *,
        planned_names: set[str],
        src_path: Path,
    ) -> Path:
        base_path = dst_dir / filename
        stem = base_path.stem
        suffix = base_path.suffix

        candidate = base_path
        index = 0
        while True:
            key = os.path.normcase(candidate.name)
            exists_conflict = candidate.exists() and not self._is_same_path(candidate, src_path)
            planned_conflict = key in planned_names
            if not exists_conflict and not planned_conflict:
                planned_names.add(key)
                return candidate

            index += 1
            candidate = dst_dir / f"{stem}_{index:04d}{suffix}"

    def _is_same_path(self, left: Path, right: Path) -> bool:
        return os.path.normcase(str(left)) == os.path.normcase(str(right))
