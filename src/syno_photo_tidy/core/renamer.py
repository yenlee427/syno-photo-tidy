"""Synology Photos style renaming plan generator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
import re
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
        self.logger = logger or get_logger(self.__class__.__name__)
        self.enabled = bool(config.get("rename.enabled", True))
        self.pattern = str(config.get("rename.pattern", "{date}_{time}"))
        self.sequence_digits = int(config.get("rename.sequence_digits", 3))

    def generate_plan(self, files: Iterable[FileInfo], progress_callback=None) -> RenameResult:
        if not self.enabled:
            return RenameResult(plan=[], skipped=list(files))
        plan: list[ActionItem] = []
        skipped: list[FileInfo] = []
        planned_names: dict[Path, set[str]] = {}

        processed = 0
        for item in files:
            target = self._build_target_path(item, planned_names)
            if target is None:
                skipped.append(item)
                continue
            plan.append(
                ActionItem(
                    action="RENAME",
                    reason="RENAME",
                    src_path=item.path,
                    dst_path=target,
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
    ) -> Path | None:
        base = self._build_base_name(item)
        ext = item.path.suffix
        parent = item.path.parent
        planned = planned_names.setdefault(parent, set())

        candidate = self._build_candidate(parent, base, ext, 0)
        if self._is_same_path(candidate, item.path):
            return None

        seq = 0
        while True:
            key = os.path.normcase(candidate.name)
            if key not in planned and not (candidate.exists() and not self._is_same_path(candidate, item.path)):
                planned.add(key)
                return candidate
            seq += 1
            candidate = self._build_candidate(parent, base, ext, seq)

    def _build_base_name(self, item: FileInfo) -> str:
        date_str, time_str = self._parse_timestamp(item.timestamp_locked)
        tokens = {
            "date": date_str,
            "time": time_str,
            "name": item.path.stem,
        }
        try:
            base = self.pattern.format(**tokens)
        except KeyError:
            base = f"{date_str}_{time_str}"
        base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_")
        return base or "unknown"

    def _parse_timestamp(self, timestamp: str) -> tuple[str, str]:
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y%m%d"), dt.strftime("%H%M%S")
        except ValueError:
            return "unknown", "000000"

    def _build_candidate(self, parent: Path, base: str, ext: str, seq: int) -> Path:
        if seq == 0:
            name = f"{base}{ext}"
        else:
            name = f"{base}_{seq:0{self.sequence_digits}d}{ext}"
        return parent / name

    def _is_same_path(self, left: Path, right: Path) -> bool:
        return os.path.normcase(str(left)) == os.path.normcase(str(right))
