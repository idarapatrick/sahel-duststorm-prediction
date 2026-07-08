# SahelDust: Cross-Modal Attention for Dust Emission Forecasting

A deep learning system that predicts significant dust emission events over the African Sahel 24 to 48 hours in advance using multi-modal satellite data. Built as a BSc Software Engineering capstone project at African Leadership University.

**Live Demo:** [https://saheldust-frontend.vercel.app](https://saheldust-frontend.vercel.app)

**Video Demo:** [5-minute walkthrough](https://drive.google.com/drive/folders/1L8UkDWP4soofYIxR8nKEt8P2K8rnCITg?usp=sharing)

**API Documentation:** [https://saheldust-backend.onrender.com/docs](https://saheldust-backend.onrender.com/docs)

**Model API:** [https://mavencodes-saheldust-api.hf.space/docs](https://mavencodes-saheldust-api.hf.space/docs)

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Solution Overview](#solution-overview)
3. [Architecture](#architecture)
4. [Installation and Setup](#installation-and-setup)
5. [Running the Application](#running-the-application)
6. [Testing Results](#testing-results)
7. [Analysis of Results](#analysis-of-results)
8. [Deployment Plan](#deployment-plan)
9. [Discussion](#discussion)
10. [Recommendations](#recommendations)
11. [Project Structure](#project-structure)

---

## Problem Statement

Sand and dust storms in the African Sahel kill people, destroy crops, contaminate water sources, and trigger respiratory disease outbreaks. On June 11, 2026, a severe sandstorm struck Birnin Kebbi, Nigeria with no specific early warning issued to communities. Existing dust forecasting systems require computational infrastructure that Sahelian meteorological centres do not have.

## Solution Overview

SahelDust is a three-tier early warning system:

1. **Mobile Web App** for community users showing dust risk forecasts with interactive maps and location-based alerts
2. **Desktop Dashboard** for WMO meteorological centre operators to review, confirm, or dismiss predictions before alerts are sent to communities (human-in-the-loop)
3. **SMS Alerts** for feature phone users in rural areas without internet access, triggered only after human operator confirmation

The machine learning model uses a dual-encoder architecture with cross-modal attention that fuses:
- 72-hour atmospheric sequences from ERA5 reanalysis (wind, temperature, pressure, boundary layer height, precipitation, dewpoint)
- Surface observations from SMAP (soil moisture, vegetation water content) and MODIS (aerosol optical depth)

The model was trained on 1.9 million samples across the Sahel (10N-25N, 18W-25E) from 2015 to 2022, validated on 2023, and tested on the full unsubsampled 2024 data.

---

## Architecture

```
Open-Meteo API (real-time atmospheric forecast)
     |
     v
FastAPI Backend (Render) --> Google Earth Engine (SMAP, MODIS)
     |
     v
ONNX Model API (Hugging Face Spaces)
     |
     v
FastAPI Backend --> Progressive Alert Tracker
     |                    |
     v                    v
Next.js Frontend     Supabase (PostgreSQL)
(Vercel)                  |
     |                    v
     v              SMS via Africa's Talking
Mobile + Desktop UI      (feature phones)
```

### Progressive Prediction System

The system does not make a single prediction and stop. It continuously refines predictions as the target date approaches:

- **Day 1 (48 hours before):** Uses atmospheric forecast data. All 72 hours are forecast values. Confidence is low. If probability exceeds 0.3, a WATCH alert is generated.
- **Day 2 (24 hours before):** The first 24 hours of the atmospheric window now use real observed data instead of forecast values. The remaining 48 hours are still forecast. Confidence improves. If probability exceeds 0.5, a WARNING is generated.
- **Day 3 (6 hours before):** 42 hours are real observations, 30 hours are forecast. SMAP morning soil moisture is available. This is the highest-confidence prediction. If probability exceeds 0.7, an ALERT is generated.

At any point, if real observations contradict the forecast and the probability drops, the alert is de-escalated and a cancellation message is generated.

SMS alerts to communities are only sent after a WMO operator reviews and confirms the prediction on the desktop dashboard. This human-in-the-loop design prevents false alarm fatigue.

### Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| ML Model | PyTorch, ONNX Runtime | Training and inference |
| Model API | FastAPI, Hugging Face Spaces | Serves ONNX model |
| Backend | FastAPI, Python | Data pipeline, alert tracking |
| Frontend | Next.js 14, shadcn/ui, Tailwind | Web interface |
| Maps | Leaflet / Mapbox GL | Geospatial visualization |
| Database | Supabase (PostgreSQL) | Users, subscriptions, alert logs |
| SMS | Africa's Talking | Feature phone alerts |
| Deployment | Vercel, Render, HF Spaces | Hosting |
| Data Sources | Open-Meteo, Google Earth Engine | Real-time satellite data |

---

## Installation and Setup

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- npm or yarn
- A Google Earth Engine account (optional, for SMAP/MODIS data)

### Step 1: Clone the repository

```bash
git clone https://github.com/idarapatrick/Dual-Encoder-Model-for-Sahel-Dust-Forecasting.git
cd Dual-Encoder-Model-for-Sahel-Dust-Forecasting
```

### Step 2: Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:

```
HF_SPACE_URL=https://mavencodes-saheldust-api.hf.space/predict
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
CORS_ORIGINS=http://localhost:3000,https://saheldust-frontend.vercel.app
```

### Step 3: Set up the frontend

```bash
cd ../frontend
npm install
```

Create a `.env.local` file in the `frontend/` directory:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Step 4: Set up the database

Go to [supabase.com](https://supabase.com), create a project, and run this SQL in the SQL Editor:

```sql
create table users (
  id uuid primary key default gen_random_uuid(),
  phone text unique not null,
  email text,
  location_lat float not null,
  location_lon float not null,
  location_name text,
  alert_threshold text default 'warning',
  created_at timestamptz default now()
);

create table alert_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id),
  lat float not null,
  lon float not null,
  location_name text,
  threshold text default 'warning',
  active boolean default true,
  created_at timestamptz default now()
);

create table sent_alerts (
  id uuid primary key default gen_random_uuid(),
  phone text not null,
  location_name text,
  alert_level text,
  probability float,
  message text,
  confirmed_by text,
  sent_at timestamptz default now()
);

create table prediction_log (
  id uuid primary key default gen_random_uuid(),
  lat float,
  lon float,
  location_name text,
  probability float,
  alert_level text,
  confidence_pct float,
  prediction_date text,
  created_at timestamptz default now()
);
```

---

## Running the Application

### Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload
```

The API runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.

### Start the frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

The app runs at `http://localhost:3000`.

### Deployed versions

The application is live and accessible:

- Frontend: [https://saheldust-frontend.vercel.app](https://saheldust-frontend.vercel.app)
- Backend API: [https://saheldust-backend.onrender.com/docs](https://saheldust-backend.onrender.com/docs)
- Model API: [https://mavencodes-saheldust-api.hf.space/docs](https://mavencodes-saheldust-api.hf.space/docs)

Note: Free-tier services (Render, HF Spaces) sleep after 15 minutes of inactivity. The first request after sleeping takes 30 to 60 seconds to wake up.

---

## Testing Results

### 1. Unit Testing: API Endpoint Validation

Each backend endpoint was tested with valid inputs, edge cases, and invalid inputs.

**Valid input test (Niamey, Niger):**
```
GET /api/v1/predict/location?lat=13.51&lon=2.11
Response: 200 OK
{
  "lat": 13.51,
  "lon": 2.11,
  "location_name": "Niamey, Niger",
  "probability": 0.0741,
  "risk_level": "low",
  "dust_event": false,
  "prediction_date": "2026-06-27",
  "data_source": "open-meteo+gee"
}
```

**Edge case test (boundary coordinates):**
```
GET /api/v1/predict/location?lat=10.0&lon=-18.0
Response: 200 OK (southern and western boundary of study area)

GET /api/v1/predict/location?lat=25.0&lon=25.0
Response: 200 OK (northern and eastern boundary)
```

**Invalid input test (outside Sahel):**
```
GET /api/v1/predict/location?lat=5.0&lon=2.0
Response: 400 Bad Request
{"detail": "Latitude must be between 10 and 25 (Sahel region)"}
```

### 2. Integration Testing: End-to-End Data Flow

Tested the full pipeline: Frontend sends coordinates to Backend, Backend fetches atmospheric data from Open-Meteo, fetches SMAP/MODIS from GEE, sends to HF Space Model API, returns prediction to frontend.

**Locations tested:**

| Location | Lat | Lon | Probability | Risk Level | Season |
|---|---|---|---|---|---|
| Niamey, Niger | 13.51 | 2.11 | 0.074 | Low | Wet (July) |
| Banizoumbou, Niger | 13.53 | 2.67 | 0.074 | Low | Wet (July) |
| Sokoto, Nigeria | 13.06 | 5.24 | varies | varies | Wet (July) |
| Dakar, Senegal | 14.69 | -17.44 | 0.75 | High | Dust transport (July) |
| N'Djamena, Chad | 12.13 | 15.06 | varies | varies | varies |
| Nouakchott, Mauritania | 18.09 | -15.98 | varies | varies | varies |

Low probabilities during the wet season (July) are physically correct: the West African monsoon brings moisture, vegetation grows, and dust emission is suppressed.

### 3. Progressive Prediction Testing

Called the progressive endpoint multiple times for the same location and target date to verify prediction tracking:

**First call:**
- update_count: 1, trend: "new", confidence: 34.7%, hours_real: 25/72

**Second call (5 minutes later):**
- update_count: 2, trend: "stable", confidence: 34.7%, hours_real: 25/72, prob_change: 0.0

The system correctly tracks prediction history and reports trends.

### 4. Multi-Day Forecast Testing

```
GET /api/v1/forecast?lat=13.51&lon=2.11&days=3
Response: 200 OK, returns predictions for 3 consecutive future days
```

Each day returns independent probability, risk level, and dust event classification.

### 5. Performance Testing

| Environment | First Request (cold) | Subsequent Requests | Notes |
|---|---|---|---|
| Local (M1 Mac / Linux) | 15 to 30 seconds | 5 to 10 seconds | GEE queries dominate latency |
| Render (free tier, cold start) | 60 to 90 seconds | 10 to 20 seconds | Server wake-up adds latency |
| HF Spaces (model inference only) | 1 to 2 seconds | < 1 second | ONNX inference is fast |

### 6. Cross-Browser Testing

| Browser | Desktop | Mobile | Status |
|---|---|---|---|
| Chrome 126 | Tested | Tested | Works |
| Safari 17 | Tested | Tested (iOS) | Works |
| Firefox 127 | Tested | Not tested | Works |

---

## Analysis of Results

### Alignment with Proposal Objectives

**Objective 1: Build a multi-modal deep learning model for dust prediction.**
Achieved. 12 models trained and evaluated (3 baselines, 6 neural networks, 3 Focal Loss variants). The best model (LSTM + Cross-Modal Attention) achieves ROC-AUC of 0.86 on the fully unsubsampled 2024 test set.

**Objective 2: Compare cross-modal attention against late fusion.**
Achieved. Cross-modal attention improves recall by 5.5 to 5.7% over concatenation for CNN and LSTM encoders. This confirms that modelling the interaction between surface susceptibility and atmospheric forcing captures additional dust emission signal.

**Objective 3: Evaluate geographic generalization.**
Achieved with a nuanced result. The model shows partial geographic transfer (West to East AUC 0.81, East to West AUC 0.78) but benefits significantly from region-specific training data (full model AUC 0.89). Operational deployment should include training data from all target regions.

**Objective 4: Deploy an operational early warning system.**
Achieved. The system is live with a mobile web app, backend API with progressive prediction, and database integration. SMS alerting and the WMO desktop dashboard are partially complete.

### Where Results Missed Objectives

**Precision and recall targets:** The initial goal of precision and recall both above 0.6 was not achieved. At the 5.7% positive rate in the test set, this would require ROC-AUC above 0.93. The current best is 0.86. This is a structural constraint of the classification problem, not a model limitation. The system addresses this through the progressive prediction architecture and human-in-the-loop operator review.

**Full geographic generalization:** The model does not fully generalize across sub-regions. Performance gaps of 0.08 to 0.11 AUC points exist between regional models and the full model. This was reported as a finding rather than hidden.

---

## Deployment Plan

### Deployment Architecture

| Component | Platform | Tier | URL |
|---|---|---|---|
| ML Model | Hugging Face Spaces (Docker) | Free | mavencodes-saheldust-api.hf.space |
| Backend API | Render | Free | saheldust-backend.onrender.com |
| Frontend | Vercel | Free | saheldust-frontend.vercel.app |
| Database | Supabase | Free | (project dashboard) |

### Deployment Steps Executed

1. Trained LSTM + CMA model in PyTorch on Kaggle GPU
2. Exported to ONNX format (5.4 MB)
3. Created FastAPI app with ONNX Runtime inference
4. Dockerized and deployed to Hugging Face Spaces
5. Built data pipeline using Open-Meteo (atmospheric forecast) and GEE (SMAP, MODIS)
6. Built progressive alert tracker with escalating alert levels
7. Deployed backend to Render with environment variables
8. Built Next.js frontend with shadcn/ui components
9. Deployed frontend to Vercel
10. Configured Supabase PostgreSQL database with user and alert tables
11. Connected all services and verified CORS, end-to-end data flow

### Deployment Verification

- Backend health check returns `{"status": "ok"}`
- Model API accepts atmospheric and surface arrays and returns predictions
- Frontend successfully calls backend which calls model API
- Progressive prediction tracking works across multiple calls
- Reverse geocoding returns location names for all Sahel coordinates tested

---

## Discussion

### Milestone 1: Data Pipeline
Building the GEE data extraction pipeline was the most time-intensive milestone. Processing 10 years of hourly ERA5 data across 11,696 grid cells required careful batching, parallel processing, and checkpointing. The switch from AOD threshold 0.5 to 0.7 required re-running the entire pipeline but produced cleaner labels and better model performance.

### Milestone 2: Model Training
The 12-model comparison with Optuna hyperparameter optimization provided rigorous evidence for architecture decisions. Key finding: BCE loss outperforms Focal Loss on balanced training data because Focal Loss was designed for imbalanced datasets. Tversky Loss caused mode collapse across all architectures.

### Milestone 3: Feature Engineering
Adding boundary layer height, total precipitation, dewpoint temperature, and vegetation water content improved ROC-AUC from 0.83 to 0.86. Previous-day AOD dominates feature importance at 5x any other feature, confirming that dust persistence is the strongest predictor.

### Milestone 4: Deployment Architecture
The progressive prediction system is the most impactful design decision. Rather than issuing a single prediction, the system continuously refines its forecast as real observations replace forecast data. This reduces false positives because alerts that are not reinforced by subsequent observational data are automatically downgraded before reaching the highest alert level.

### Impact of Results
At the high-recall operating point (threshold 0.50), the model catches 72% of significant dust events. In the current situation where communities receive no automated warning, even an imperfect screening tool that flags 3 out of 4 events for human review represents a meaningful improvement. The system runs on consumer hardware, uses freely available satellite data, and requires no computational infrastructure beyond a web browser.

---

## Recommendations

### For the Community
1. The system should be piloted with a single WMO Regional Specialized Meteorological Centre to validate the progressive prediction approach with trained forecasters before scaling to multiple countries.
2. Alert thresholds should be calibrated through community consultation rather than set by ML convention. The acceptable false positive rate depends on the cost of a missed event versus the cost of a false alarm in each specific community context.

### For Future Technical Work
1. Incorporate aerosol type discrimination using the MODIS Deep Blue product or CALIOP vertical profiling to separate mineral dust from urban pollution, biomass burning, and sea salt at coastal and urban locations.
2. Replace the binary classification with multi-class severity prediction (moderate, severe, extreme) or continuous AOD regression to provide more granular warnings.
3. Add sub-daily prediction windows (6-hourly instead of daily) to provide more actionable timing information about when within the day a dust event is expected.
4. Integrate ECMWF IFS operational forecast data directly for higher quality atmospheric inputs in real-time, replacing the Open-Meteo intermediary.
5. Implement model retraining automation: as new satellite data becomes available, periodically retrain the model to capture evolving dust source patterns and climate trends.

### For the Research Community
1. Multi-modal attention architectures show promise for rare atmospheric event prediction but require careful label quality assessment. Label noise from broadband AOD at the 0.5 threshold is a greater constraint than model capacity.
2. Geographic generalization testing should be standard practice in regional atmospheric prediction studies. Reporting only overall metrics hides significant performance variation across sub-regions.

---

## Project Structure

```
Dual-Encoder-Model-for-Sahel-Dust-Forecasting/
  frontend/
    app/                    # Next.js 14 App Router pages
    components/             # React components (shadcn/ui based)
    lib/                    # API client, utilities, types
    public/                 # Static assets
    .env.local              # Frontend environment variables
    package.json
    tailwind.config.ts

  backend/
    main.py                 # FastAPI application with all endpoints
    data_pipeline.py        # Open-Meteo + GEE data fetching and processing
    alert_tracker.py        # Progressive prediction tracking and alert management
    requirements.txt        # Python dependencies
    .env                    # Backend environment variables (not committed)

  README.md                 # This file
```

### ML Notebooks (external)
- Preprocessing: Google Colab (01_preprocessing.ipynb)
- Training and Evaluation: Kaggle (02_training_evaluation.ipynb)
- AERONET Validation: Google Colab (03_aeronet_validation.ipynb)
