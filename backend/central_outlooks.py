"""Shared calendar-day contract for validated central predictions.

The deployed single-output classifier supports independent current-day and
next-day evaluation. Day+2 remains excluded until the separate multi-horizon
model completes evaluation and export.
"""

from __future__ import annotations

from datetime import date, timedelta


CENTRAL_OUTLOOK_DAYS = 2


def central_target_dates(reference_date: date) -> list[date]:
    """Return the ordered daily targets exposed by the dashboard."""
    return [
        reference_date + timedelta(days=offset)
        for offset in range(CENTRAL_OUTLOOK_DAYS)
    ]
