from __future__ import annotations


class CollectionItemConstraintViolationError(Exception):
    """Raised when collection-item persistence violates database constraints."""
