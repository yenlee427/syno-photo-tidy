import hashlib
from pathlib import Path

from syno_photo_tidy.utils import hash_calc


def test_compute_hashes(tmp_path: Path) -> None:
    sample_path = tmp_path / "sample.bin"
    sample_path.write_bytes(b"syno-photo-tidy")

    expected_md5 = hashlib.md5(b"syno-photo-tidy").hexdigest()
    expected_sha256 = hashlib.sha256(b"syno-photo-tidy").hexdigest()

    hashes = hash_calc.compute_hashes(sample_path, ["md5", "sha256"])

    assert hashes["md5"] == expected_md5
    assert hashes["sha256"] == expected_sha256
