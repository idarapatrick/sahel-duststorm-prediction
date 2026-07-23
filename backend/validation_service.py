"""Evaluate stored prediction revisions with leakage-safe time rules.

The service scores only revisions whose linked evidence was available at issue
time. It reports probability quality, threshold behaviour, lead-time and
failure slices, plus persistence, physical-threshold, and AOD-only baselines.
It does not retrain or alter the deployed model.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from history_store import _postgres_connection, _using_postgres


@dataclass(frozen=True)
class ValidationCase:
    """One issued probability paired with a later verified daily outcome."""

    snapshot_id: str
    location_id: str
    location_name: str
    target_date: date
    issued_at: datetime
    probability: float
    outcome: bool
    lead_hours: float
    season: str
    fallback_used: bool
    completeness: float
    evidence: dict[str, float | None]
    previous_outcome: bool | None = None


def sahel_season(target_date: date) -> str:
    """Return a broad Sahel season used for failure-slice reporting."""
    if target_date.month in {11, 12, 1, 2}:
        return "dry"
    if target_date.month in {6, 7, 8, 9}:
        return "wet"
    return "transition"


def _rank_auc(probabilities: list[float], outcomes: list[bool]) -> float | None:
    """Calculate ROC-AUC from pairwise ranking without external dependencies."""
    positive = [p for p, y in zip(probabilities, outcomes) if y]
    negative = [p for p, y in zip(probabilities, outcomes) if not y]
    if not positive or not negative:
        return None
    wins = sum(
        1.0 if pos > neg else 0.5 if pos == neg else 0.0
        for pos in positive
        for neg in negative
    )
    return wins / (len(positive) * len(negative))


def _average_precision(probabilities: list[float], outcomes: list[bool]) -> float | None:
    """Calculate area under the stepwise precision-recall curve."""
    positives = sum(outcomes)
    if positives == 0:
        return None
    ordered = sorted(zip(probabilities, outcomes), reverse=True)
    true_positives = 0
    precision_sum = 0.0
    for rank, (_, outcome) in enumerate(ordered, start=1):
        if outcome:
            true_positives += 1
            precision_sum += true_positives / rank
    return precision_sum / positives


def probability_metrics(
    probabilities: Iterable[float],
    outcomes: Iterable[bool],
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Return discrimination, calibration, and alert-threshold metrics."""
    probs = [min(1.0, max(0.0, float(value))) for value in probabilities]
    labels = [bool(value) for value in outcomes]
    if not probs or len(probs) != len(labels):
        return {"count": 0}
    predicted = [value >= threshold for value in probs]
    tp = sum(p and y for p, y in zip(predicted, labels))
    fp = sum(p and not y for p, y in zip(predicted, labels))
    tn = sum(not p and not y for p, y in zip(predicted, labels))
    fn = sum(not p and y for p, y in zip(predicted, labels))
    epsilon = 1e-15
    brier = sum((p - float(y)) ** 2 for p, y in zip(probs, labels)) / len(probs)
    log_loss = -sum(
        float(y) * math.log(max(p, epsilon))
        + (1.0 - float(y)) * math.log(max(1.0 - p, epsilon))
        for p, y in zip(probs, labels)
    ) / len(probs)
    bins = []
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        members = [
            (p, y)
            for p, y in zip(probs, labels)
            if lower <= p < lower + 0.2 or (lower == 0.8 and p == 1.0)
        ]
        if members:
            bins.append(
                {
                    "range": [lower, round(lower + 0.2, 1)],
                    "count": len(members),
                    "mean_probability": round(
                        sum(item[0] for item in members) / len(members), 4
                    ),
                    "event_rate": round(
                        sum(item[1] for item in members) / len(members), 4
                    ),
                }
            )
    return {
        "count": len(probs),
        "event_count": sum(labels),
        "brier_score": round(brier, 6),
        "log_loss": round(log_loss, 6),
        "roc_auc": (
            round(value, 6)
            if (value := _rank_auc(probs, labels)) is not None
            else None
        ),
        "pr_auc": (
            round(value, 6)
            if (value := _average_precision(probs, labels)) is not None
            else None
        ),
        "precision": round(tp / (tp + fp), 6) if tp + fp else None,
        "recall": round(tp / (tp + fn), 6) if tp + fn else None,
        "specificity": round(tn / (tn + fp), 6) if tn + fp else None,
        "false_alert_rate": round(fp / (fp + tn), 6) if fp + tn else None,
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "calibration_bins": bins,
    }


def _physical_baseline(case: ValidationCase) -> float:
    """Return a transparent wind, dryness, and aerosol comparison score."""
    wind = case.evidence.get("wind_speed_10m")
    soil = case.evidence.get("soil_moisture")
    aod = case.evidence.get("previous_day_aod")
    score = 0.1
    if wind is not None:
        score += 0.25 if wind >= 8 else 0.12 if wind >= 5 else 0
    if soil is not None:
        score += 0.25 if soil < 0.1 else 0.1 if soil < 0.2 else 0
    if aod is not None:
        score += 0.3 if aod >= 0.5 else 0.18 if aod >= 0.3 else 0
    return min(score, 0.95)


def _aod_baseline(case: ValidationCase) -> float:
    """Map available AOD to a bounded comparison probability."""
    aod = case.evidence.get("previous_day_aod")
    return min(0.95, max(0.05, float(aod))) if aod is not None else 0.5


class ValidationEvaluator:
    """Compare model revisions and baselines across operational failure slices."""

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def evaluate(self, cases: Iterable[ValidationCase]) -> dict[str, Any]:
        """Calculate overall, baseline, and stratified validation results."""
        rows = list(cases)
        overall = probability_metrics(
            [case.probability for case in rows],
            [case.outcome for case in rows],
            self.threshold,
        )
        baselines = {
            "physical_threshold": probability_metrics(
                [_physical_baseline(case) for case in rows],
                [case.outcome for case in rows],
                self.threshold,
            ),
            "aod_only": probability_metrics(
                [_aod_baseline(case) for case in rows],
                [case.outcome for case in rows],
                self.threshold,
            ),
        }
        persistence_cases = [
            case for case in rows if case.previous_outcome is not None
        ]
        baselines["previous_day_persistence"] = probability_metrics(
            [0.9 if case.previous_outcome else 0.1 for case in persistence_cases],
            [case.outcome for case in persistence_cases],
            self.threshold,
        )
        slices: dict[str, dict[str, Any]] = {}
        groups: dict[str, list[ValidationCase]] = defaultdict(list)
        for case in rows:
            groups[f"location:{case.location_name}"].append(case)
            groups[f"season:{case.season}"].append(case)
            groups[
                "source:fallback" if case.fallback_used else "source:primary"
            ].append(case)
            if case.lead_hours >= 36:
                lead = "36h_or_more"
            elif case.lead_hours >= 18:
                lead = "18_to_36h"
            elif case.lead_hours >= 6:
                lead = "6_to_18h"
            else:
                lead = "under_6h"
            groups[f"lead:{lead}"].append(case)
        for name, members in groups.items():
            slices[name] = probability_metrics(
                [case.probability for case in members],
                [case.outcome for case in members],
                self.threshold,
            )
        return {
            "threshold": self.threshold,
            "overall": overall,
            "baselines": baselines,
            "slices": slices,
        }


def load_leakage_safe_cases() -> list[ValidationCase]:
    """Load labelled revisions whose evidence was available when issued."""
    if not _using_postgres():
        raise RuntimeError("Stored validation requires PostgreSQL")
    with _postgres_connection() as connection:
        rows = connection.execute(
            """SELECT p.id snapshot_id,l.id location_id,p.location_name,
                      p.target_date,p.recorded_at,p.probability,o.dust_event,
                      p.input_completeness,
                      coalesce(bool_or(e.is_fallback),false) fallback_used,
                      count(*) filter(where e.available_at>p.recorded_at) leaked_values,
                      jsonb_object_agg(e.variable_name,e.value)
                        filter(where e.variable_name is not null) evidence
               FROM prediction_snapshots p
               JOIN locations l
                 ON abs(l.lat-p.lat)<=0.001 AND abs(l.lon-p.lon)<=0.001
               JOIN prediction_outcomes o
                 ON o.location_id=l.id AND o.target_date=p.target_date
               LEFT JOIN prediction_evidence_links link ON link.snapshot_id=p.id
               LEFT JOIN environmental_evidence e ON e.id=link.evidence_id
               GROUP BY p.id,l.id,o.dust_event
               HAVING count(*) filter(where e.available_at>p.recorded_at)=0
               ORDER BY l.id,p.target_date,p.recorded_at""",
        ).fetchall()
    previous_by_location: dict[str, tuple[date, bool]] = {}
    cases = []
    for row in rows:
        target = row["target_date"]
        issued = row["recorded_at"]
        midnight = datetime.combine(target, datetime.min.time(), tzinfo=issued.tzinfo)
        key = str(row["location_id"])
        previous = previous_by_location.get(key)
        previous_outcome = (
            previous[1]
            if previous is not None and previous[0] < target
            else None
        )
        cases.append(
            ValidationCase(
                snapshot_id=str(row["snapshot_id"]),
                location_id=key,
                location_name=row["location_name"],
                target_date=target,
                issued_at=issued,
                probability=float(row["probability"]),
                outcome=bool(row["dust_event"]),
                lead_hours=(midnight - issued).total_seconds() / 3600,
                season=sahel_season(target),
                fallback_used=bool(row["fallback_used"]),
                completeness=float(row["input_completeness"] or 0),
                evidence=dict(row["evidence"] or {}),
                previous_outcome=previous_outcome,
            )
        )
        if previous is None or previous[0] < target:
            previous_by_location[key] = (target, bool(row["dust_event"]))
    return cases


def run_stored_validation(
    model_version: str, threshold: float = 0.5
) -> dict[str, Any]:
    """Evaluate stored labelled revisions and persist reproducible results."""
    from psycopg.types.json import Jsonb

    cases = load_leakage_safe_cases()
    metrics = ValidationEvaluator(threshold).evaluate(cases)
    run_id = str(uuid.uuid4())
    configuration = {
        "method": "issuance-time historical replay of stored revisions",
        "threshold": threshold,
        "future_evidence_rule": "available_at <= recorded_at",
    }
    with _postgres_connection() as connection:
        connection.execute(
            """INSERT INTO validation_runs
               (id,model_version,completed_at,status,configuration,metrics)
               VALUES (%s,%s,now(),'completed',%s,%s)""",
            (run_id, model_version, Jsonb(configuration), Jsonb(metrics)),
        )
        for case in cases:
            connection.execute(
                """INSERT INTO validation_predictions
                   (id,validation_run_id,location_id,target_date,issued_at,
                    lead_hours,probability,predicted_event,outcome_event,season,
                    fallback_used,evidence_completeness,metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    str(uuid.uuid4()),
                    run_id,
                    case.location_id,
                    case.target_date,
                    case.issued_at,
                    case.lead_hours,
                    case.probability,
                    case.probability >= threshold,
                    case.outcome,
                    case.season,
                    case.fallback_used,
                    case.completeness,
                    Jsonb({"snapshot_id": case.snapshot_id}),
                ),
            )
    return {"validation_run_id": run_id, **metrics}
