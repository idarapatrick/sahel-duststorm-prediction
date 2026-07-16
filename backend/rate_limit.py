"""Database-backed fixed-window rate limiting shared by every web instance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from history_store import _postgres_connection, _using_postgres


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__("Too many requests")


def enforce_rate_limit(identity: str, action: str, limit: int, window_seconds: int) -> None:
    if not _using_postgres():
        return
    now = datetime.now(timezone.utc)
    epoch = int(now.timestamp())
    window_epoch = epoch - (epoch % window_seconds)
    window_start = datetime.fromtimestamp(window_epoch, tz=timezone.utc)
    bucket = hashlib.sha256(identity.encode()).hexdigest()
    with _postgres_connection() as connection:
        row = connection.execute(
            """INSERT INTO api_rate_limits(bucket_key,action,window_started_at,request_count)
               VALUES (%s,%s,%s,1)
               ON CONFLICT(bucket_key,action,window_started_at)
               DO UPDATE SET request_count=api_rate_limits.request_count+1
               RETURNING request_count""",
            (bucket, action, window_start),
        ).fetchone()
    if row["request_count"] > limit:
        raise RateLimitExceeded(max(1, window_seconds - (epoch - window_epoch)))

