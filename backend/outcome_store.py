"""Collect delayed MODIS labels used to evaluate issued predictions.

Outcomes are stored only when Earth Engine returns a valid daily AOD value.
Missing or masked satellite pixels remain absent rather than becoming negative
dust labels.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any

from data_pipeline import _fetch_modis_aod_gee
from history_store import _postgres_connection, _using_postgres

MODIS_DUST_EVENT_THRESHOLD = float(
    os.getenv("MODIS_DUST_EVENT_THRESHOLD", "0.7")
)


def store_modis_outcome(
    lat: float,
    lon: float,
    location_name: str,
    target_date: date,
    aod: float,
    *,
    available_at: datetime | None = None,
) -> bool:
    """Persist one verified daily label using the training threshold."""
    if not _using_postgres():
        return False
    from psycopg.types.json import Jsonb

    available = available_at or datetime.now(timezone.utc)
    with _postgres_connection() as connection:
        location = connection.execute(
            """INSERT INTO locations(lat,lon,name) VALUES (%s,%s,%s)
               ON CONFLICT(lat,lon) DO UPDATE SET name=EXCLUDED.name
               RETURNING id""",
            (lat, lon, location_name),
        ).fetchone()
        row = connection.execute(
            """INSERT INTO prediction_outcomes
               (id,location_id,target_date,dust_event,label_value,provider,
                measured_at,available_at,metadata)
               VALUES (%s,%s,%s,%s,%s,'modis-mcd19a2',%s,%s,%s)
               ON CONFLICT(location_id,target_date,provider) DO NOTHING
               RETURNING id""",
            (
                str(uuid.uuid4()),
                location["id"],
                target_date,
                aod > MODIS_DUST_EVENT_THRESHOLD,
                aod,
                datetime.combine(
                    target_date, datetime.min.time(), tzinfo=timezone.utc
                ),
                available,
                Jsonb({"aod_threshold": MODIS_DUST_EVENT_THRESHOLD}),
            ),
        ).fetchone()
    return row is not None


async def collect_recent_outcomes(
    lookback_days: int = 7,
) -> dict[str, int]:
    """Backfill newly published MODIS labels for recent prediction targets."""
    if not _using_postgres():
        return {"checked": 0, "stored": 0}
    with _postgres_connection() as connection:
        candidates = connection.execute(
            """SELECT distinct on (
                   round(p.lat::numeric,3),round(p.lon::numeric,3),p.target_date
                 )
                      p.lat,p.lon,p.location_name,p.target_date
               FROM prediction_snapshots p
               WHERE p.target_date between current_date-%s and current_date-1
                 AND NOT EXISTS (
                   SELECT 1 FROM prediction_outcomes o
                   JOIN locations l ON l.id=o.location_id
                   WHERE o.provider='modis-mcd19a2'
                     AND o.target_date=p.target_date
                     AND abs(l.lat-p.lat)<=0.001 AND abs(l.lon-p.lon)<=0.001
                 )
               ORDER BY round(p.lat::numeric,3),round(p.lon::numeric,3),
                        p.target_date,p.recorded_at desc""",
            (lookback_days,),
        ).fetchall()
    loop = asyncio.get_running_loop()
    semaphore = asyncio.Semaphore(4)

    async def collect(candidate: dict[str, Any]) -> int:
        target_date = candidate["target_date"]
        target_datetime = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc
        )
        lat = float(candidate["lat"])
        lon = float(candidate["lon"])
        async with semaphore:
            aod = await loop.run_in_executor(
                None, _fetch_modis_aod_gee, lat, lon, target_datetime
            )
        if aod is None:
            return 0
        return int(
            store_modis_outcome(
                lat,
                lon,
                candidate["location_name"],
                target_date,
                float(aod),
            )
        )

    results = await asyncio.gather(
        *(collect(dict(candidate)) for candidate in candidates)
    )
    return {"checked": len(candidates), "stored": sum(results)}
