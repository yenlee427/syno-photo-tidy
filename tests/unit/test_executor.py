from pathlib import Path

from syno_photo_tidy.core import PlanExecutor
from syno_photo_tidy.models import ActionItem


def test_execute_plan_moves_file(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "dest" / "moved.txt"
    src.write_text("data", encoding="utf-8")

    plan = [ActionItem(action="MOVE", reason="THUMBNAIL", src_path=src, dst_path=dst)]
    executor = PlanExecutor()

    result = executor.execute_plan(plan)

    assert result.cancelled is False
    assert len(result.executed_entries) == 1
    assert result.executed_entries[0].status in {"MOVED", "COPIED"}
    assert dst.exists()


def test_execute_plan_renames_file(tmp_path: Path) -> None:
    src = tmp_path / "source.txt"
    dst = tmp_path / "renamed.txt"
    src.write_text("data", encoding="utf-8")

    plan = [ActionItem(action="RENAME", reason="RENAME", src_path=src, dst_path=dst)]
    executor = PlanExecutor()

    result = executor.execute_plan(plan)

    assert result.cancelled is False
    assert len(result.executed_entries) == 1
    assert result.executed_entries[0].status == "RENAMED"
    assert dst.exists()
