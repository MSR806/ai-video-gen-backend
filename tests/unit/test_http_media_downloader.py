from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

from ai_video_gen_backend.domain.generation import MediaDownloadError
from ai_video_gen_backend.infrastructure.providers.http_media_downloader import (
    HttpMediaDownloader,
)


class FakeResponse:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        chunks: list[bytes] | None = None,
        raise_http_error: bool = False,
    ) -> None:
        self.headers = headers or {}
        self._chunks = chunks or []
        self._raise_http_error = raise_http_error

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def raise_for_status(self) -> None:
        if self._raise_http_error:
            raise httpx.HTTPError('bad response')

    def iter_bytes(self, *, chunk_size: int) -> Iterator[bytes]:
        del chunk_size
        yield from self._chunks


class FakeClient:
    def __init__(
        self,
        *,
        response: FakeResponse | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self._response = response
        self._stream_error = stream_error

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb

    def stream(self, method: str, url: str) -> FakeResponse:
        del method, url
        if self._stream_error is not None:
            raise self._stream_error
        assert self._response is not None
        return self._response


def test_download_success_reads_chunks_and_parses_content_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(
        headers={'Content-Type': 'video/mp4; charset=binary'},
        chunks=[b'abc', b'def'],
    )
    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.http_media_downloader.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(response=response),
    )

    downloader = HttpMediaDownloader()
    payload, content_type = downloader.download('https://provider.test/video.mp4', max_bytes=100)

    assert payload == b'abcdef'
    assert content_type == 'video/mp4'


def test_download_uses_default_content_type_when_header_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(chunks=[b'image'])
    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.http_media_downloader.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(response=response),
    )

    downloader = HttpMediaDownloader()
    payload, content_type = downloader.download('https://provider.test/image.png', max_bytes=10)

    assert payload == b'image'
    assert content_type == 'image/png'


def test_download_raises_when_size_exceeds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    response = FakeResponse(chunks=[b'12345', b'67890'])
    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.http_media_downloader.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(response=response),
    )

    downloader = HttpMediaDownloader()

    with pytest.raises(MediaDownloadError, match='size limit'):
        downloader.download('https://provider.test/image.png', max_bytes=7)


def test_download_maps_httpx_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.providers.http_media_downloader.httpx.Client',
        lambda timeout, follow_redirects: FakeClient(stream_error=httpx.HTTPError('network down')),
    )

    downloader = HttpMediaDownloader()

    with pytest.raises(MediaDownloadError, match='Failed to download generated output'):
        downloader.download('https://provider.test/image.png', max_bytes=100)
