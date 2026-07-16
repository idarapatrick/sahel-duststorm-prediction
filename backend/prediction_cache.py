"""PostgreSQL read-through response cache with a distributed single-flight lock."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from history_store import DATABASE_URL, _postgres_connection, _using_postgres

CACHE_TTL_SECONDS = max(30, int(os.getenv("PREDICTION_CACHE_TTL_SECONDS", "300")))
CACHE_BUCKET_SECONDS = max(30, int(os.getenv("PREDICTION_CACHE_BUCKET_SECONDS", "300")))
MODEL_VERSION = os.getenv("MODEL_VERSION", "single-head-current").strip()


def build_cache_key(
    lat: float,
    lon: float,
    target_date: date,
    *,
    now: datetime | None = None,
    model_version: str = MODEL_VERSION,
) -> str:
    """Group nearby coordinates and requests sharing the same input-data window."""
    instant = now or datetime.now(timezone.utc)
    bucket = int(instant.timestamp()) // CACHE_BUCKET_SECONDS
    return f"location:{lat:.3f}:{lon:.3f}:{target_date}:{model_version}:{bucket}"


def get_cached_prediction(cache_key: str) -> dict[str, Any] | None:
    if not _using_postgres():
        return None
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT payload FROM prediction_response_cache
               WHERE cache_key=%s AND expires_at > now()""",
            (cache_key,),
        ).fetchone()
    if not row:
        return None
    payload = row["payload"]
    return json.loads(payload) if isinstance(payload, str) else payload


@dataclass
class PredictionLease:
    """A session-scoped PostgreSQL advisory lock for one cache key."""

    cache_key: str
    connection: Any

    def store(
        self,
        payload: dict[str, Any],
        lat: float,
        lon: float,
        target_date: date,
        model_version: str = MODEL_VERSION,
    ) -> None:
        if self.connection is None:
            return
        from psycopg.types.json import Jsonb

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=CACHE_TTL_SECONDS)
        self.connection.execute(
            "DELETE FROM prediction_response_cache WHERE expires_at < now() - interval '1 day'"
        )
        self.connection.execute(
            """INSERT INTO prediction_response_cache
               (cache_key,lat,lon,target_date,model_version,payload,expires_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (cache_key) DO UPDATE SET payload=EXCLUDED.payload,
                 created_at=now(), expires_at=EXCLUDED.expires_at""",
            (self.cache_key, lat, lon, target_date, model_version, Jsonb(payload), expires_at),
        )
        self.connection.commit()

    def close(self) -> None:
        if self.connection is None:
            return
        try:
            self.connection.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (self.cache_key,)
            )
        finally:
            self.connection.close()


def try_acquire_prediction_lease(cache_key: str) -> PredictionLease | None:
    if not _using_postgres():
        return PredictionLease(cache_key, None)
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("Install psycopg[binary] to use prediction caching") from exc
    connection = psycopg.connect(
        DATABASE_URL, row_factory=dict_row, connect_timeout=10, autocommit=False
    )
    row = connection.execute(
        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired",
        (cache_key,),
    ).fetchone()
    if not row["acquired"]:
        connection.close()
        return None
    return PredictionLease(cache_key, connection)
