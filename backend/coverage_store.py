"""Database-backed place catalogue and shared forecast-cell queries."""

from __future__ import annotations

from math import cos, radians, sqrt
from typing import Any

from history_store import _postgres_connection, _using_postgres


FALLBACK_PLACES = [
    {"name": "Niamey", "country": "Niger", "country_code": "NE", "place_type": "city", "lat": 13.51, "lon": 2.11, "coverage_status": "operational"},
    {"name": "Sokoto", "country": "Nigeria", "country_code": "NG", "place_type": "city", "lat": 13.06, "lon": 5.24, "coverage_status": "operational"},
    {"name": "Kano", "country": "Nigeria", "country_code": "NG", "place_type": "city", "lat": 12.00, "lon": 8.52, "coverage_status": "operational"},
    {"name": "Maiduguri", "country": "Nigeria", "country_code": "NG", "place_type": "city", "lat": 11.85, "lon": 13.16, "coverage_status": "operational"},
    {"name": "Agadez", "country": "Niger", "country_code": "NE", "place_type": "city", "lat": 16.97, "lon": 7.99, "coverage_status": "operational"},
    {"name": "N'Djamena", "country": "Chad", "country_code": "TD", "place_type": "city", "lat": 12.13, "lon": 15.06, "coverage_status": "operational"},
    {"name": "Bamako", "country": "Mali", "country_code": "ML", "place_type": "city", "lat": 12.64, "lon": -8.00, "coverage_status": "operational"},
    {"name": "Timbuktu", "country": "Mali", "country_code": "ML", "place_type": "town", "lat": 16.77, "lon": -3.01, "coverage_status": "operational"},
    {"name": "Ouagadougou", "country": "Burkina Faso", "country_code": "BF", "place_type": "city", "lat": 12.36, "lon": -1.48, "coverage_status": "operational"},
    {"name": "Dakar", "country": "Senegal", "country_code": "SN", "place_type": "city", "lat": 14.69, "lon": -17.44, "coverage_status": "operational"},
    {"name": "Nouakchott", "country": "Mauritania", "country_code": "MR", "place_type": "city", "lat": 18.09, "lon": -15.98, "coverage_status": "operational"},
]


def list_covered_places(query: str | None = None, country_code: str | None = None, limit: int = 250) -> list[dict[str, Any]]:
    """Return active places. The fallback keeps the UI usable before migration 010."""
    if not _using_postgres():
        rows = FALLBACK_PLACES
        if query:
            needle = query.casefold()
            rows = [row for row in rows if needle in f"{row['name']} {row['country']}".casefold()]
        if country_code:
            rows = [row for row in rows if row["country_code"] == country_code.upper()]
        return rows[:limit]
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT p.id,p.name,p.country,p.country_code,p.place_type,p.lat,p.lon,
                      p.coverage_status,c.cell_key,c.centre_lat AS forecast_lat,
                      c.centre_lon AS forecast_lon
               FROM covered_places p JOIN forecast_grid_cells c ON c.id=p.forecast_cell_id
               WHERE p.active AND c.active
                 AND (%s IS NULL OR p.country_code=%s)
                 AND (%s IS NULL OR p.name ILIKE '%%' || %s || '%%'
                                  OR p.country ILIKE '%%' || %s || '%%')
               ORDER BY p.priority,p.country,p.name LIMIT %s""",
            (country_code, country_code, query, query, query, min(max(limit, 1), 500)),
        ).fetchall()
    return [dict(row) for row in rows]


def list_active_forecast_cells() -> list[dict[str, Any]]:
    """Return each active forecast coordinate once, regardless of place count."""
    if not _using_postgres():
        return [{"cell_key": f"fallback:{row['lat']}:{row['lon']}", "lat": row["lat"], "lon": row["lon"], "name": f"{row['name']}, {row['country']}"} for row in FALLBACK_PLACES]
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT c.cell_key,c.centre_lat AS lat,c.centre_lon AS lon,
                      min(p.name || ', ' || p.country) AS name
               FROM forecast_grid_cells c JOIN covered_places p ON p.forecast_cell_id=c.id
               WHERE c.active AND p.active
               GROUP BY c.id,c.cell_key,c.centre_lat,c.centre_lon
               ORDER BY min(p.priority),c.cell_key"""
        ).fetchall()
    return [dict(row) for row in rows]


def nearest_covered_place(lat: float, lon: float) -> dict[str, Any] | None:
    places = list_covered_places(limit=500)
    if not places:
        return None
    latitude_scale = max(0.1, cos(radians(lat)))
    return min(places, key=lambda row: sqrt((row["lat"] - lat) ** 2 + ((row["lon"] - lon) * latitude_scale) ** 2))


def coverage_status() -> dict[str, Any]:
    if not _using_postgres():
        return {"source": "fallback", "places": len(FALLBACK_PLACES), "forecast_cells": len(FALLBACK_PLACES)}
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT count(*) FILTER (WHERE p.active) AS places,
                      count(DISTINCT p.forecast_cell_id) FILTER (WHERE p.active AND c.active) AS forecast_cells,
                      count(*) FILTER (WHERE p.active AND p.coverage_status='provisional') AS provisional_places
               FROM covered_places p JOIN forecast_grid_cells c ON c.id=p.forecast_cell_id"""
        ).fetchone()
    return {"source": "postgresql", **dict(row)}
