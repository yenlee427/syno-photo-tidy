from pathlib import Path

import pytest

from syno_photo_tidy.config import ConfigManager
from syno_photo_tidy.core import FileScanner


@pytest.mark.parametrize(
    "path",
    [
        "D:/Photos/Processed_20260211_120000/a.jpg",
        "D:/Photos/TO_DELETE/a.jpg",
        "D:/Photos/KEEP/a.jpg",
        "D:/Photos/REPORT/a.jpg",
        "D:/Photos/ROLLBACK_TRASH/a.jpg",
        "D:/Photos/ROLLBACK_CONFLICTS/a.jpg",
    ],
)
def test_should_exclude_path(path: str) -> None:
    scanner = FileScanner(ConfigManager())
    assert scanner.should_exclude_path(Path(path)) is True


def test_should_not_exclude_normal_path() -> None:
    scanner = FileScanner(ConfigManager())
    assert scanner.should_exclude_path(Path("D:/Photos/Album/a.jpg")) is False
