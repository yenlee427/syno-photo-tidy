"""Rollback executor for the last run."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

from ..models import ManifestEntry
from ..utils import file_ops, path_utils
from ..utils.logger import get_logger
from .manifest import append_manifest_entries, read_manifest_records


@dataclass
class RollbackResult:
    rolled_back: list[ManifestEntry]
    trashed: list[ManifestEntry]
    conflicts: list[ManifestEntry]
    skipped: list[ManifestEntry]
    failed: list[ManifestEntry]


class RollbackRunner:
    def __init__(self, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)

    def rollback(self, processed_dir: Path) -> RollbackResult:
        report_dir = processed_dir / "REPORT"
        manifest_path = report_dir / "manifest.jsonl"
        records = read_manifest_records(manifest_path)
        actions = [
            record
            for record in records
            if record.get("record_type") == "ACTION"
            and record.get("status") in {"MOVED", "COPIED", "RENAMED"}
        ]

        rollback_entries: list[ManifestEntry] = []
        for record in reversed(actions):
            rollback_entries.append(self._rollback_record(record, processed_dir))

        if rollback_entries and manifest_path.exists():
            append_manifest_entries(manifest_path, rollback_entries, logger=self.logger)

        rolled_back = [entry for entry in rollback_entries if entry.status == "ROLLED_BACK"]
        trashed = [entry for entry in rollback_entries if entry.status == "ROLLBACK_TRASHED"]
        conflicts = [entry for entry in rollback_entries if entry.status == "ROLLBACK_CONFLICT"]
        skipped = [entry for entry in rollback_entries if entry.status == "ROLLBACK_SKIPPED"]
        failed = [entry for entry in rollback_entries if entry.status == "ROLLBACK_ERROR"]

        return RollbackResult(
            rolled_back=rolled_back,
            trashed=trashed,
            conflicts=conflicts,
            skipped=skipped,
            failed=failed,
        )

    def _rollback_record(self, record: dict[str, object], processed_dir: Path) -> ManifestEntry:
        src_path = _to_path(record.get("src_path"))
        dst_path = _to_path(record.get("dst_path"))
        status = str(record.get("status"))
        reason = str(record.get("reason")) if record.get("reason") else None

        if src_path is None or dst_path is None:
            return self._build_entry("ROLLBACK_SKIPPED", dst_path, src_path, reason)
        if not dst_path.exists():
            return self._build_entry("ROLLBACK_SKIPPED", dst_path, src_path, reason)

        if status == "COPIED":
            trash_path = self._build_rollback_path(
                processed_dir / "ROLLBACK_TRASH",
                dst_path,
                processed_dir,
            )
            return self._move_to_rollback(dst_path, trash_path, "ROLLBACK_TRASHED", reason)

        if src_path.exists():
            conflict_path = self._build_rollback_path(
                processed_dir / "ROLLBACK_CONFLICTS",
                dst_path,
                processed_dir,
            )
            return self._move_to_rollback(
                dst_path,
                conflict_path,
                "ROLLBACK_CONFLICT",
                reason,
            )

        return self._move_to_rollback(dst_path, src_path, "ROLLED_BACK", reason)

    def _move_to_rollback(
        self,
        src_path: Path,
        dst_path: Path,
        status: str,
        reason: str | None,
    ) -> ManifestEntry:
        try:
            dst_path = _ensure_unique_path(dst_path)
            cross_drive_copy = path_utils.is_cross_drive(src_path, dst_path)
            file_ops.move_or_copy(
                src_path,
                dst_path,
                cross_drive_copy=cross_drive_copy,
                logger=self.logger,
            )
            return self._build_entry(status, src_path, dst_path, reason)
        except Exception as exc:  # noqa: BLE001
            entry = self._build_entry("ROLLBACK_ERROR", src_path, dst_path, reason)
            entry.error_code = "E-ROLLBACK"
            entry.error_message = str(exc)
            return entry

    def _build_entry(
        self,
        status: str,
        src_path: Path | None,
        dst_path: Path | None,
        reason: str | None,
    ) -> ManifestEntry:
        return ManifestEntry(
            action="ROLLBACK",
            src_path=str(src_path) if src_path else "",
            dst_path=str(dst_path) if dst_path else None,
            status=status,
            reason=reason,
        )

    def _build_rollback_path(
        self,
        base_dir: Path,
        original_path: Path,
        processed_dir: Path,
    ) -> Path:
        try:
            relative = original_path.relative_to(processed_dir)
        except ValueError:
            relative = Path(original_path.name)
        return base_dir / relative


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _to_path(value: object) -> Path | None:
    if not value:
        return None
    return Path(str(value))
