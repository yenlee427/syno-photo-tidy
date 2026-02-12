from pathlib import Path
from unittest.mock import patch

from syno_photo_tidy.core import (
    ManifestContext,
    ManifestWriter,
    PlanExecutor,
    generate_op_id,
    load_manifest_with_status,
)
from syno_photo_tidy.models import ActionItem, ManifestEntry
from syno_photo_tidy.utils.file_ops import safe_copy2


def _write_manifest(report_dir: Path, entries: list[ManifestEntry]) -> Path:
    context = ManifestContext.from_run(
        run_id=report_dir.parent.name,
        mode="Full Run (Dry-run)",
        source_dir=report_dir.parent,
        output_dir=report_dir.parent,
    )
    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(entries)
        return writer.finalize()


def test_network_failure_retry(tmp_path: Path) -> None:
    src = tmp_path / "src.jpg"
    dst = tmp_path / "dst.jpg"
    src.write_text("x", encoding="utf-8")

    with patch("syno_photo_tidy.utils.file_ops.time.sleep", return_value=None), patch(
        "syno_photo_tidy.utils.file_ops.shutil.copy2",
        side_effect=[OSError("Network error"), OSError("Network error"), None],
    ):
        result = safe_copy2(
            src,
            dst,
            max_retries=5,
            backoff_base_sec=0.01,
            backoff_cap_sec=0.01,
        )

    assert result.success is True
    assert result.retry_count == 2


def test_partial_success_manifest(tmp_path: Path) -> None:
    processed = tmp_path / "Processed_20260212_143000"
    report_dir = processed / "REPORT"
    report_dir.mkdir(parents=True)

    plan: list[ActionItem] = []
    entries: list[ManifestEntry] = []
    for index in range(5):
        src = tmp_path / f"f{index}.jpg"
        src.write_text("data", encoding="utf-8")
        dst = processed / "KEEP" / f"f{index}.jpg"
        action = ActionItem(action="MOVE", reason="TEST", src_path=src, dst_path=dst)
        plan.append(action)
        entries.append(
            ManifestEntry(
                op_id=generate_op_id("MOVE", src, dst, {"reason": "TEST"}),
                action="MOVE",
                src_path=str(src),
                dst_path=str(dst),
                status="PLANNED",
            )
        )

    manifest_path = _write_manifest(report_dir, entries)

    fail_indices = {1, 3}

    def _side_effect(src_path, dst_path, **kwargs):
        file_index = int(Path(src_path).stem.replace("f", ""))
        if file_index in fail_indices:
            raise OSError("Network error")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        return "MOVED"

    with patch("syno_photo_tidy.core.executor.file_ops.move_or_copy", side_effect=_side_effect):
        result = PlanExecutor().execute_plan(plan, manifest_path=manifest_path)

    assert len(result.executed_entries) == 3
    assert len(result.failed_entries) == 2

    loaded = load_manifest_with_status(manifest_path)
    success_count = sum(1 for item in loaded if item.status == "SUCCESS")
    failed_count = sum(1 for item in loaded if item.status == "FAILED")
    assert success_count == 3
    assert failed_count == 2


def test_resume_skip_completed(tmp_path: Path) -> None:
    processed = tmp_path / "Processed_20260212_143000"
    report_dir = processed / "REPORT"
    report_dir.mkdir(parents=True)

    src1 = tmp_path / "a.jpg"
    src2 = tmp_path / "b.jpg"
    src1.write_text("a", encoding="utf-8")
    src2.write_text("b", encoding="utf-8")

    dst1 = processed / "KEEP" / "a.jpg"
    dst2 = processed / "KEEP" / "b.jpg"

    plan = [
        ActionItem(action="MOVE", reason="TEST", src_path=src1, dst_path=dst1),
        ActionItem(action="MOVE", reason="TEST", src_path=src2, dst_path=dst2),
    ]

    entries = [
        ManifestEntry(
            op_id=generate_op_id("MOVE", src1, dst1, {"reason": "TEST"}),
            action="MOVE",
            src_path=str(src1),
            dst_path=str(dst1),
            status="SUCCESS",
        ),
        ManifestEntry(
            op_id=generate_op_id("MOVE", src2, dst2, {"reason": "TEST"}),
            action="MOVE",
            src_path=str(src2),
            dst_path=str(dst2),
            status="PLANNED",
        ),
    ]

    manifest_path = _write_manifest(report_dir, entries)

    result = PlanExecutor().execute_plan(plan, manifest_path=manifest_path)

    assert len(result.executed_entries) == 1
    loaded = load_manifest_with_status(manifest_path)
    assert all(item.status == "SUCCESS" for item in loaded)
