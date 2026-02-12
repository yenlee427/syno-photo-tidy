"""Manifest writer and reader."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..models import ManifestEntry
from ..utils.logger import get_logger


def _normalize_path_for_id(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def generate_op_id(
    action: str,
    src_path: Path,
    dst_path: Path,
    extra: dict | None = None,
) -> str:
    payload = {
        "action": action,
        "src": _normalize_path_for_id(src_path),
        "dst": _normalize_path_for_id(dst_path),
        "extra": extra or {},
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"op_{digest[:16]}"


def update_manifest_status(
    manifest_path: Path,
    op_id: str,
    status: str,
    *,
    error_message: str | None = None,
    retry_count: int | None = None,
    elapsed_time_sec: float | None = None,
    result_status: str | None = None,
) -> bool:
    records = read_manifest_records(manifest_path)
    updated = False

    for record in records:
        if record.get("record_type") != "ACTION":
            continue
        if record.get("op_id") != op_id:
            continue

        record["status"] = status
        if error_message is not None:
            record["error_message"] = error_message
        if retry_count is not None:
            record["retry_count"] = retry_count
        if elapsed_time_sec is not None:
            record["elapsed_time_sec"] = elapsed_time_sec
        if result_status is not None:
            record["result_status"] = result_status
        updated = True
        break

    if not updated:
        return False

    temp_path = manifest_path.with_suffix(".jsonl.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    temp_path.replace(manifest_path)
    return True


def load_manifest_with_status(manifest_path: Path) -> list[ManifestEntry]:
    records = read_manifest_records(manifest_path)
    entries: list[ManifestEntry] = []

    for record in records:
        if record.get("record_type") != "ACTION":
            continue

        entries.append(
            ManifestEntry(
                op_id=str(record.get("op_id")) if record.get("op_id") else None,
                action=str(record.get("action", "")),
                src_path=str(record.get("src_path", "")),
                dst_path=str(record.get("dst_path")) if record.get("dst_path") else None,
                status=str(record.get("status", "")),
                reason=str(record.get("reason")) if record.get("reason") else None,
                error_code=str(record.get("error_code")) if record.get("error_code") else None,
                error_message=str(record.get("error_message")) if record.get("error_message") else None,
                retry_count=int(record.get("retry_count", 0) or 0),
                elapsed_time_sec=float(record.get("elapsed_time_sec", 0.0) or 0.0),
                size_bytes=int(record.get("size_bytes")) if record.get("size_bytes") is not None else None,
                resolution=tuple(record.get("resolution")) if record.get("resolution") else None,
                hash_md5=str(record.get("hash_md5")) if record.get("hash_md5") else None,
                hash_sha256=str(record.get("hash_sha256")) if record.get("hash_sha256") else None,
                timestamp_locked=str(record.get("timestamp_locked")) if record.get("timestamp_locked") else None,
                timestamp_source=str(record.get("timestamp_source")) if record.get("timestamp_source") else None,
                file_type=str(record.get("file_type")) if record.get("file_type") else None,
                is_live_pair=bool(record.get("is_live_pair", False)),
                pair_id=str(record.get("pair_id")) if record.get("pair_id") else None,
                pair_confidence=str(record.get("pair_confidence")) if record.get("pair_confidence") else None,
                is_screenshot=bool(record.get("is_screenshot", False)),
                screenshot_evidence=(
                    str(record.get("screenshot_evidence"))
                    if record.get("screenshot_evidence")
                    else None
                ),
            )
        )

    return entries


@dataclass
class ManifestContext:
    run_id: str
    mode: str
    source_dir: str
    output_dir: str
    created_at: str

    @classmethod
    def from_run(
        cls,
        *,
        run_id: str,
        mode: str,
        source_dir: Path,
        output_dir: Path,
    ) -> "ManifestContext":
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return cls(
            run_id=run_id,
            mode=mode,
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            created_at=created_at,
        )


class ManifestWriter:
    def __init__(self, report_dir: Path, context: ManifestContext, logger=None) -> None:
        self.report_dir = report_dir
        self.context = context
        self.logger = logger or get_logger(self.__class__.__name__)
        self.manifest_path = report_dir / "manifest.jsonl"
        self.partial_path = report_dir / "manifest.jsonl.partial"
        self._handle = self.partial_path.open("w", encoding="utf-8")
        self._write_record(
            {
                "record_type": "RUN",
                "run_id": context.run_id,
                "mode": context.mode,
                "source_dir": context.source_dir,
                "output_dir": context.output_dir,
                "created_at": context.created_at,
            }
        )

    def __enter__(self) -> "ManifestWriter":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.finalize()

    def write_entry(self, entry: ManifestEntry) -> None:
        payload = entry.to_dict()
        payload["record_type"] = "ACTION"
        self._write_record(payload)

    def write_entries(self, entries: Iterable[ManifestEntry]) -> None:
        for entry in entries:
            self.write_entry(entry)

    def finalize(self) -> Path:
        if not self._handle.closed:
            self._handle.close()
        if self.partial_path.exists():
            self.partial_path.replace(self.manifest_path)
        return self.manifest_path

    def _write_record(self, payload: dict[str, object]) -> None:
        self._handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_manifest_records(manifest_path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    except OSError as exc:
        logger = get_logger("ManifestReader")
        logger.warning(f"無法讀取 manifest: {manifest_path} ({exc})")
    return records


def append_manifest_entries(
    manifest_path: Path,
    entries: Iterable[ManifestEntry],
    logger=None,
) -> None:
    logger = logger or get_logger("ManifestAppender")
    try:
        with manifest_path.open("a", encoding="utf-8") as handle:
            for entry in entries:
                payload = entry.to_dict()
                payload["record_type"] = "ACTION"
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError as exc:
        logger.warning(f"無法追加 manifest: {manifest_path} ({exc})")
