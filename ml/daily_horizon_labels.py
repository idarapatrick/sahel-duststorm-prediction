"""Build date-aware day+0/day+1/day+2 targets from daily MODIS labels."""

from __future__ import annotations

from typing import Iterable

import numpy as np


def build_daily_horizon_targets(
    sample_dates: Iterable,
    cell_ids: Iterable,
    daily_labels: Iterable,
) -> tuple[np.ndarray, np.ndarray]:
    """Return `(targets, valid_mask)` with shape `(N, 3)`.

    Inputs must retain one calendar date and stable grid-cell identifier per
    sample. A target is valid only when the same grid cell has a real MODIS
    label on reference day + offset. Missing satellite days remain masked;
    they are never interpolated or filled.
    """
    dates = np.asarray(sample_dates, dtype="datetime64[D]")
    cells = np.asarray(cell_ids)
    labels = np.asarray(daily_labels, dtype=np.float32)
    if not (len(dates) == len(cells) == len(labels)):
        raise ValueError("sample_dates, cell_ids and daily_labels must have equal length")

    lookup = {
        (cells[i].item() if hasattr(cells[i], "item") else cells[i], dates[i]): labels[i]
        for i in range(len(labels))
        if not np.isnan(labels[i])
    }
    targets = np.full((len(labels), 3), np.nan, dtype=np.float32)
    valid = np.zeros((len(labels), 3), dtype=bool)
    for i, (date, cell) in enumerate(zip(dates, cells)):
        cell_key = cell.item() if hasattr(cell, "item") else cell
        for offset in range(3):
            value = lookup.get((cell_key, date + np.timedelta64(offset, "D")))
            if value is not None:
                targets[i, offset] = value
                valid[i, offset] = True
    return targets, valid


def save_date_aware_batch(path, atmospheric, surface, labels, years, sample_dates, cell_ids):
    """Persist the identifiers required to construct future daily targets."""
    np.savez_compressed(
        path,
        X_atm=np.asarray(atmospheric, dtype=np.float32),
        X_surf=np.asarray(surface, dtype=np.float32),
        y=np.asarray(labels, dtype=np.float32),
        years=np.asarray(years, dtype=np.int16),
        sample_dates=np.asarray(sample_dates, dtype="datetime64[D]"),
        cell_ids=np.asarray(cell_ids),
    )
