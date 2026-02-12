from pathlib import Path

from syno_photo_tidy.core import (
    ManifestContext,
    ManifestWriter,
    append_manifest_entries,
    generate_op_id,
    load_manifest_with_status,
    read_manifest_records,
    update_manifest_status,
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


def test_generate_op_id_is_reproducible() -> None:
    op1 = generate_op_id(
        "MOVE",
        Path("C:/Photos/a.jpg"),
        Path("C:/Photos/KEEP/a.jpg"),
        {},
    )
    op2 = generate_op_id(
        "MOVE",
        Path("C:/Photos/a.jpg"),
        Path("C:/Photos/KEEP/a.jpg"),
        {},
    )
    op3 = generate_op_id(
        "RENAME",
        Path("C:/Photos/a.jpg"),
        Path("C:/Photos/KEEP/a.jpg"),
        {"new_name": "IMG_20240101_000000_0001.jpg"},
    )

    assert op1 == op2
    assert op1 != op3
    assert op1.startswith("op_")


def test_update_manifest_status_and_load(tmp_path: Path) -> None:
    report_dir = tmp_path / "REPORT"
    report_dir.mkdir()

    context = ManifestContext.from_run(
        run_id="Processed_20260211_143015",
        mode="Full Run (Dry-run)",
        source_dir=tmp_path / "source",
        output_dir=tmp_path / "output",
    )
    op_id = generate_op_id("MOVE", Path("a.jpg"), Path("KEEP/a.jpg"), {})

    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(
            [
                ManifestEntry(
                    op_id=op_id,
                    action="MOVE",
                    src_path="a.jpg",
                    dst_path="KEEP/a.jpg",
                    status="PLANNED",
                    reason="THUMBNAIL",
                )
            ]
        )
        manifest_path = writer.finalize()

    updated = update_manifest_status(
        manifest_path,
        op_id,
        "SUCCESS",
        retry_count=2,
        elapsed_time_sec=1.23,
    )
    assert updated is True

    entries = load_manifest_with_status(manifest_path)
    assert len(entries) == 1
    assert entries[0].op_id == op_id
    assert entries[0].status == "SUCCESS"
    assert entries[0].retry_count == 2
    assert entries[0].elapsed_time_sec == 1.23
