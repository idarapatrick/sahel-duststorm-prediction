"""Store and select field-level evidence used by central dust predictions.

The module gives each environmental value its own provider, measurement time,
availability time, and semantic kind. Prediction revisions can therefore be
reproduced without treating forecasts, analyses, and observations as the same
kind of information.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from history_store import _postgres_connection, _using_postgres

VALID_KINDS = {
    "observation",
    "analysis",
    "forecast",
    "delayed_observation",
    "fallback",
    "missing",
}


def _utc(value: datetime | str | None) -> datetime | None:
    """Return an aware UTC datetime from a provider timestamp."""
    if value is None:
        return None
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceRecord:
    """One model input value with enough provenance for historical replay."""

    variable_name: str
    value: float | None
    unit: str | None
    provider: str
    evidence_kind: str
    available_at: datetime | str
    measured_at: datetime | str | None = None
    availability_is_estimated: bool = True
    retrieved_at: datetime | str = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    forecast_issued_at: datetime | str | None = None
    forecast_target_at: datetime | str | None = None
    quality_status: str = "valid"
    is_fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate distinctions that protect the replay process from leakage."""
        if self.evidence_kind not in VALID_KINDS:
            raise ValueError(f"Unsupported evidence kind: {self.evidence_kind}")
        if self.evidence_kind == "forecast" and self.forecast_target_at is None:
            raise ValueError("Forecast evidence requires forecast_target_at")
        if self.value is not None and not math.isfinite(float(self.value)):
            raise ValueError(f"{self.variable_name} must be finite")

    def normalized(self) -> dict[str, Any]:
        """Return a deterministic representation for storage and hashing."""
        item = asdict(self)
        for name in (
            "available_at",
            "measured_at",
            "retrieved_at",
            "forecast_issued_at",
            "forecast_target_at",
        ):
            timestamp = _utc(item[name])
            item[name] = timestamp.isoformat() if timestamp else None
        if item["value"] is not None:
            item["value"] = round(float(item["value"]), 8)
        return item

    def eligible_at(self, issued_at: datetime | str) -> bool:
        """Report whether the value was available at the prediction issue time."""
        return bool(_utc(self.available_at) <= _utc(issued_at))


def evidence_fingerprint(records: Iterable[EvidenceRecord]) -> str:
    """Hash evidence identity and values to suppress identical model reruns."""
    material = []
    for record in records:
        item = record.normalized()
        item.pop("retrieved_at", None)
        # Availability is retained for replay but does not make unchanged
        # provider values a new model input on every poll.
        item.pop("available_at", None)
        item.pop("availability_is_estimated", None)
        material.append(item)
    material.sort(
        key=lambda item: (
            item["variable_name"],
            item["provider"],
            item.get("measured_at") or item.get("forecast_target_at") or "",
        )
    )
    encoded = json.dumps(
        material, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_summary(records: Iterable[EvidenceRecord]) -> dict[str, Any]:
    """Calculate completeness and source composition without implying confidence."""
    items = list(records)
    expected = len(items)
    available = sum(
        record.value is not None and record.quality_status not in {"missing", "invalid"}
        for record in items
    )
    observed = sum(
        record.value is not None
        and record.evidence_kind in {"observation", "delayed_observation"}
        for record in items
    )
    forecast = sum(
        record.value is not None and record.evidence_kind == "forecast"
        for record in items
    )
    fallback = sum(record.is_fallback for record in items)
    denominator = expected or 1
    return {
        "expected_values": expected,
        "available_values": available,
        "input_completeness": round(available / denominator, 4),
        "observed_fraction": round(observed / denominator, 4),
        "forecast_fraction": round(forecast / denominator, 4),
        "fallback_count": fallback,
    }


def replay_eligible(
    records: Iterable[EvidenceRecord], issued_at: datetime | str
) -> list[EvidenceRecord]:
    """Filter evidence to values known at a historical prediction time."""
    return [record for record in records if record.eligible_at(issued_at)]


def records_from_prediction(result: dict[str, Any]) -> list[EvidenceRecord]:
    """Convert a prediction's provider manifest into normalized evidence rows."""
    provenance = result["evidence_provenance"]
    retrieved_at = provenance["retrieved_at"]
    records: list[EvidenceRecord] = []
    atmospheric = provenance["atmospheric"]
    series = atmospheric["series"]
    units = {
        "wind_speed_10m": "m/s",
        "wind_direction_10m": "degrees",
        "temperature_2m": "degrees_celsius",
        "surface_pressure": "hPa",
        "boundary_layer_height": "m",
        "precipitation": "mm",
        "dewpoint_2m": "degrees_celsius",
    }
    for variable_name, unit in units.items():
        values = series[variable_name]
        valid_values = [float(value) for value in values if value is not None]
        representative = (
            sum(valid_values) / len(valid_values) if valid_values else None
        )
        records.append(
            EvidenceRecord(
                variable_name=variable_name,
                value=representative,
                unit=unit,
                provider=atmospheric["source"],
                evidence_kind="forecast",
                available_at=atmospheric["available_at"],
                availability_is_estimated=atmospheric[
                    "availability_is_estimated"
                ],
                retrieved_at=retrieved_at,
                forecast_target_at=atmospheric["forecast_target_at"],
                quality_status="valid" if valid_values else "missing",
                metadata={
                    "aggregation": "mean for catalogue; exact series retained",
                    "timestamps": series["timestamps"],
                    "values": values,
                },
            )
        )

    surface_values = {
        "soil_moisture": (
            result["surface_data"]["soil_moisture"],
            "m3/m3",
            provenance["soil_moisture"],
        ),
        "vegetation_water_content": (
            result["surface_data"]["vegetation_water_content"],
            "kg/m2",
            provenance["vegetation_water_content"],
        ),
        "previous_day_aod": (
            result["surface_data"]["prev_day_aod"],
            "unitless",
            provenance["previous_day_aod"],
        ),
    }
    for variable_name, (value, unit, source) in surface_values.items():
        available = source["available"]
        measured_at = source.get("observed_at")
        if measured_at and len(measured_at) == 10:
            measured_at = f"{measured_at}T00:00:00Z"
        records.append(
            EvidenceRecord(
                variable_name=variable_name,
                value=float(value) if available else None,
                unit=unit,
                provider=source.get("source") or "unavailable",
                evidence_kind=source["kind"],
                measured_at=measured_at,
                available_at=source["available_at"],
                availability_is_estimated=source["availability_is_estimated"],
                retrieved_at=retrieved_at,
                forecast_target_at=source.get("forecast_target_at"),
                quality_status="valid" if available else "missing",
                is_fallback=source.get("is_fallback", False),
            )
        )
    return records


def latest_fingerprint(lat: float, lon: float, target_date: str) -> str | None:
    """Return the fingerprint of the latest stored revision for a target."""
    if not _using_postgres():
        return None
    with _postgres_connection() as connection:
        row = connection.execute(
            """SELECT p.evidence_fingerprint
               FROM prediction_snapshots p
               WHERE p.target_date=%s
                 AND p.lat BETWEEN %s AND %s AND p.lon BETWEEN %s AND %s
                 AND EXISTS (
                   SELECT 1 FROM prediction_evidence_links link
                   WHERE link.snapshot_id=p.id
                 )
               ORDER BY p.revision_number DESC, p.recorded_at DESC LIMIT 1""",
            (target_date, lat - 0.001, lat + 0.001, lon - 0.001, lon + 0.001),
        ).fetchone()
    return row["evidence_fingerprint"] if row else None


def persist_and_link_evidence(
    snapshot_id: str,
    lat: float,
    lon: float,
    location_name: str,
    records: Iterable[EvidenceRecord],
) -> list[str]:
    """Upsert evidence and link the exact values to an immutable snapshot."""
    if not _using_postgres():
        return []
    from psycopg.types.json import Jsonb

    evidence_ids: list[str] = []
    with _postgres_connection() as connection:
        location = connection.execute(
            """INSERT INTO locations(lat,lon,name) VALUES (%s,%s,%s)
               ON CONFLICT(lat,lon) DO UPDATE SET name=EXCLUDED.name
               RETURNING id""",
            (lat, lon, location_name),
        ).fetchone()
        for position, record in enumerate(records):
            item = record.normalized()
            measured = _utc(item["measured_at"])
            available = _utc(item["available_at"])
            retrieved = _utc(item["retrieved_at"])
            source_age = (
                int((retrieved - measured).total_seconds())
                if measured is not None and retrieved is not None
                else None
            )
            row = connection.execute(
                """INSERT INTO environmental_evidence
                   (id,location_id,variable_name,value,unit,provider,evidence_kind,
                    measured_at,available_at,availability_is_estimated,retrieved_at,
                    forecast_issued_at,forecast_target_at,quality_status,is_fallback,
                    source_age_seconds,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (
                     location_id,variable_name,provider,evidence_kind,
                     (coalesce(measured_at, '-infinity'::timestamptz)),
                     (coalesce(forecast_issued_at, '-infinity'::timestamptz)),
                     (coalesce(forecast_target_at, '-infinity'::timestamptz)),
                     available_at
                   ) DO UPDATE SET
                     value=EXCLUDED.value,
                     quality_status=EXCLUDED.quality_status,
                     metadata=EXCLUDED.metadata
                   RETURNING id""",
                (
                    str(uuid.uuid4()),
                    location["id"],
                    item["variable_name"],
                    item["value"],
                    item["unit"],
                    item["provider"],
                    item["evidence_kind"],
                    measured,
                    available,
                    item["availability_is_estimated"],
                    retrieved,
                    _utc(item["forecast_issued_at"]),
                    _utc(item["forecast_target_at"]),
                    item["quality_status"],
                    item["is_fallback"],
                    source_age,
                    Jsonb(item["metadata"]),
                ),
            ).fetchone()
            evidence_id = str(row["id"])
            evidence_ids.append(evidence_id)
            connection.execute(
                """INSERT INTO prediction_evidence_links
                   (snapshot_id,evidence_id,model_feature,feature_position)
                   VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (snapshot_id, evidence_id, item["variable_name"], position),
            )
    return evidence_ids


def query_snapshot_evidence(snapshot_id: str) -> list[dict[str, Any]]:
    """Return user-safe provenance for every value linked to a prediction."""
    if not _using_postgres():
        return []
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT e.variable_name,e.value,e.unit,e.provider,e.evidence_kind,
                      e.measured_at,e.available_at,e.availability_is_estimated,
                      e.retrieved_at,e.forecast_issued_at,e.forecast_target_at,
                      e.quality_status,e.is_fallback,e.source_age_seconds
               FROM prediction_evidence_links link
               JOIN environmental_evidence e ON e.id=link.evidence_id
               WHERE link.snapshot_id=%s
               ORDER BY link.feature_position,e.variable_name""",
            (snapshot_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in (
            "measured_at",
            "available_at",
            "retrieved_at",
            "forecast_issued_at",
            "forecast_target_at",
        ):
            if item.get(key):
                item[key] = item[key].isoformat()
        result.append(item)
    return result
