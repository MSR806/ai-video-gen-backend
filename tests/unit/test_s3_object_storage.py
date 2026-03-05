from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import pytest
from botocore.exceptions import ClientError

from ai_video_gen_backend.domain.collection_item import StorageError
from ai_video_gen_backend.infrastructure.storage.s3_object_storage import S3ObjectStorage


class FakeS3Client:
    def __init__(
        self,
        *,
        upload_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.upload_error = upload_error
        self.delete_error = delete_error
        self.upload_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, str]] = []

    def upload_fileobj(
        self,
        body: BinaryIO,
        bucket: str,
        key: str,
        **kwargs: object,
    ) -> None:
        if self.upload_error is not None:
            raise self.upload_error

        extra_args = kwargs.get('ExtraArgs')
        content_type: str | None = None
        if isinstance(extra_args, dict):
            content_type_raw = extra_args.get('ContentType')
            if isinstance(content_type_raw, str):
                content_type = content_type_raw

        payload = body.read()
        self.upload_calls.append(
            {
                'bucket': bucket,
                'key': key,
                'content_type': content_type,
                'payload': payload,
            }
        )

    def delete_object(self, **kwargs: object) -> None:
        if self.delete_error is not None:
            raise self.delete_error

        bucket_raw = kwargs.get('Bucket')
        key_raw = kwargs.get('Key')
        if isinstance(bucket_raw, str) and isinstance(key_raw, str):
            self.delete_calls.append({'bucket': bucket_raw, 'key': key_raw})


def _storage(fake_client: FakeS3Client, monkeypatch: pytest.MonkeyPatch) -> S3ObjectStorage:
    monkeypatch.setattr(
        'ai_video_gen_backend.infrastructure.storage.s3_object_storage.boto3.client',
        lambda *args, **kwargs: fake_client,
    )
    test_secret_key = 'test-secret-key'
    return S3ObjectStorage(
        endpoint='https://s3.test',
        public_base_url='https://cdn.test/media/',
        access_key='key',
        secret_key=test_secret_key,
        bucket='media-bucket',
        region='us-east-1',
        secure=True,
    )


def test_upload_object_success_returns_stored_object_and_encoded_public_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeS3Client()
    storage = _storage(fake_client, monkeypatch)

    stream = BytesIO(b'image-bytes')
    stream.seek(5)

    stored = storage.upload_object(
        key='generated/My File#1.png',
        content_type='image/png',
        body=stream,
        size_bytes=11,
    )

    assert len(fake_client.upload_calls) == 1
    assert fake_client.upload_calls[0]['bucket'] == 'media-bucket'
    assert fake_client.upload_calls[0]['key'] == 'generated/My File#1.png'
    assert fake_client.upload_calls[0]['content_type'] == 'image/png'
    assert fake_client.upload_calls[0]['payload'] == b'image-bytes'
    assert stored.provider == 's3'
    assert stored.bucket == 'media-bucket'
    assert stored.key == 'generated/My File#1.png'
    assert stored.url == 'https://cdn.test/media/generated/My%20File%231.png'


def test_upload_object_maps_client_errors_to_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ClientError({'Error': {'Code': '500', 'Message': 'boom'}}, 'Upload')
    storage = _storage(FakeS3Client(upload_error=error), monkeypatch)

    with pytest.raises(StorageError, match='Failed to upload object to storage'):
        storage.upload_object(
            key='generated/file.png',
            content_type='image/png',
            body=BytesIO(b'image-bytes'),
            size_bytes=11,
        )


def test_delete_object_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeS3Client()
    storage = _storage(fake_client, monkeypatch)

    storage.delete_object(key='generated/file.png')

    assert fake_client.delete_calls == [{'bucket': 'media-bucket', 'key': 'generated/file.png'}]


def test_delete_object_maps_boto_errors_to_storage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delete_error = ClientError({'Error': {'Code': '500', 'Message': 'delete failed'}}, 'Delete')
    storage = _storage(FakeS3Client(delete_error=delete_error), monkeypatch)

    with pytest.raises(StorageError, match='Failed to delete object from storage'):
        storage.delete_object(key='generated/file.png')
