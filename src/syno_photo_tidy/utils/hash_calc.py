"""Hash calculation helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


def compute_hashes(
    path: Path,
    algorithms: Iterable[str],
    chunk_size_kb: int = 1024,
    logger=None,
) -> dict[str, str]:
    hashers: dict[str, "hashlib._Hash"] = {}
    for algo in algorithms:
        try:
            hashers[algo] = hashlib.new(algo)
        except ValueError:
            if logger is not None:
                logger.warning(f"不支援的 hash 演算法: {algo}")

    if not hashers:
        return {}

    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size_kb * 1024)
                if not chunk:
                    break
                for hasher in hashers.values():
                    hasher.update(chunk)
    except OSError as exc:
        if logger is not None:
            logger.warning(f"無法計算 hash: {path} ({exc})")
        return {}

    return {algo: hasher.hexdigest() for algo, hasher in hashers.items()}
