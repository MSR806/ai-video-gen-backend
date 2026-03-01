from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import BinaryIO

from ai_video_gen_backend.domain.collection_item import VideoThumbnailGenerationError


class FfmpegVideoThumbnailGenerator:
    def __init__(self, *, ffmpeg_bin: str = 'ffmpeg') -> None:
        self._ffmpeg_bin = ffmpeg_bin

    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes:
        with TemporaryDirectory(prefix='video-thumb-') as temp_dir:
            input_path = Path(temp_dir) / 'input-video'
            output_path = Path(temp_dir) / 'thumbnail.jpg'

            try:
                video_stream.seek(0)
                with input_path.open('wb') as input_file:
                    shutil.copyfileobj(video_stream, input_file)
            except Exception as exc:  # pragma: no cover - defensive I/O guard
                raise VideoThumbnailGenerationError(
                    'Failed to read uploaded video stream for thumbnail extraction'
                ) from exc

            command = [
                self._ffmpeg_bin,
                '-hide_banner',
                '-loglevel',
                'error',
                '-y',
                '-i',
                str(input_path),
                '-frames:v',
                '1',
                str(output_path),
            ]

            try:
                subprocess.run(  # noqa: S603 - args are passed as an explicit list, no shell
                    command,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except FileNotFoundError as exc:
                raise VideoThumbnailGenerationError(
                    f'ffmpeg binary "{self._ffmpeg_bin}" was not found'
                ) from exc
            except subprocess.CalledProcessError as exc:
                ffmpeg_error = exc.stderr.strip() if exc.stderr else 'unknown ffmpeg error'
                raise VideoThumbnailGenerationError(
                    f'Failed to extract first frame thumbnail: {ffmpeg_error}'
                ) from exc

            if not output_path.exists():
                raise VideoThumbnailGenerationError(
                    'Failed to extract first frame thumbnail: ffmpeg produced no output'
                )

            thumbnail_bytes = output_path.read_bytes()
            if len(thumbnail_bytes) == 0:
                raise VideoThumbnailGenerationError(
                    'Failed to extract first frame thumbnail: empty thumbnail output'
                )

            return thumbnail_bytes
