# SahelWatch prediction architecture

## Supervision determines forecast cadence

MODIS AOD supplies one dust-event label per grid cell per calendar day. The system therefore predicts daily horizons, not independent +12h/+24h/+36h/+48h clock-hour targets. Sub-daily labels are not interpolated or synthesized.

## Three model outputs

One 72-hour atmospheric sequence spans `T-60h` to `T+12h`, aligned to the reference calendar day's midnight. One surface vector contains soil moisture, vegetation water content, previous-day AOD, latitude, longitude and month encoding.

The atmospheric LSTM encoder and surface encoder produce a shared cross-modal embedding. Three lightweight binary heads read that same embedding:

- `day+0`: dust outcome on the reference calendar day; approximately the next 12–24 hours because the input includes forecast data through `T+12h`;
- `day+1`: outcome one calendar day later; approximately 24–48 hours;
- `day+2`: outcome two calendar days later; approximately 48–72 hours.

These lead-time descriptions are approximate ranges, not clock-hour ground truth.

## Date-aware training labels

Every extracted sample must retain:

- `sample_date`, the reference day used by the day-level extraction;
- `cell_id`, a stable grid-cell identifier;
- the real MODIS-derived daily label.

For sample `(cell, date)` the three targets are joined from:

```text
day+0 = label(cell, date)
day+1 = label(cell, date + 1 calendar day)
day+2 = label(cell, date + 2 calendar days)
```

Missing MODIS dates remain masked and contribute no training loss. The join cannot be performed reliably from the old flattened arrays because those arrays preserved only year, not per-sample date.

Implementation:

- `ml/daily_horizon_labels.py` builds targets and valid-label masks;
- `ml/multi_horizon_model.py` provides the three heads and masked loss;
- future preprocessing batches must use `save_date_aware_batch` or preserve equivalent `sample_dates` and `cell_ids` arrays.

## Backend inference contract

`GET /api/v1/predict/daily-horizons` builds one feature payload and makes one call to `MULTI_HORIZON_MODEL_URL`. The model service must return:

```json
{
  "model_version": "daily-horizons-v1",
  "horizons": {
    "day_0": {"probability": 0.18, "dust_event": false},
    "day_1": {"probability": 0.47, "dust_event": false},
    "day_2": {"probability": 0.63, "dust_event": true}
  }
}
```

The backend adds target dates, risk levels, current Open-Meteo conditions and surface values. It archives each horizon separately. When no multi-horizon model URL is configured, the endpoint returns HTTP 501 rather than falling back to fabricated shifted-window outputs.

## Progressive refinement

Progressive refinement remains separate from horizon prediction. It evaluates the same target calendar day only when a provider returns meaningfully different evidence. Open-Meteo Forecast API values remain classified as forecasts even after their target timestamps pass. CAMS values are analyses, while SMAP and MODIS values are delayed observations. The system never infers observation status from the clock.

Production reinforcement requires a scheduled server-side worker over persisted monitored locations. A browser timer is only a foreground convenience and cannot provide offline monitoring.

## Current dashboard conditions

Open-Meteo supplies the nearest current weather-model timestep for temperature, humidity, apparent temperature, precipitation, pressure, wind and shallow soil moisture. MODIS/GEE supplies delayed AOD and SMAP/GEE supplies delayed surface inputs when available. CAMS analysis supplies AOD when a valid recent MODIS value is absent. Current values describe conditions near the selected location; they are not per-feature causal attribution.

## Evidence provenance and revision identity

Every environmental field records its provider, semantic kind, measurement
time, availability time, retrieval time, quality, fallback state and relevant
forecast target. The exact 72-hour atmospheric series is retained with its
field record. Each immutable prediction revision links to the evidence it used
and stores an evidence fingerprint, revision reason, source fractions and input
completeness.

An hourly check does not automatically mean an hourly model call. When the
fingerprint matches the latest stored revision, the worker reschedules the job
without inference or a duplicate snapshot. New results are accepted whether
their probability rises or falls.

The central worker maintains two independently stored targets for every active
forecast cell: the current calendar day and the next calendar day. The current
day is the dashboard's primary result. The next day is returned as a separate
outlook. A following-day result remains disabled because the deployed
single-head model has not been validated for that additional lead time.

## Leakage-safe validation

Historical replay follows one rule:

```text
evidence.available_at <= prediction.recorded_at
```

A satellite value measured on a target day but published later cannot be used
to reconstruct an earlier prediction. Labelled revisions are evaluated with
Brier score, log loss, ROC-AUC, PR-AUC, precision, recall, specificity,
false-alert rate and calibration bins. Results are sliced by location, season,
lead time and fallback use and compared with previous-day persistence, a
transparent wind-dryness-AOD rule, and an AOD-only baseline.

The worker checks recent issued target days for newly published MODIS outcomes.
A masked or unavailable satellite value remains unlabeled. It is never stored
as a no-event outcome. When new outcomes are stored, the worker records a new
validation run using the AOD greater than 0.7 label documented by the training
and AERONET evaluation notebooks.
