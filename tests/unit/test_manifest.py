from pathlib import Path

from syno_photo_tidy.core import (
    ManifestContext,
    ManifestWriter,
    append_manifest_entries,
    read_manifest_records,
)
from syno_photo_tidy.models import ManifestEntry


def test_manifest_writer_creates_run_record(tmp_path: Path) -> None:
    report_dir = tmp_path / "REPORT"
    report_dir.mkdir()

    context = ManifestContext.from_run(
        run_id="Processed_20260211_143015",
        mode="Full Run (Dry-run)",
        source_dir=tmp_path / "source",
        output_dir=tmp_path / "output",
    )

    entries = [
        ManifestEntry(
            action="MOVE",
            src_path="a.jpg",
            dst_path="TO_DELETE/a.jpg",
            status="PLANNED",
            reason="THUMBNAIL",
        )
    ]

    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(entries)
        manifest_path = writer.finalize()

    assert manifest_path.exists()

    records = read_manifest_records(manifest_path)
    assert records[0]["record_type"] == "RUN"
    assert records[1]["record_type"] == "ACTION"


def test_manifest_append_entries(tmp_path: Path) -> None:
    report_dir = tmp_path / "REPORT"
    report_dir.mkdir()

    context = ManifestContext.from_run(
        run_id="Processed_20260211_143015",
        mode="Full Run (Dry-run)",
        source_dir=tmp_path / "source",
        output_dir=tmp_path / "output",
    )

    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries([])
        manifest_path = writer.finalize()

    append_manifest_entries(
        manifest_path,
        [
            ManifestEntry(
                action="MOVE",
                src_path="a.jpg",
                dst_path="TO_DELETE/a.jpg",
                status="MOVED",
                reason="THUMBNAIL",
            )
        ],
    )

    records = read_manifest_records(manifest_path)
    assert records[-1]["record_type"] == "ACTION"
    assert records[-1]["status"] == "MOVED"
