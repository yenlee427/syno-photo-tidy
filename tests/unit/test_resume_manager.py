from pathlib import Path

from syno_photo_tidy.core import ManifestContext, ManifestWriter, ResumeManager
from syno_photo_tidy.models import ManifestEntry


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


def test_find_latest_manifest(tmp_path: Path) -> None:
    manager = ResumeManager()
    older = tmp_path / "Processed_20260101_000000" / "REPORT"
    newer = tmp_path / "Processed_20260102_000000" / "REPORT"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)

    _write_manifest(older, [])
    latest_path = _write_manifest(newer, [])

    found = manager.find_latest_manifest(tmp_path)
    assert found == latest_path


def test_load_resume_plan_filters_success(tmp_path: Path) -> None:
    manager = ResumeManager()
    report_dir = tmp_path / "Processed_20260102_000000" / "REPORT"
    report_dir.mkdir(parents=True)

    manifest_path = _write_manifest(
        report_dir,
        [
            ManifestEntry(
                op_id="op_1",
                action="MOVE",
                src_path="a.jpg",
                dst_path="KEEP/a.jpg",
                status="SUCCESS",
            ),
            ManifestEntry(
                op_id="op_2",
                action="MOVE",
                src_path="b.jpg",
                dst_path="KEEP/b.jpg",
                status="FAILED",
            ),
        ],
    )

    pending = manager.load_resume_plan(manifest_path)
    assert len(pending) == 1
    assert pending[0].op_id == "op_2"


def test_validate_manifest_duplicate_op_id(tmp_path: Path) -> None:
    manager = ResumeManager()
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(
        "\n".join(
            [
                '{"record_type":"RUN"}',
                '{"record_type":"ACTION","op_id":"op_1","action":"MOVE","src_path":"a.jpg","status":"PLANNED"}',
                '{"record_type":"ACTION","op_id":"op_1","action":"MOVE","src_path":"b.jpg","status":"FAILED"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    validation = manager.validate_manifest(manifest_path)
    assert validation.is_valid is False
    assert any("op_id 重複" in error for error in validation.errors)
