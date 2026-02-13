"""Hash calculation helpers."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Callable, Iterable, Optional

from .cancel import CancelledError, CancellationToken


def compute_hashes(
    path: Path,
    algorithms: Iterable[str],
    chunk_size_kb: int = 1024,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancellationToken] = None,
    bytes_update_threshold: int = 1048576,
    report_interval_sec: float = 0.1,
    return_elapsed_ms: bool = False,
    logger=None,
) -> dict[str, str] | tuple[dict[str, str], int]:
    hashers: dict[str, "hashlib._Hash"] = {}
    for algo in algorithms:
        try:
            hashers[algo] = hashlib.new(algo)
        except ValueError:
            if logger is not None:
                logger.warning(f"不支援的 hash 演算法: {algo}")

    if not hashers:
        if return_elapsed_ms:
            return {}, 0
        return {}

    total_size = 0
    try:
        total_size = path.stat().st_size
    except OSError:
        total_size = 0

    start_time = time.time()
    bytes_read = 0
    last_reported = 0
    last_report_time = start_time

    try:
        with path.open("rb") as handle:
            while True:
                if cancel_token is not None and cancel_token.is_cancelled():
                    raise CancelledError(f"已取消 hash 計算: {path}")
                chunk = handle.read(chunk_size_kb * 1024)
                if not chunk:
                    break
                bytes_read += len(chunk)
                for hasher in hashers.values():
                    hasher.update(chunk)

                if progress_callback is not None:
                    now = time.time()
                    should_report = (bytes_read - last_reported) >= bytes_update_threshold
                    if not should_report and (now - last_report_time) >= report_interval_sec:
                        should_report = True
                    if should_report:
                        progress_callback(bytes_read, total_size)
                        last_reported = bytes_read
                        last_report_time = now

        if progress_callback is not None and bytes_read != last_reported:
            progress_callback(bytes_read, total_size)
    except OSError as exc:
        if logger is not None:
            logger.warning(f"無法計算 hash: {path} ({exc})")
        if return_elapsed_ms:
            return {}, int((time.time() - start_time) * 1000)
        return {}

    result = {algo: hasher.hexdigest() for algo, hasher in hashers.items()}
    if return_elapsed_ms:
        return result, int((time.time() - start_time) * 1000)
    return result
