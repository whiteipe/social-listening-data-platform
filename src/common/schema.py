from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime


def hash_author(author_id: str | None, salt: str) -> str | None:
    if not author_id:
        return None
    return hashlib.sha256(f"{salt}:{author_id}".encode()).hexdigest()[:16]


def make_row(*, source: str, mention_id: str, published_at: datetime, text: str | None,
             url: str | None, query_group: str, author_id: str | None = None,
             language: str | None = None, engagement: int | None = None,
             reach: int | None = None, metrics: dict | None = None, salt: str = "") -> dict:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    published_at = published_at.astimezone(UTC)
    return {
        "source": source,
        "mention_id": str(mention_id),
        "published_at": published_at.isoformat(),
        "date": published_at.date().isoformat(),
        "text": (text or "").strip(),
        "author_hash": hash_author(author_id, salt),
        "url": url,
        "query_group": query_group,
        "language": language,
        "engagement": engagement,
        "reach": reach,
        "metrics": json.dumps(metrics or {}, ensure_ascii=False),
        "_loaded_at": datetime.now(UTC).isoformat(),
    }
