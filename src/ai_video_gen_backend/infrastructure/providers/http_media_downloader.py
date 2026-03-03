from __future__ import annotations

import httpx

from ai_video_gen_backend.domain.generation import MediaDownloadError


class HttpMediaDownloader:
    def download(self, url: str, *, max_bytes: int) -> tuple[bytes, str]:
        downloaded = bytearray()
        content_type = 'image/png'

        try:
            with (
                httpx.Client(timeout=20.0, follow_redirects=True) as client,
                client.stream('GET', url) as response,
            ):
                response.raise_for_status()
                header_content_type = response.headers.get('Content-Type')
                if isinstance(header_content_type, str) and len(header_content_type.strip()) > 0:
                    content_type = header_content_type.split(';', maxsplit=1)[0].strip()

                for chunk in response.iter_bytes(chunk_size=65536):
                    downloaded.extend(chunk)
                    if len(downloaded) > max_bytes:
                        raise MediaDownloadError(
                            'Generated output exceeds configured download size limit'
                        )
        except httpx.HTTPError as exc:
            raise MediaDownloadError('Failed to download generated output') from exc

        return bytes(downloaded), content_type
