"""Year/month archiving plan generator."""

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
class ArchiveResult:
    plan: List[ActionItem]
    skipped: List[FileInfo]


class Archiver:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.enabled = bool(config.get("archive.enabled", True))
        self.root_folder = str(config.get("archive.root_folder", "KEEP"))
        self.unknown_folder = str(config.get("archive.unknown_folder", "unknown"))
        self.sequence_digits = int(config.get("archive.sequence_digits", 3))

    def generate_plan(
        self,
        files: Iterable[FileInfo],
        output_root: Path,
        progress_callback=None,
    ) -> ArchiveResult:
        if not self.enabled:
            return ArchiveResult(plan=[], skipped=list(files))

        plan: list[ActionItem] = []
        skipped: list[FileInfo] = []
        planned_names: dict[Path, set[str]] = {}

        processed = 0
        for item in files:
            target = self._build_target_path(item, output_root, planned_names)
            if target is None:
                skipped.append(item)
                continue
            plan.append(
                ActionItem(
                    action="ARCHIVE",
                    reason="ARCHIVE",
                    src_path=item.path,
                    dst_path=target,
                )
            )
            processed += 1
            if progress_callback is not None:
                progress_callback(processed)

        return ArchiveResult(plan=plan, skipped=skipped)

    def _build_target_path(
        self,
        item: FileInfo,
        output_root: Path,
        planned_names: dict[Path, set[str]],
    ) -> Path | None:
        year, month = self._parse_timestamp(item.timestamp_locked)
        parent = output_root / self.root_folder / year / month
        candidate = self._build_candidate(parent, item.path.name, 0)
        if self._is_same_path(candidate, item.path):
            return None

        planned = planned_names.setdefault(parent, set())
        seq = 0
        while True:
            key = os.path.normcase(candidate.name)
            if key not in planned and not (candidate.exists() and not self._is_same_path(candidate, item.path)):
                planned.add(key)
                return candidate
            seq += 1
            candidate = self._build_candidate(parent, item.path.name, seq)

    def _parse_timestamp(self, timestamp: str) -> tuple[str, str]:
        try:
            dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y"), dt.strftime("%m")
        except ValueError:
            return self.unknown_folder, self.unknown_folder

    def _build_candidate(self, parent: Path, filename: str, seq: int) -> Path:
        if seq == 0:
            name = filename
        else:
            stem = Path(filename).stem
            ext = Path(filename).suffix
            name = f"{stem}_{seq:0{self.sequence_digits}d}{ext}"
        return parent / name

    def _is_same_path(self, left: Path, right: Path) -> bool:
        return os.path.normcase(str(left)) == os.path.normcase(str(right))
