"""Exact hash-based deduplication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable, List

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

    def dedupe(
        self,
        files: Iterable[FileInfo],
        progress_callback=None,
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
                )
            else:
                for item in items:
                    processed = self._hash_item(
                        item,
                        groups,
                        keepers,
                        processed,
                        progress_callback,
                    )

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
    ) -> int:
        hashes = hash_calc.compute_hashes(
            item.path,
            algorithms=self.algorithms,
            chunk_size_kb=self.chunk_size_kb,
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
    ) -> int:
        with ThreadPoolExecutor(max_workers=self.parallel_workers) as executor:
            future_map = {
                executor.submit(self._compute_hashes, item): item for item in items
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

    def _compute_hashes(self, item: FileInfo) -> tuple[FileInfo, dict[str, str]]:
        hashes = hash_calc.compute_hashes(
            item.path,
            algorithms=self.algorithms,
            chunk_size_kb=self.chunk_size_kb,
            logger=self.logger,
        )
        return item, hashes
