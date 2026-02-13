"""Execute planned actions safely."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable, Iterable, Optional

from ..config import ConfigManager
from ..models import ActionItem, ManifestEntry, ProgressEvent, ProgressEventType
from ..utils import file_ops, path_utils
from ..utils.cancel import CancelledError, CancellationToken
from ..utils.logger import get_logger
from .manifest import generate_op_id, load_manifest_with_status, update_manifest_status


@dataclass
class ExecutionResult:
    executed_entries: list[ManifestEntry]
    failed_entries: list[ManifestEntry]
    cancelled: bool


class PlanExecutor:
    def __init__(self, logger=None, config: ConfigManager | None = None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.config = config or ConfigManager()

    def execute_plan(
        self,
        plan: Iterable[ActionItem],
        *,
        cancel_event=None,
        cancel_token: Optional[CancellationToken] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        phase_name: str = "Execute",
        manifest_path: Path | None = None,
    ) -> ExecutionResult:
        plan_items = list(plan)
        executed: list[ManifestEntry] = []
        failed: list[ManifestEntry] = []
        cancelled = False
        success_op_ids: set[str] = set()
        run_total_bytes = _sum_plan_bytes(plan_items)
        run_processed_bytes = 0

        if cancel_token is None and cancel_event is not None:
            cancel_token = _EventCancellationToken(cancel_event)

        heartbeat = HeartbeatTicker(
            interval_sec=float(self.config.get("progress.heartbeat_interval_sec", 2.0)),
            callback=lambda: self._emit(
                progress_callback,
                ProgressEvent(
                    event_type=ProgressEventType.HEARTBEAT,
                    phase_name=phase_name,
                    run_total_bytes=run_total_bytes,
                    run_processed_bytes=run_processed_bytes,
                ),
            ),
        )
        heartbeat.start()

        slow_network_threshold_mbps = float(self.config.get("progress.slow_network_threshold_mbps", 5.0))
        slow_network_check_count = int(self.config.get("progress.slow_network_check_count", 3))
        slow_network_min_bytes = int(self.config.get("progress.slow_network_min_bytes", 5242880))
        slow_network_min_elapsed_ms = int(self.config.get("progress.slow_network_min_elapsed_ms", 300))
        slow_speed_streak = 0
        slow_warning_sent = False

        if manifest_path is not None and manifest_path.exists():
            for manifest_entry in load_manifest_with_status(manifest_path):
                if manifest_entry.op_id and manifest_entry.status == "SUCCESS":
                    success_op_ids.add(manifest_entry.op_id)

        try:
            self._emit(
                progress_callback,
                ProgressEvent(
                    event_type=ProgressEventType.PHASE_START,
                    phase_name=phase_name,
                    run_total_bytes=run_total_bytes,
                    run_processed_bytes=run_processed_bytes,
                ),
            )

            for item in plan_items:
                if cancel_token is not None and cancel_token.is_cancelled():
                    cancelled = True
                    break

                op_id = self._build_op_id(item)
                if op_id in success_op_ids:
                    continue

                if manifest_path is not None:
                    update_manifest_status(manifest_path, op_id, "STARTED")

                item_size = _get_size_bytes(item.src_path) or 0
                item_started = time.time()
                self._emit(
                    progress_callback,
                    ProgressEvent(
                        event_type=ProgressEventType.FILE_START,
                        phase_name=phase_name,
                        file_path=str(item.src_path),
                        op_type=_event_op_type(item.action),
                        file_total_bytes=item_size,
                        file_processed_bytes=0,
                        run_total_bytes=run_total_bytes,
                        run_processed_bytes=run_processed_bytes,
                    ),
                )

                def on_bytes(file_processed: int, file_total: int) -> None:
                    self._emit(
                        progress_callback,
                        ProgressEvent(
                            event_type=ProgressEventType.FILE_PROGRESS,
                            phase_name=phase_name,
                            file_path=str(item.src_path),
                            op_type=_event_op_type(item.action),
                            file_total_bytes=file_total,
                            file_processed_bytes=file_processed,
                            run_total_bytes=run_total_bytes,
                            run_processed_bytes=run_processed_bytes + file_processed,
                        ),
                    )

                entry = self._execute_action(
                    item,
                    progress_callback=on_bytes,
                    cancel_token=cancel_token,
                )
                entry.op_id = op_id
                elapsed_ms = int((time.time() - item_started) * 1000)
                if manifest_path is not None:
                    update_manifest_status(
                        manifest_path,
                        op_id,
                        "SUCCESS" if entry.status in {"MOVED", "COPIED", "RENAMED"} else "FAILED",
                        error_message=entry.error_message,
                        result_status=entry.status,
                    )
                if entry.status in {"MOVED", "COPIED", "RENAMED"}:
                    executed.append(entry)
                else:
                    failed.append(entry)

                run_processed_bytes += max(0, item_size)
                speed_mbps = 0.0
                if elapsed_ms > 0 and item_size > 0:
                    speed_mbps = item_size / (elapsed_ms / 1000.0) / 1024 / 1024

                self._emit(
                    progress_callback,
                    ProgressEvent(
                        event_type=ProgressEventType.FILE_DONE,
                        phase_name=phase_name,
                        file_path=str(item.src_path),
                        op_type=_event_op_type(item.action),
                        file_total_bytes=item_size,
                        file_processed_bytes=item_size,
                        run_total_bytes=run_total_bytes,
                        run_processed_bytes=run_processed_bytes,
                        status=entry.status,
                        elapsed_ms=elapsed_ms,
                        speed_mbps=speed_mbps,
                    ),
                )

                if item_size >= slow_network_min_bytes and elapsed_ms >= slow_network_min_elapsed_ms:
                    if speed_mbps < slow_network_threshold_mbps:
                        slow_speed_streak += 1
                    else:
                        slow_speed_streak = 0
                    if not slow_warning_sent and slow_speed_streak >= slow_network_check_count:
                        self._emit(
                            progress_callback,
                            ProgressEvent(
                                event_type=ProgressEventType.SLOW_NETWORK_WARNING,
                                phase_name=phase_name,
                                run_total_bytes=run_total_bytes,
                                run_processed_bytes=run_processed_bytes,
                                evidence=(
                                    f"連續 {slow_speed_streak} 次低於 {slow_network_threshold_mbps:.1f} MB/s，"
                                    f"最近速度 {speed_mbps:.2f} MB/s"
                                ),
                            ),
                        )
                        slow_warning_sent = True
        except CancelledError:
            cancelled = True
        finally:
            heartbeat.stop()

        self._emit(
            progress_callback,
            ProgressEvent(
                event_type=ProgressEventType.PHASE_END,
                phase_name=phase_name,
                run_total_bytes=run_total_bytes,
                run_processed_bytes=run_processed_bytes,
                status="CANCELLED" if cancelled else "DONE",
            ),
        )

        return ExecutionResult(
            executed_entries=executed,
            failed_entries=failed,
            cancelled=cancelled,
        )

    def _build_op_id(self, item: ActionItem) -> str:
        dst_path = item.dst_path if item.dst_path is not None else item.src_path
        return generate_op_id(item.action, item.src_path, dst_path, {"reason": item.reason})

    def _execute_action(
        self,
        item: ActionItem,
        *,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[CancellationToken] = None,
    ) -> ManifestEntry:
        if item.action in {"MOVE", "ARCHIVE"} and item.dst_path is not None:
            return self._execute_move(item, progress_callback=progress_callback, cancel_token=cancel_token)
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

    def _execute_move(
        self,
        item: ActionItem,
        *,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        cancel_token: Optional[CancellationToken] = None,
    ) -> ManifestEntry:
        size_bytes = _get_size_bytes(item.src_path)
        try:
            cross_drive_copy = path_utils.is_cross_drive(item.src_path, item.dst_path)
            status = file_ops.move_or_copy(
                item.src_path,
                item.dst_path,
                cross_drive_copy=cross_drive_copy,
                config=self.config,
                progress_callback=progress_callback,
                cancel_token=cancel_token,
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

    def _emit(
        self,
        callback: Optional[Callable[[ProgressEvent], None]],
        event: ProgressEvent,
    ) -> None:
        if callback is None:
            return
        callback(event)

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


def _sum_plan_bytes(plan: Iterable[ActionItem]) -> int:
    total = 0
    for item in plan:
        total += max(0, _get_size_bytes(item.src_path) or 0)
    return total


def _event_op_type(action: str) -> str:
    mapping = {
        "MOVE": "move",
        "ARCHIVE": "move",
        "RENAME": "rename",
        "COPY": "copy",
    }
    return mapping.get(action, action.lower())


class _EventCancellationToken(CancellationToken):
    def __init__(self, event) -> None:
        self._event = event

    def set(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return bool(self._event.is_set())


class HeartbeatTicker:
    def __init__(self, interval_sec: float, callback: Callable[[], None]) -> None:
        self._interval_sec = max(0.2, interval_sec)
        self._callback = callback
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval_sec):
            self._callback()
