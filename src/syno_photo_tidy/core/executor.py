"""Execute planned actions safely."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..models import ActionItem, ManifestEntry
from ..utils import file_ops, path_utils
from ..utils.logger import get_logger


@dataclass
class ExecutionResult:
    executed_entries: list[ManifestEntry]
    failed_entries: list[ManifestEntry]
    cancelled: bool


class PlanExecutor:
    def __init__(self, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)

    def execute_plan(
        self,
        plan: Iterable[ActionItem],
        *,
        cancel_event=None,
    ) -> ExecutionResult:
        executed: list[ManifestEntry] = []
        failed: list[ManifestEntry] = []
        cancelled = False

        for item in plan:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break

            entry = self._execute_action(item)
            if entry.status in {"MOVED", "COPIED", "RENAMED"}:
                executed.append(entry)
            else:
                failed.append(entry)

        return ExecutionResult(
            executed_entries=executed,
            failed_entries=failed,
            cancelled=cancelled,
        )

    def _execute_action(self, item: ActionItem) -> ManifestEntry:
        if item.action == "MOVE" and item.dst_path is not None:
            return self._execute_move(item)
        if item.action == "RENAME" and item.dst_path is not None:
            return self._execute_rename(item)

        return ManifestEntry(
            action=item.action,
            src_path=str(item.src_path),
            dst_path=str(item.dst_path) if item.dst_path else None,
            status="ERROR",
            reason=item.reason,
            error_code="E-UNSUPPORTED",
            error_message="Unsupported action",
        )

    def _execute_move(self, item: ActionItem) -> ManifestEntry:
        size_bytes = _get_size_bytes(item.src_path)
        try:
            cross_drive_copy = path_utils.is_cross_drive(item.src_path, item.dst_path)
            status = file_ops.move_or_copy(
                item.src_path,
                item.dst_path,
                cross_drive_copy=cross_drive_copy,
                logger=self.logger,
            )
            if size_bytes is None:
                size_bytes = _get_size_bytes(item.dst_path)
            return ManifestEntry(
                action=item.action,
                src_path=str(item.src_path),
                dst_path=str(item.dst_path),
                status=status,
                reason=item.reason,
                size_bytes=size_bytes,
            )
        except Exception as exc:  # noqa: BLE001 - record failure for manifest
            return ManifestEntry(
                action=item.action,
                src_path=str(item.src_path),
                dst_path=str(item.dst_path),
                status="ERROR",
                reason=item.reason,
                error_code="E-EXECUTE",
                error_message=str(exc),
                size_bytes=size_bytes,
            )

    def _execute_rename(self, item: ActionItem) -> ManifestEntry:
        size_bytes = _get_size_bytes(item.src_path)
        try:
            if path_utils.is_cross_drive(item.src_path, item.dst_path):
                raise ValueError("Rename cannot cross drives")
            status = file_ops.rename_file(item.src_path, item.dst_path, logger=self.logger)
            return ManifestEntry(
                action=item.action,
                src_path=str(item.src_path),
                dst_path=str(item.dst_path),
                status=status,
                reason=item.reason,
                size_bytes=size_bytes,
            )
        except Exception as exc:  # noqa: BLE001 - record failure for manifest
            return ManifestEntry(
                action=item.action,
                src_path=str(item.src_path),
                dst_path=str(item.dst_path),
                status="ERROR",
                reason=item.reason,
                error_code="E-RENAME",
                error_message=str(exc),
                size_bytes=size_bytes,
            )


def _get_size_bytes(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None
