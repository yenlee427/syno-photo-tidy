"""Exact hash-based deduplication."""

from __future__ import annotations

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

    def dedupe(
        self,
        files: Iterable[FileInfo],
        progress_callback=None,
    ) -> DedupeResult:
        groups: dict[str, List[FileInfo]] = {}
        keepers: List[FileInfo] = []
        duplicates: List[FileInfo] = []
        dedupe_groups: List[DedupeGroup] = []

        processed = 0
        for item in files:
            hashes = hash_calc.compute_hashes(
                item.path,
                algorithms=self.algorithms,
                chunk_size_kb=self.chunk_size_kb,
                logger=self.logger,
            )
            item.hash_md5 = hashes.get("md5")
            item.hash_sha256 = hashes.get("sha256")
            hash_key = item.hash_sha256 or item.hash_md5
            if not hash_key:
                keepers.append(item)
                continue
            groups.setdefault(hash_key, []).append(item)
            processed += 1
            if progress_callback is not None:
                progress_callback(processed)

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
