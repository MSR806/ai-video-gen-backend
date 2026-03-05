from __future__ import annotations

import subprocess
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, cast

import pytest

from ai_video_gen_backend.domain.collection_item import VideoThumbnailGenerationError
from ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator import (
    FfmpegVideoThumbnailGenerator,
)


def test_extract_first_frame_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        output_path = Path(command[-1])
        output_path.write_bytes(b'jpeg-bytes')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator.subprocess.run',
        fake_run,
    )

    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='ffmpeg')
    result = generator.extract_first_frame(video_stream=BytesIO(b'video-bytes'))

    assert result == b'jpeg-bytes'


def test_extract_first_frame_raises_when_ffmpeg_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del command, check, capture_output, text
        raise FileNotFoundError

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator.subprocess.run',
        fake_run,
    )

    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='missing-ffmpeg')

    with pytest.raises(VideoThumbnailGenerationError, match='missing-ffmpeg'):
        generator.extract_first_frame(video_stream=BytesIO(b'video-bytes'))


def test_extract_first_frame_raises_when_ffmpeg_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        raise subprocess.CalledProcessError(1, command, stderr='invalid stream')

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator.subprocess.run',
        fake_run,
    )

    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='ffmpeg')

    with pytest.raises(VideoThumbnailGenerationError, match='invalid stream'):
        generator.extract_first_frame(video_stream=BytesIO(b'video-bytes'))


def test_extract_first_frame_raises_when_ffmpeg_produces_no_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del command, check, capture_output, text
        return subprocess.CompletedProcess([], 0, '', '')

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator.subprocess.run',
        fake_run,
    )

    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='ffmpeg')

    with pytest.raises(VideoThumbnailGenerationError, match='produced no output'):
        generator.extract_first_frame(video_stream=BytesIO(b'video-bytes'))


def test_extract_first_frame_raises_when_thumbnail_output_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        del check, capture_output, text
        output_path = Path(command[-1])
        output_path.write_bytes(b'')
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.ffmpeg_video_thumbnail_generator.subprocess.run',
        fake_run,
    )

    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='ffmpeg')

    with pytest.raises(VideoThumbnailGenerationError, match='empty thumbnail output'):
        generator.extract_first_frame(video_stream=BytesIO(b'video-bytes'))


def test_extract_first_frame_raises_when_input_stream_is_unreadable() -> None:
    generator = FfmpegVideoThumbnailGenerator(ffmpeg_bin='ffmpeg')

    with pytest.raises(VideoThumbnailGenerationError, match='Failed to read uploaded video stream'):
        generator.extract_first_frame(video_stream=cast(BinaryIO, BrokenStream()))


class BrokenStream:
    def seek(self, offset: int, whence: int = 0) -> int:
        del offset, whence
        raise OSError('broken stream')

    def read(self, size: int = -1) -> bytes:
        del size
        return b''
