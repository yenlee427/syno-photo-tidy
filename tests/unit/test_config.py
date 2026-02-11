from syno_photo_tidy.config import ConfigManager


def test_config_load_defaults() -> None:
    config = ConfigManager()
    assert config.get("phash.threshold") == 8
    assert config.get("thumbnail.max_size_kb") == 120


def test_config_validation() -> None:
    config = ConfigManager()
    config.set("phash.threshold", 20)
    errors = config.validate_config()
    assert len(errors) > 0
