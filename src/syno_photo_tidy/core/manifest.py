"""Manifest writer and reader."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from ..models import ManifestEntry
from ..utils.logger import get_logger


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
