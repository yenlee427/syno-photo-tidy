"""Resume 管理工具。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..models import ManifestEntry
from .manifest import load_manifest_with_status, read_manifest_records


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


class ResumeManager:
    VALID_STATUS = {"PLANNED", "STARTED", "SUCCESS", "FAILED"}

    def find_latest_manifest(self, output_root: Path) -> Path | None:
        candidates = sorted(
            output_root.glob("Processed_*/REPORT/manifest*.jsonl"),
            key=lambda path: path.parent.parent.name,
            reverse=True,
        )
        return candidates[0] if candidates else None

    def load_resume_plan(self, manifest_path: Path) -> list[ManifestEntry]:
        entries = load_manifest_with_status(manifest_path)
        by_op_id: dict[str, ManifestEntry] = {}

        for entry in entries:
            if not entry.op_id:
                continue
            by_op_id[entry.op_id] = entry

        pending = [entry for entry in by_op_id.values() if entry.status != "SUCCESS"]
        pending.sort(key=lambda item: item.op_id or "")
        return pending

    def is_resumable(self, manifest_path: Path) -> bool:
        validation = self.validate_manifest(manifest_path)
        if not validation.is_valid:
            return False
        return len(self.load_resume_plan(manifest_path)) > 0

    def validate_manifest(self, manifest_path: Path) -> ValidationResult:
        errors: list[str] = []
        if not manifest_path.exists():
            return ValidationResult(is_valid=False, errors=[f"檔案不存在: {manifest_path}"])

        try:
            lines = manifest_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return ValidationResult(is_valid=False, errors=[f"無法讀取 manifest: {exc}"])

        seen_op_ids: set[str] = set()
        for index, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"第 {index} 行 JSON 解析失敗: {exc}")
                continue

            if record.get("record_type") != "ACTION":
                continue

            missing = [
                key
                for key in ("op_id", "action", "src_path", "status")
                if key not in record or record.get(key) in {None, ""}
            ]
            if missing:
                errors.append(f"第 {index} 行缺少欄位: {', '.join(missing)}")
                continue

            status = str(record.get("status"))
            if status not in self.VALID_STATUS:
                errors.append(f"第 {index} 行 status 非法: {status}")

            op_id = str(record.get("op_id"))
            if op_id in seen_op_ids:
                errors.append(f"第 {index} 行 op_id 重複: {op_id}")
            seen_op_ids.add(op_id)

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def build_actions_from_manifest(entries: list[ManifestEntry]):
    from ..models import ActionItem

    actions: list[ActionItem] = []
    for entry in entries:
        if not entry.dst_path:
            continue
        actions.append(
            ActionItem(
                action=entry.action,
                reason=entry.reason or "RESUME",
                src_path=Path(entry.src_path),
                dst_path=Path(entry.dst_path),
            )
        )
    return actions
