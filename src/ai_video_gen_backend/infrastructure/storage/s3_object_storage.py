from __future__ import annotations

from typing import BinaryIO
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from ai_video_gen_backend.domain.collection_item import StorageError, StoredObject


class S3ObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        public_base_url: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        secure: bool,
    ) -> None:
        self._bucket = bucket
        self._public_base_url = public_base_url.rstrip('/')
        self._client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            use_ssl=secure,
            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        )

    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject:
        try:
            body.seek(0)
            self._client.upload_fileobj(
                body,
                self._bucket,
                key,
                ExtraArgs={'ContentType': content_type},
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError('Failed to upload object to storage') from exc

        return StoredObject(
            provider='s3',
            bucket=self._bucket,
            key=key,
            url=self._build_public_url(key=key),
            mime_type=content_type,
            size_bytes=size_bytes,
        )

    def delete_object(self, *, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError('Failed to delete object from storage') from exc

    def _build_public_url(self, *, key: str) -> str:
        encoded_key = quote(key, safe='/')
        return f'{self._public_base_url}/{encoded_key}'
