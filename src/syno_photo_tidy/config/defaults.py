"""預設設定值。"""

DEFAULT_CONFIG = {
    "hash": {
        "algorithms": ["sha256", "md5"],
        "chunk_size_kb": 1024,
        "parallel_workers": 4,
    },
    "phash": {
        "threshold": 8,
    },
    "rename": {
        "enabled": True,
        "pattern": "{date}_{time}",
        "sequence_digits": 3,
    },
    "archive": {
        "enabled": True,
        "root_folder": "KEEP",
        "unknown_folder": "unknown",
        "sequence_digits": 3,
    },
    "thumbnail": {
        "max_size_kb": 120,
        "max_dimension_px": 640,
        "min_dimension_px": 320,
    },
}
