from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Protocol


@dataclass(frozen=True, slots=True)
class StoredObject:
    provider: str
    bucket: str
    key: str
    url: str
    mime_type: str
    size_bytes: int


class StorageError(Exception):
    """Raised when object storage operations fail."""


class ObjectStoragePort(Protocol):
    def upload_object(
        self,
        *,
        key: str,
        content_type: str,
        body: BinaryIO,
        size_bytes: int,
    ) -> StoredObject: ...

    def delete_object(self, *, key: str) -> None: ...
