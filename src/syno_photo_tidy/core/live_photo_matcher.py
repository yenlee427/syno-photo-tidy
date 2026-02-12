"""iPhone Live Photo 配對引擎。"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from ..models import FileInfo, LivePhotoPair


class LivePhotoMatcher:
    IMAGE_EXTS = {".heic", ".jpg", ".jpeg"}
    VIDEO_EXTS = {".mov", ".mp4"}

    def find_live_pairs(self, files: list[FileInfo]) -> list[LivePhotoPair]:
        folder_groups: dict[Path, list[FileInfo]] = defaultdict(list)
        for file_info in files:
            folder_groups[file_info.path.parent].append(file_info)

        pairs: list[LivePhotoPair] = []

        for folder in sorted(folder_groups.keys(), key=lambda item: str(item)):
            folder_files = folder_groups[folder]
            images = [
                file_info
                for file_info in folder_files
                if file_info.file_type == "IMAGE" and file_info.ext.lower() in self.IMAGE_EXTS
            ]
            videos = [
                file_info
                for file_info in folder_files
                if file_info.file_type == "VIDEO" and file_info.ext.lower() in self.VIDEO_EXTS
            ]

            images.sort(key=lambda item: (item.timestamp_locked, item.path.stem, str(item.path)))
            videos.sort(key=lambda item: (item.timestamp_locked, item.path.stem, str(item.path)))

            candidates: list[tuple[float, FileInfo, FileInfo]] = []
            for image in images:
                image_time = self._parse_timestamp(image.timestamp_locked)
                if image_time is None:
                    continue
                for video in videos:
                    video_time = self._parse_timestamp(video.timestamp_locked)
                    if video_time is None:
                        continue
                    time_diff = abs(image_time - video_time)
                    if time_diff <= timedelta(seconds=2):
                        candidates.append((float(time_diff.total_seconds()), image, video))

            candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1].path.stem,
                    item[2].path.stem,
                    str(item[1].path),
                    str(item[2].path),
                )
            )

            used_images: set[Path] = set()
            used_videos: set[Path] = set()

            for diff_sec, image, video in candidates:
                if image.path in used_images or video.path in used_videos:
                    continue

                pair_id = self.calculate_pair_id(image, video)
                image.is_live_pair = True
                image.pair_id = pair_id
                image.pair_confidence = "high"

                video.is_live_pair = True
                video.pair_id = pair_id
                video.pair_confidence = "high"

                pairs.append(
                    LivePhotoPair(
                        image=image,
                        video=video,
                        pair_id=pair_id,
                        confidence="high",
                        time_diff_sec=diff_sec,
                    )
                )
                used_images.add(image.path)
                used_videos.add(video.path)

        return pairs

    def calculate_pair_id(self, image: FileInfo, video: FileInfo) -> str:
        payload = {
            "image": str(image.path).replace("\\", "/"),
            "video": str(video.path).replace("\\", "/"),
            "image_ts": image.timestamp_locked,
            "video_ts": video.timestamp_locked,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"pair_{digest[:16]}"

    def _parse_timestamp(self, value: str) -> datetime | None:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
