from pathlib import Path

from syno_photo_tidy.core import ManifestContext, ManifestWriter, RollbackRunner
from syno_photo_tidy.models import ManifestEntry


def _write_manifest(report_dir: Path, entries: list[ManifestEntry]) -> Path:
    context = ManifestContext.from_run(
        run_id=report_dir.parent.name,
        mode="Full Run",
        source_dir=report_dir.parent,
        output_dir=report_dir.parent,
    )
    with ManifestWriter(report_dir, context) as writer:
        writer.write_entries(entries)
        return writer.finalize()


def test_rollback_moves_back(tmp_path: Path) -> None:
    processed_dir = tmp_path / "Processed_20260211_143015"
    report_dir = processed_dir / "REPORT"
    report_dir.mkdir(parents=True)

    src = tmp_path / "source.jpg"
    dst = processed_dir / "TO_DELETE" / "THUMBNAILS" / "source.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("data", encoding="utf-8")

    _write_manifest(
        report_dir,
        [
            ManifestEntry(
                action="MOVE",
                src_path=str(src),
                dst_path=str(dst),
                status="MOVED",
                reason="THUMBNAIL",
            )
        ],
    )

    runner = RollbackRunner()
    result = runner.rollback(processed_dir)

    assert len(result.rolled_back) == 1
    assert src.exists()
    assert not dst.exists()


def test_rollback_copied_moves_to_trash(tmp_path: Path) -> None:
    processed_dir = tmp_path / "Processed_20260211_143015"
    report_dir = processed_dir / "REPORT"
    report_dir.mkdir(parents=True)

    src = tmp_path / "source.jpg"
    src.write_text("data", encoding="utf-8")
    dst = processed_dir / "TO_DELETE" / "DUPLICATES" / "source.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("copy", encoding="utf-8")

    _write_manifest(
        report_dir,
        [
            ManifestEntry(
                action="MOVE",
                src_path=str(src),
                dst_path=str(dst),
                status="COPIED",
                reason="DUPLICATE_HASH",
            )
        ],
    )

    runner = RollbackRunner()
    result = runner.rollback(processed_dir)

    trash_path = (
        processed_dir / "ROLLBACK_TRASH" / "TO_DELETE" / "DUPLICATES" / "source.jpg"
    )
    assert len(result.trashed) == 1
    assert trash_path.exists()
    assert not dst.exists()


def test_rollback_conflict(tmp_path: Path) -> None:
    processed_dir = tmp_path / "Processed_20260211_143015"
    report_dir = processed_dir / "REPORT"
    report_dir.mkdir(parents=True)

    src = tmp_path / "source.jpg"
    src.write_text("data", encoding="utf-8")
    dst = processed_dir / "KEEP" / "source.jpg"
    dst.parent.mkdir(parents=True)
    dst.write_text("moved", encoding="utf-8")

    _write_manifest(
        report_dir,
        [
            ManifestEntry(
                action="MOVE",
                src_path=str(src),
                dst_path=str(dst),
                status="MOVED",
                reason="ARCHIVE",
            )
        ],
    )

    runner = RollbackRunner()
    result = runner.rollback(processed_dir)

    conflict_path = processed_dir / "ROLLBACK_CONFLICTS" / "KEEP" / "source.jpg"
    assert len(result.conflicts) == 1
    assert conflict_path.exists()
    assert dst.exists() is False
