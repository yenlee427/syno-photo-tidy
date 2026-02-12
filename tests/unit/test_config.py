from syno_photo_tidy.config import ConfigManager


def test_config_load_defaults() -> None:
    config = ConfigManager()
    assert config.get("phash.threshold") == 8
    assert config.get("thumbnail.max_size_kb") == 120
    assert config.get("rename.pattern") == "{date}_{time}"
    assert config.get("rename.enabled") is True
    assert config.get("enable_rename") is False
    assert config.get("archive.enabled") is True
    assert config.get("hash.parallel_workers") == 4
    assert ".jpg" in config.get("file_extensions.image")
    assert ".mp4" in config.get("file_extensions.video")


def test_config_validation() -> None:
    config = ConfigManager()
    config.set("phash.threshold", 20)
    errors = config.validate_config()
    assert len(errors) > 0
