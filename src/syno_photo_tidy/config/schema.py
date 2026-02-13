"""設定檔驗證邏輯。"""

from __future__ import annotations

from typing import Any


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def add_error(path: str, message: str) -> None:
        errors.append(f"{path}: {message}")

    retry = config.get("retry", {})
    max_retries = retry.get("max_retries", 5)
    backoff_base_sec = retry.get("backoff_base_sec", 1.0)
    backoff_cap_sec = retry.get("backoff_cap_sec", 30.0)
    if not isinstance(max_retries, int) or max_retries < 0:
        add_error("retry.max_retries", "必須是大於等於 0 的整數")
    if not isinstance(backoff_base_sec, (int, float)) or backoff_base_sec <= 0:
        add_error("retry.backoff_base_sec", "必須是大於 0 的數值")
    if not isinstance(backoff_cap_sec, (int, float)) or backoff_cap_sec <= 0:
        add_error("retry.backoff_cap_sec", "必須是大於 0 的數值")
    if (
        isinstance(backoff_base_sec, (int, float))
        and isinstance(backoff_cap_sec, (int, float))
        and backoff_base_sec > backoff_cap_sec
    ):
        add_error("retry", "backoff_base_sec 不可大於 backoff_cap_sec")

    file_extensions = config.get("file_extensions", {})
    image_exts = file_extensions.get("image", [])
    video_exts = file_extensions.get("video", [])
    if not isinstance(image_exts, list) or any(not isinstance(item, str) for item in image_exts):
        add_error("file_extensions.image", "必須是字串清單")
    if not isinstance(video_exts, list) or any(not isinstance(item, str) for item in video_exts):
        add_error("file_extensions.video", "必須是字串清單")

    move_other_to_keep = config.get("move_other_to_keep", False)
    if not isinstance(move_other_to_keep, bool):
        add_error("move_other_to_keep", "必須是布林值")

    enable_rename = config.get("enable_rename", False)
    if not isinstance(enable_rename, bool):
        add_error("enable_rename", "必須是布林值")

    group_screenshots = config.get("group_screenshots", False)
    if not isinstance(group_screenshots, bool):
        add_error("group_screenshots", "必須是布林值")
    screenshots_dest = config.get("screenshots_dest", "")
    if not isinstance(screenshots_dest, str) or not screenshots_dest.strip():
        add_error("screenshots_dest", "必須是非空字串")
    screenshot_detection_mode = config.get("screenshot_detection_mode", "strict")
    if screenshot_detection_mode not in {"strict", "relaxed"}:
        add_error("screenshot_detection_mode", "必須是 strict 或 relaxed")
    screenshot_filename_patterns = config.get("screenshot_filename_patterns", [])
    if not isinstance(screenshot_filename_patterns, list) or any(
        not isinstance(item, str) for item in screenshot_filename_patterns
    ):
        add_error("screenshot_filename_patterns", "必須是字串清單")
    screenshot_metadata_keywords = config.get("screenshot_metadata_keywords", [])
    if not isinstance(screenshot_metadata_keywords, list) or any(
        not isinstance(item, str) for item in screenshot_metadata_keywords
    ):
        add_error("screenshot_metadata_keywords", "必須是字串清單")

    hash_config = config.get("hash", {})
    algorithms = hash_config.get("algorithms")
    chunk_size_kb = hash_config.get("chunk_size_kb")
    parallel_workers = hash_config.get("parallel_workers", 1)

    if not isinstance(algorithms, list) or not algorithms:
        add_error("hash.algorithms", "必須是非空清單")
    else:
        for algo in algorithms:
            if not isinstance(algo, str):
                add_error("hash.algorithms", "清單項目必須是字串")
                break

    if not isinstance(chunk_size_kb, int) or chunk_size_kb <= 0:
        add_error("hash.chunk_size_kb", "必須是正整數")
    if not isinstance(parallel_workers, int) or parallel_workers <= 0:
        add_error("hash.parallel_workers", "必須是正整數")

    phash = config.get("phash", {})
    threshold = phash.get("threshold")
    if not isinstance(threshold, int):
        add_error("phash.threshold", "必須是整數")
    elif not (0 <= threshold <= 16):
        add_error("phash.threshold", "必須介於 0 到 16")

    thumbnail = config.get("thumbnail", {})
    max_size_kb = thumbnail.get("max_size_kb")
    max_dimension_px = thumbnail.get("max_dimension_px")
    min_dimension_px = thumbnail.get("min_dimension_px")

    if not isinstance(max_size_kb, int) or max_size_kb <= 0:
        add_error("thumbnail.max_size_kb", "必須是正整數")
    if not isinstance(max_dimension_px, int) or max_dimension_px <= 0:
        add_error("thumbnail.max_dimension_px", "必須是正整數")
    if not isinstance(min_dimension_px, int) or min_dimension_px <= 0:
        add_error("thumbnail.min_dimension_px", "必須是正整數")

    rename = config.get("rename", {})
    enabled = rename.get("enabled", True)
    pattern = rename.get("pattern")
    sequence_digits = rename.get("sequence_digits")
    if not isinstance(enabled, bool):
        add_error("rename.enabled", "必須是布林值")
    if not isinstance(pattern, str) or not pattern.strip():
        add_error("rename.pattern", "必須是非空字串")
    if not isinstance(sequence_digits, int) or sequence_digits <= 0:
        add_error("rename.sequence_digits", "必須是正整數")

    archive = config.get("archive", {})
    archive_enabled = archive.get("enabled", True)
    root_folder = archive.get("root_folder")
    unknown_folder = archive.get("unknown_folder")
    archive_sequence_digits = archive.get("sequence_digits")
    if not isinstance(archive_enabled, bool):
        add_error("archive.enabled", "必須是布林值")
    if not isinstance(root_folder, str) or not root_folder.strip():
        add_error("archive.root_folder", "必須是非空字串")
    if not isinstance(unknown_folder, str) or not unknown_folder.strip():
        add_error("archive.unknown_folder", "必須是非空字串")
    if not isinstance(archive_sequence_digits, int) or archive_sequence_digits <= 0:
        add_error("archive.sequence_digits", "必須是正整數")

    progress = config.get("progress", {})
    ui_update_interval_ms = progress.get("ui_update_interval_ms", 250)
    heartbeat_interval_sec = progress.get("heartbeat_interval_sec", 2.0)
    bytes_update_threshold = progress.get("bytes_update_threshold", 1048576)
    speed_window_sec = progress.get("speed_window_sec", 5)
    slow_network_threshold_mbps = progress.get("slow_network_threshold_mbps", 5.0)
    slow_network_check_count = progress.get("slow_network_check_count", 3)
    slow_network_min_bytes = progress.get("slow_network_min_bytes", 5242880)
    slow_network_min_elapsed_ms = progress.get("slow_network_min_elapsed_ms", 300)
    hash_progress_workers = progress.get("hash_progress_workers", 4)
    log_max_lines = progress.get("log_max_lines", 500)

    if not isinstance(ui_update_interval_ms, int) or ui_update_interval_ms <= 0:
        add_error("progress.ui_update_interval_ms", "必須是正整數")
    if not isinstance(heartbeat_interval_sec, (int, float)) or heartbeat_interval_sec <= 0:
        add_error("progress.heartbeat_interval_sec", "必須是大於 0 的數值")
    if not isinstance(bytes_update_threshold, int) or bytes_update_threshold <= 0:
        add_error("progress.bytes_update_threshold", "必須是正整數")
    if not isinstance(speed_window_sec, (int, float)) or speed_window_sec <= 0:
        add_error("progress.speed_window_sec", "必須是大於 0 的數值")
    if not isinstance(slow_network_threshold_mbps, (int, float)) or slow_network_threshold_mbps <= 0:
        add_error("progress.slow_network_threshold_mbps", "必須是大於 0 的數值")
    if not isinstance(slow_network_check_count, int) or slow_network_check_count <= 0:
        add_error("progress.slow_network_check_count", "必須是正整數")
    if not isinstance(slow_network_min_bytes, int) or slow_network_min_bytes <= 0:
        add_error("progress.slow_network_min_bytes", "必須是正整數")
    if not isinstance(slow_network_min_elapsed_ms, int) or slow_network_min_elapsed_ms <= 0:
        add_error("progress.slow_network_min_elapsed_ms", "必須是正整數")
    if not isinstance(hash_progress_workers, int) or hash_progress_workers <= 0:
        add_error("progress.hash_progress_workers", "必須是正整數")
    if not isinstance(log_max_lines, int) or log_max_lines <= 0:
        add_error("progress.log_max_lines", "必須是正整數")

    return errors
