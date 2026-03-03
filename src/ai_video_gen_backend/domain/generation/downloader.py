from __future__ import annotations

from typing import Protocol


class MediaDownloadError(Exception):
    """Raised when downloading generated media fails."""


class MediaDownloaderPort(Protocol):
    def download(self, url: str, *, max_bytes: int) -> tuple[bytes, str]:
        """Download media from a URL.

        Returns a tuple of (content_bytes, content_type).
        Raises MediaDownloadError on failure.
        """
        ...
