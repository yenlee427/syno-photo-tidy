"""Exact hash-based deduplication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import threading
import time
from typing import Callable, Iterable, List, Optional

from ..config import ConfigManager
from ..models import FileInfo
from ..utils import hash_calc
from ..utils.logger import get_logger


@dataclass
class DedupeGroup:
    hash_value: str
    keeper: FileInfo
    duplicates: List[FileInfo]


@dataclass
class DedupeResult:
    keepers: List[FileInfo]
    duplicates: List[FileInfo]
    groups: List[DedupeGroup]


class ExactDeduper:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.algorithms = self._load_algorithms(config)
        self.chunk_size_kb = int(config.get("hash.chunk_size_kb", 1024))
        self.parallel_workers = int(config.get("hash.parallel_workers", 1))
        self.progress_bytes_threshold = int(config.get("progress.bytes_update_threshold", 1048576))
        self.progress_emit_interval_sec = float(config.get("progress.ui_update_interval_ms", 250)) / 1000.0

    def dedupe(
        self,
        files: Iterable[FileInfo],
        progress_callback=None,
        bytes_progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> DedupeResult:
        groups: dict[str, List[FileInfo]] = {}
        keepers: List[FileInfo] = []
        duplicates: List[FileInfo] = []
        dedupe_groups: List[DedupeGroup] = []

        size_groups: dict[int, List[FileInfo]] = {}
        for item in files:
            if item.file_type == "OTHER":
                keepers.append(item)
                continue
            size_groups.setdefault(item.size_bytes, []).append(item)

        processed = 0
        hash_total_bytes = sum(
            item.size_bytes
            for items in size_groups.values()
            if len(items) > 1
            for item in items
        )
        aggregator = _HashProgressAggregator(
            total_bytes=max(0, hash_total_bytes),
            callback=bytes_progress_callback,
            bytes_threshold=self.progress_bytes_threshold,
            emit_interval_sec=self.progress_emit_interval_sec,
        )
        for items in size_groups.values():
            if len(items) == 1:
                keepers.extend(items)
                continue
            if self.parallel_workers > 1:
                processed = self._hash_group_parallel(
                    items,
                    groups,
                    keepers,
                    processed,
                    progress_callback,
                    aggregator,
                )
            else:
                for item in items:
                    processed = self._hash_item(
                        item,
                        groups,
                        keepers,
                        processed,
                        progress_callback,
                        aggregator,
                    )

        aggregator.flush()

        for hash_value, items in groups.items():
            if len(items) == 1:
                keepers.extend(items)
                continue

            keeper = self._select_keeper(items)
            duplicates_in_group = [item for item in items if item is not keeper]
            keepers.append(keeper)
            duplicates.extend(duplicates_in_group)
            dedupe_groups.append(
                DedupeGroup(
                    hash_value=hash_value,
                    keeper=keeper,
                    duplicates=duplicates_in_group,
                )
            )

        return DedupeResult(keepers=keepers, duplicates=duplicates, groups=dedupe_groups)

    def _load_algorithms(self, config: ConfigManager) -> List[str]:
        algorithms = config.get("hash.algorithms", ["sha256", "md5"])
        if isinstance(algorithms, list):
            return [str(algo).lower() for algo in algorithms if str(algo).strip()]
        return ["sha256", "md5"]

    def _select_keeper(self, items: List[FileInfo]) -> FileInfo:
        def score(item: FileInfo) -> tuple[int, int, str]:
            if item.resolution:
                area = item.resolution[0] * item.resolution[1]
            else:
                area = 0
            return (-area, -item.size_bytes, str(item.path))

        return sorted(items, key=score)[0]

    def _build_hash_key(self, item: FileInfo) -> str | None:
        if item.hash_sha256 and item.hash_md5:
            return f"{item.size_bytes}:{item.hash_sha256}:{item.hash_md5}"
        if item.hash_sha256:
            return f"{item.size_bytes}:{item.hash_sha256}"
        if item.hash_md5:
            return f"{item.size_bytes}:{item.hash_md5}"
        return None

    def _hash_item(
        self,
        item: FileInfo,
        groups: dict[str, List[FileInfo]],
        keepers: List[FileInfo],
        processed: int,
        progress_callback,
        aggregator: "_HashProgressAggregator",
    ) -> int:
        previous_bytes = 0

        def on_hash_progress(bytes_read: int, _total_size: int) -> None:
            nonlocal previous_bytes
            delta = max(0, bytes_read - previous_bytes)
            previous_bytes = bytes_read
            aggregator.add(delta)

        hashes = hash_calc.compute_hashes(
            item.path,
            algorithms=self.algorithms,
            chunk_size_kb=self.chunk_size_kb,
            progress_callback=on_hash_progress,
            logger=self.logger,
        )
        item.hash_md5 = hashes.get("md5")
        item.hash_sha256 = hashes.get("sha256")
        hash_key = self._build_hash_key(item)
        if not hash_key:
            keepers.append(item)
            return processed
        groups.setdefault(hash_key, []).append(item)
        processed += 1
        if progress_callback is not None:
            progress_callback(processed)
        return processed

    def _hash_group_parallel(
        self,
        items: list[FileInfo],
        groups: dict[str, List[FileInfo]],
        keepers: List[FileInfo],
        processed: int,
        progress_callback,
        aggregator: "_HashProgressAggregator",
    ) -> int:
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            future_map = {
                executor.submit(self._compute_hashes, item, aggregator): item for item in items
            }
            for future in as_completed(future_map):
                item, hashes = future.result()
                item.hash_md5 = hashes.get("md5")
                item.hash_sha256 = hashes.get("sha256")
                hash_key = self._build_hash_key(item)
                if not hash_key:
                    keepers.append(item)
                    continue
                groups.setdefault(hash_key, []).append(item)
                processed += 1
                if progress_callback is not None:
                    progress_callback(processed)
        return processed

    def _compute_hashes(
        self,
        item: FileInfo,
        aggregator: "_HashProgressAggregator",
    ) -> tuple[FileInfo, dict[str, str]]:
        previous_bytes = 0

        def on_hash_progress(bytes_read: int, _total_size: int) -> None:
            nonlocal previous_bytes
            delta = max(0, bytes_read - previous_bytes)
            previous_bytes = bytes_read
            aggregator.add(delta)

        hashes = hash_calc.compute_hashes(
            item.path,
            algorithms=self.algorithms,
            chunk_size_kb=self.chunk_size_kb,
            progress_callback=on_hash_progress,
            logger=self.logger,
        )
        return item, hashes


class _HashProgressAggregator:
    def __init__(
        self,
        *,
        total_bytes: int,
        callback: Optional[Callable[[int, int], None]],
        bytes_threshold: int,
        emit_interval_sec: float,
    ) -> None:
        self.total_bytes = max(0, total_bytes)
        self.callback = callback
        self.bytes_threshold = max(1, bytes_threshold)
        self.emit_interval_sec = max(0.1, emit_interval_sec)
        self._processed_bytes = 0
        self._last_emitted_bytes = 0
        self._last_emitted_time = time.time()
        self._lock = threading.Lock()

    def add(self, delta_bytes: int) -> None:
        if self.callback is None or delta_bytes <= 0:
            return
        with self._lock:
            self._processed_bytes += delta_bytes
            now = time.time()
            bytes_since_emit = self._processed_bytes - self._last_emitted_bytes
            if bytes_since_emit >= self.bytes_threshold or (now - self._last_emitted_time) >= self.emit_interval_sec:
                self.callback(self._processed_bytes, self.total_bytes)
                self._last_emitted_bytes = self._processed_bytes
                self._last_emitted_time = now

    def flush(self) -> None:
        if self.callback is None:
            return
        with self._lock:
            if self._processed_bytes != self._last_emitted_bytes:
                self.callback(self._processed_bytes, self.total_bytes)
                self._last_emitted_bytes = self._processed_bytes
                self._last_emitted_time = time.time()
