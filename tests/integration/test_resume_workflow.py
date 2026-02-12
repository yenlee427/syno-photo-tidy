from pathlib import Path

from syno_photo_tidy.core import (
    ManifestContext,
    ManifestWriter,
    PlanExecutor,
    ResumeManager,
    build_actions_from_manifest,
    generate_op_id,
    load_manifest_with_status,
)
from syno_photo_tidy.models import ActionItem, ManifestEntry


def test_resume_workflow_end_to_end(tmp_path: Path) -> None:
    processed = tmp_path / "Processed_20260212_143000"
    report_dir = processed / "REPORT"
    keep_dir = processed / "KEEP"
    report_dir.mkdir(parents=True)
    keep_dir.mkdir(parents=True)

    src_a = tmp_path / "a.jpg"
    src_b = tmp_path / "b.jpg"
    src_a.write_text("a", encoding="utf-8")
    src_b.write_text("b", encoding="utf-8")

    dst_a = keep_dir / "a.jpg"
    dst_b = keep_dir / "b.jpg"

    op_a = generate_op_id("MOVE", src_a, dst_a, {"reason": "TEST"})
    op_b = generate_op_id("MOVE", src_b, dst_b, {"reason": "TEST"})

    context = ManifestContext.from_run(
        run_id=processed.name,
        mode="Full Run (Dry-run)",
        source_dir=tmp_path,
        output_dir=processed,
    )

    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(
            [
                ManifestEntry(
                    op_id=op_a,
                    action="MOVE",
                    src_path=str(src_a),
                    dst_path=str(dst_a),
                    status="SUCCESS",
                    reason="TEST",
                ),
                ManifestEntry(
                    op_id=op_b,
                    action="MOVE",
                    src_path=str(src_b),
                    dst_path=str(dst_b),
                    status="PLANNED",
                    reason="TEST",
                ),
            ]
        )
        manifest_path = writer.finalize()

    manager = ResumeManager()
    assert manager.is_resumable(manifest_path) is True

    pending = manager.load_resume_plan(manifest_path)
    assert len(pending) == 1
    assert pending[0].op_id == op_b

    actions = build_actions_from_manifest(pending)
    assert actions == [
        ActionItem(action="MOVE", reason="TEST", src_path=src_b, dst_path=dst_b)
    ]

    result = PlanExecutor().execute_plan(actions, manifest_path=manifest_path)
    assert len(result.executed_entries) == 1
    assert len(result.failed_entries) == 0

    final_entries = load_manifest_with_status(manifest_path)
    by_id = {entry.op_id: entry for entry in final_entries if entry.op_id}
    assert by_id[op_a].status == "SUCCESS"
    assert by_id[op_b].status == "SUCCESS"
