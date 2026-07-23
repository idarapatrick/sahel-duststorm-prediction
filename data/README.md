# SahelWatch data contract

This directory is reserved for local or DVC-managed datasets used by the preprocessing, training, and evaluation notebooks. Large source data and generated arrays are intentionally excluded from Git.

## Study domain

- Latitude: 10°N to 25°N
- Longitude: 18°W to 25°E
- Training period described by the project: 2015 to 2022
- Validation period: 2023
- Held-out test period: 2024
- Dust-event supervision: daily MODIS aerosol optical depth (AOD)

## Model inputs

### Atmospheric sequence

Each sample contains a 72-hour sequence aligned to the target calendar day, spanning approximately T-60 hours to T+12 hours. The seven atmospheric channels are:

1. east-west 10 m wind component;
2. north-south 10 m wind component;
3. 2 m air temperature;
4. surface pressure;
5. boundary-layer height;
6. total precipitation; and
7. 2 m dew-point temperature.

The expected atmospheric array shape is `(samples, 72, 7)`.

### Surface vector

The seven surface and context features are:

1. soil moisture;
2. vegetation water content;
3. previous available AOD;
4. latitude;
5. longitude;
6. sine of calendar month; and
7. cosine of calendar month.

The expected surface array shape is `(samples, 7)`.

## Labels

The operational model uses a binary daily dust-event label derived from MODIS AOD. The threshold and filtering decisions used for a particular experiment must remain recorded in the evaluation notebook and its exported results.

The pending multi-horizon extension uses three daily targets for the same grid cell:

- day+0: label on the reference calendar day;
- day+1: label one calendar day later; and
- day+2: label two calendar days later.

`ml/daily_horizon_labels.py` constructs these targets from preserved sample dates and grid-cell identifiers. Missing MODIS days are masked. They are not interpolated or converted into synthetic sub-daily labels.

## Expected processed files

Processed training archives use compressed NumPy storage and include fields such as:

```text
X_atm        float32 atmospheric sequences
X_surf       float32 surface vectors
y            float32 binary daily labels
years        integer year for temporal splitting
sample_dates calendar date for each sample
cell_ids     stable spatial-cell identifier
```

Exact file names can differ between notebook runs, but the semantic fields and shapes must be checked before training.

## Data provenance

| Variable group | Research or runtime source |
|---|---|
| Atmospheric variables | ERA5 for research extraction; Open-Meteo for deployed forecast access |
| Soil moisture | SMAP, with explicitly reported Open-Meteo fallback at runtime |
| Vegetation water content | SMAP |
| Aerosol optical depth | MODIS MCD19A2 through Google Earth Engine |
| Geographic and seasonal context | Grid coordinates and sample calendar date |

Runtime SMAP and MODIS observations can be delayed or masked by retrieval quality and cloud cover. Their actual observation dates and availability are therefore stored as provenance. A fallback value must not be described as a satellite observation.

## Repository policy

The root `.gitignore` excludes raw data, processed arrays, model weights, raster files, and common large scientific formats. This protects repository size and prevents accidental redistribution of provider data. Reproducible dataset access requires the corresponding provider permissions or the project's configured DVC remote.

No credentials, service-account documents, personally identifying information, or phone records belong in this directory.

## Related files

- `notebooks/01_preprocessing.ipynb`: preprocessing workflow
- `notebooks/02-model-evaluation.ipynb`: model definitions, training, calibration, and comparison
- `notebooks/03_aeronet_validation.ipynb`: external observational validation
- `ml/dust_model.py`: reusable dual-encoder and cross-modal-attention architecture
- `ml/daily_horizon_labels.py`: date-aware daily target construction
- `ml/multi_horizon_model.py`: pending daily multi-head extension
