"""安全檔案操作（move/copy）。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..config.manager import ConfigManager

from .logger import get_logger


@dataclass
class OperationResult:
    success: bool
    error_message: Optional[str] = None
    retry_count: int = 0
    elapsed_time: float = 0.0
    value: Any = None


def safe_op(
    *,
    config,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> Callable:
    """包裝檔案操作，提供重試與指數退避。"""

    cfg_get = getattr(config, "get", None)
    if not callable(cfg_get):
        raise TypeError("config 必須提供 get(key, default) 方法")

    resolved_max = int(max_retries if max_retries is not None else cfg_get("retry.max_retries", 5))
    resolved_base = float(
        backoff_base_sec if backoff_base_sec is not None else cfg_get("retry.backoff_base_sec", 1.0)
    )
    resolved_cap = float(backoff_cap_sec if backoff_cap_sec is not None else cfg_get("retry.backoff_cap_sec", 30.0))
    resolved_exceptions = exceptions if exceptions is not None else (OSError, PermissionError)
    op_logger = logger or get_logger("FileOps")

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> OperationResult:
            start_time = time.time()
            last_error: BaseException | None = None

            for attempt in range(resolved_max + 1):
                try:
                    value = func(*args, **kwargs)
                    return OperationResult(
                        success=True,
                        retry_count=attempt,
                        elapsed_time=time.time() - start_time,
                        value=value,
                    )
                except resolved_exceptions as exc:
                    last_error = exc
                    if attempt < resolved_max:
                        wait_time = min(resolved_base * (2**attempt), resolved_cap)
                        op_logger.warning(
                            "檔案操作重試 %s/%s，等待 %.2fs：%s",
                            attempt + 1,
                            resolved_max,
                            wait_time,
                            exc,
                        )
                        time.sleep(wait_time)
                    else:
                        op_logger.error("檔案操作最終失敗（重試 %s 次）：%s", resolved_max, exc)

            return OperationResult(
                success=False,
                error_message=str(last_error) if last_error is not None else "Unknown error",
                retry_count=resolved_max,
                elapsed_time=time.time() - start_time,
            )

        return wrapper

    return decorator


def _resolve_config(config) -> ConfigManager:
    if config is None:
        return ConfigManager()
    return config


def safe_copy2(
    src_path: Path,
    dst_path: Path,
    *,
    config=None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _copy() -> None:
        shutil.copy2(src_path, dst_path)

    return _copy()


def safe_move(
    src_path: Path,
    dst_path: Path,
    *,
    config=None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _move() -> None:
        shutil.move(src_path, dst_path)

    return _move()


def safe_makedirs(
    path: Path,
    *,
    config=None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _makedirs() -> None:
        path.mkdir(parents=True, exist_ok=True)

    return _makedirs()


def safe_stat(
    path: Path,
    *,
    config=None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _stat():
        return path.stat()

    return _stat()


def move_or_copy(
    src_path: Path,
    dst_path: Path,
    *,
    cross_drive_copy: bool,
    logger=None,
) -> str:
    logger = logger or get_logger("FileOps")
    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst_path}")

    mkdir_result = safe_makedirs(dst_path.parent, logger=logger)
    if not mkdir_result.success:
        raise OSError(mkdir_result.error_message)

    if cross_drive_copy:
        copy_result = safe_copy2(src_path, dst_path, logger=logger)
        if not copy_result.success:
            raise OSError(copy_result.error_message)
        logger.info(f"COPIED: {src_path} -> {dst_path}")
        return "COPIED"

    move_result = safe_move(src_path, dst_path, logger=logger)
    if not move_result.success:
        raise OSError(move_result.error_message)
    logger.info(f"MOVED: {src_path} -> {dst_path}")
    return "MOVED"


def rename_file(src_path: Path, dst_path: Path, logger=None) -> str:
    logger = logger or get_logger("FileOps")
    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst_path}")
    if src_path.parent != dst_path.parent:
        raise ValueError("Rename must stay in the same directory")

    src_path.rename(dst_path)
    logger.info(f"RENAMED: {src_path} -> {dst_path}")
    return "RENAMED"
