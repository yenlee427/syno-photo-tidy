"""設定檔驗證邏輯。"""

from __future__ import annotations

from typing import Any


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def add_error(path: str, message: str) -> None:
        errors.append(f"{path}: {message}")

    hash_config = config.get("hash", {})
    algorithms = hash_config.get("algorithms")
    chunk_size_kb = hash_config.get("chunk_size_kb")

    if not isinstance(algorithms, list) or not algorithms:
        add_error("hash.algorithms", "必須是非空清單")
    else:
        for algo in algorithms:
            if not isinstance(algo, str):
                add_error("hash.algorithms", "清單項目必須是字串")
                break

    if not isinstance(chunk_size_kb, int) or chunk_size_kb <= 0:
        add_error("hash.chunk_size_kb", "必須是正整數")

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

    return errors
