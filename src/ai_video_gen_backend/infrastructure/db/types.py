from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.type_api import TypeEngine

JSONType: TypeEngine[object] = sa.JSON().with_variant(JSONB(), 'postgresql')
