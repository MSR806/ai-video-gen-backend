from __future__ import annotations

from typing import BinaryIO, Protocol


class VideoThumbnailGenerationError(Exception):
    """Raised when video thumbnail generation fails."""


class VideoThumbnailGeneratorPort(Protocol):
    def extract_first_frame(self, *, video_stream: BinaryIO) -> bytes: ...
