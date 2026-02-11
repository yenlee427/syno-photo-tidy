"""Perceptual-hash-based deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from ..config import ConfigManager
from ..models import FileInfo
from ..utils import image_utils
from ..utils.logger import get_logger


@dataclass
class VisualDedupeGroup:
    hash_value: str
    keeper: FileInfo
    duplicates: List[FileInfo]


@dataclass
class VisualDedupeResult:
    keepers: List[FileInfo]
    duplicates: List[FileInfo]
    groups: List[VisualDedupeGroup]


class VisualDeduper:
    def __init__(self, config: ConfigManager, logger=None) -> None:
        self.logger = logger or get_logger(self.__class__.__name__)
        self.threshold = int(config.get("phash.threshold", 8))

    def dedupe(self, files: Iterable[FileInfo]) -> VisualDedupeResult:
        keepers: List[FileInfo] = []
        duplicates: List[FileInfo] = []
        groups: List[VisualDedupeGroup] = []

        hashed_items: list[tuple[FileInfo, object]] = []
        for item in files:
            phash = image_utils.compute_phash(item.path, self.logger)
            if phash is None:
                keepers.append(item)
                continue
            hashed_items.append((item, phash))

        raw_groups: list[list[tuple[FileInfo, object]]] = []
        for item, phash in hashed_items:
            matched = False
            for group in raw_groups:
                if (phash - group[0][1]) <= self.threshold:
                    group.append((item, phash))
                    matched = True
                    break
            if not matched:
                raw_groups.append([(item, phash)])

        for group in raw_groups:
            items = [entry[0] for entry in group]
            if len(items) == 1:
                keepers.extend(items)
                continue

            keeper = self._select_keeper(items)
            duplicates_in_group = [item for item in items if item is not keeper]
            keepers.append(keeper)
            duplicates.extend(duplicates_in_group)
            groups.append(
                VisualDedupeGroup(
                    hash_value=str(group[0][1]),
                    keeper=keeper,
                    duplicates=duplicates_in_group,
                )
            )

        return VisualDedupeResult(keepers=keepers, duplicates=duplicates, groups=groups)

    def _select_keeper(self, items: List[FileInfo]) -> FileInfo:
        def score(item: FileInfo) -> tuple[int, int, str]:
            if item.resolution:
                area = item.resolution[0] * item.resolution[1]
            else:
                area = 0
            return (-area, -item.size_bytes, str(item.path))

        return sorted(items, key=score)[0]
