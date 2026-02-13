"""安全檔案操作（move/copy）。"""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..config.manager import ConfigManager
from .cancel import CancelledError, CancellationToken

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
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancellationToken] = None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    size_threshold = int(cfg.get("file_ops.chunked_copy_threshold_bytes", 10 * 1024 * 1024))
    chunk_size_kb = int(cfg.get("file_ops.copy_chunk_size_kb", cfg.get("hash.chunk_size_kb", 1024)))

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _copy() -> None:
        file_size = 0
        try:
            file_size = src_path.stat().st_size
        except OSError:
            file_size = 0
        if progress_callback is not None and file_size > size_threshold:
            chunked_copy(
                src_path,
                dst_path,
                progress_callback=progress_callback,
                cancel_token=cancel_token,
                chunk_size_kb=chunk_size_kb,
            )
            shutil.copystat(src_path, dst_path)
            return
        if cancel_token is not None and cancel_token.is_cancelled():
            raise CancelledError(f"已取消複製: {src_path}")
        shutil.copy2(src_path, dst_path)
        if progress_callback is not None:
            progress_callback(file_size, file_size)

    return _copy()


def safe_move(
    src_path: Path,
    dst_path: Path,
    *,
    config=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancellationToken] = None,
    max_retries: Optional[int] = None,
    backoff_base_sec: Optional[float] = None,
    backoff_cap_sec: Optional[float] = None,
    exceptions: Optional[tuple[type[BaseException], ...]] = None,
    logger=None,
) -> OperationResult:
    cfg = _resolve_config(config)
    op_logger = logger or get_logger("FileOps")

    cross_volume = _is_cross_volume(src_path, dst_path)
    block_cross_volume_move = bool(cfg.get("file_ops.block_cross_volume_move", False))

    if cross_volume and block_cross_volume_move:
        return OperationResult(
            success=False,
            error_message="跨磁碟移動已被設定阻擋，請改用複製策略",
            value="BLOCKED",
        )

    if cross_volume:
        copy_result = safe_copy2(
            src_path,
            dst_path,
            config=cfg,
            progress_callback=progress_callback,
            cancel_token=cancel_token,
            max_retries=max_retries,
            backoff_base_sec=backoff_base_sec,
            backoff_cap_sec=backoff_cap_sec,
            exceptions=exceptions,
            logger=op_logger,
        )
        if copy_result.success:
            copy_result.value = "COPIED"
        return copy_result

    @safe_op(
        config=cfg,
        max_retries=max_retries,
        backoff_base_sec=backoff_base_sec,
        backoff_cap_sec=backoff_cap_sec,
        exceptions=exceptions,
        logger=op_logger,
    )
    def _move() -> None:
        if cancel_token is not None and cancel_token.is_cancelled():
            raise CancelledError(f"已取消搬移: {src_path}")
        shutil.move(src_path, dst_path)
        if progress_callback is not None:
            try:
                total_size = src_path.stat().st_size
            except OSError:
                total_size = 0
            progress_callback(total_size, total_size)

    return _move()


def chunked_copy(
    src_path: Path,
    dst_path: Path,
    *,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancellationToken] = None,
    chunk_size_kb: int = 1024,
) -> None:
    total_size = 0
    try:
        total_size = src_path.stat().st_size
    except OSError:
        total_size = 0

    bytes_copied = 0
    with src_path.open("rb") as source, dst_path.open("wb") as target:
        while True:
            if cancel_token is not None and cancel_token.is_cancelled():
                raise CancelledError(f"已取消複製: {src_path}")
            chunk = source.read(chunk_size_kb * 1024)
            if not chunk:
                break
            target.write(chunk)
            bytes_copied += len(chunk)
            if progress_callback is not None:
                progress_callback(bytes_copied, total_size)


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
    config=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_token: Optional[CancellationToken] = None,
    logger=None,
) -> str:
    logger = logger or get_logger("FileOps")
    cfg = _resolve_config(config)
    if dst_path.exists():
        raise FileExistsError(f"Destination already exists: {dst_path}")

    mkdir_result = safe_makedirs(dst_path.parent, config=cfg, logger=logger)
    if not mkdir_result.success:
        raise OSError(mkdir_result.error_message)

    if cross_drive_copy:
        copy_result = safe_copy2(
            src_path,
            dst_path,
            config=cfg,
            progress_callback=progress_callback,
            cancel_token=cancel_token,
            logger=logger,
        )
        if not copy_result.success:
            raise OSError(copy_result.error_message)
        logger.info(f"COPIED: {src_path} -> {dst_path}")
        return "COPIED"

    move_result = safe_move(
        src_path,
        dst_path,
        config=cfg,
        progress_callback=progress_callback,
        cancel_token=cancel_token,
        logger=logger,
    )
    if not move_result.success:
        raise OSError(move_result.error_message)
    if move_result.value == "COPIED":
        logger.info(f"COPIED: {src_path} -> {dst_path}")
        return "COPIED"
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


def _is_cross_volume(src_path: Path, dst_path: Path) -> bool:
    src_anchor = src_path.resolve().anchor.lower()
    dst_anchor = dst_path.resolve().anchor.lower()
    return src_anchor != dst_anchor
