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

Progressive refinement remains separate from horizon prediction. It repeatedly evaluates the same target calendar day as more of its 72-hour atmospheric window changes from forecast data to observations. This produces a probability trajectory and data-completeness measure; it does not create new forecast horizons.

Production reinforcement requires a scheduled server-side worker over persisted monitored locations. A browser timer is only a foreground convenience and cannot provide offline monitoring.

## Current dashboard conditions

Open-Meteo supplies current temperature, humidity, apparent temperature, precipitation, pressure, wind and shallow soil moisture. MODIS/GEE supplies AOD and SMAP/GEE supplies enhanced surface inputs when available. Current weather values describe conditions at the selected location; they are not themselves per-feature causal attribution.
