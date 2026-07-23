# SahelWatch

SahelWatch is an AI-powered dust and sand storm monitoring and early-warning platform for communities in the Sahel. It combines atmospheric forecasts, recent satellite observations, a dust-event classifier, continuous background monitoring, location-based history, and alert delivery infrastructure in one deployed system.

This repository contains the machine-learning work, FastAPI backend, PostgreSQL schema and workers, and the responsive SvelteKit web application developed for a BSc Software Engineering capstone project at the African Leadership University.

## Submission links

- **Five-minute demonstration video:** [Watch on YouTube](https://youtu.be/M0oD24Dbub4)
- **Live web application:** [saheldust-frontend.vercel.app](https://saheldust-frontend.vercel.app)
- **Backend API documentation:** [saheldust-backend.onrender.com/docs](https://saheldust-backend.onrender.com/docs)
- **Backend health check:** [saheldust-backend.onrender.com/api/v1/health](https://saheldust-backend.onrender.com/api/v1/health)
- **Model service documentation:** [mavencodes-saheldust-api.hf.space/docs](https://mavencodes-saheldust-api.hf.space/docs)
- **Model service source and Dockerfile:** [Hugging Face Space repository](https://huggingface.co/spaces/mavencodes/saheldust-api/tree/main)

## Problem and project objective

Sand and dust storms reduce visibility, damage crops and infrastructure, contaminate water sources, and worsen respiratory illness. Many at-risk Sahelian communities do not receive accessible, location-specific early information.

SahelWatch aims to provide a practical screening and monitoring system that:

1. estimates the likelihood of dust-producing conditions for a selected Sahel location;
2. explains the result using wind, temperature, soil moisture, and aerosol optical depth (AOD);
3. updates predictions when meaningfully newer forecasts, analyses, or observations become available;
4. records immutable prediction revisions for up to 90 days;
5. creates alerts only when risk rises above clear conditions; and
6. supports optional phone-linked accounts for future offline SMS delivery.

SahelWatch is an early-warning aid, not a replacement for an official warning issued by a national meteorological organisation.

## Implemented functionality

### Community web application

- Responsive SvelteKit interface for desktop and mobile browsers
- Searchable location selection for database-backed cities, towns, and rural communities
- Immediate retrieval of the current-day central prediction, with the separately stored next-day outlook shown alongside it
- Progress state that does not display a probability before a result exists
- Current wind speed, temperature, soil moisture, and AOD when their providers return valid data
- Plain-language prediction evidence and data-availability warnings
- Tracking view, current alerts, recent history, and date-based history search
- Ninety-day rolling retention for prediction records created by the system
- Optional Firebase-verified phone account, login, logout, and freshly verified account deletion
- Privacy policy and terms of use pages
- Multi-horizon control retained in a disabled “Coming soon” state

### Backend and operations

- FastAPI endpoints with coordinate validation and consistent error responses
- Open-Meteo atmospheric forecast and current weather-model retrieval
- Google Earth Engine access for recent SMAP soil moisture and MODIS AOD
- Remote model inference through the deployed model service
- Field-level PostgreSQL evidence provenance with measurement, availability, retrieval, forecast-target, quality, and fallback metadata
- Request coalescing and short-lived PostgreSQL response caching for near-simultaneous requests
- Autonomous reinforcement worker that monitors active forecast grid cells
- PostgreSQL job claiming with `FOR UPDATE SKIP LOCKED`, safe for multiple workers
- Immutable prediction revisions linked to their exact evidence, with identical-input runs suppressed
- Alert upgrade and downgrade events through a transactional outbox
- Separate alert-delivery worker with idempotency, retry, and dead-letter handling
- Worker heartbeat, queue health, rate limiting, retention cleanup, and health reporting
- Delayed MODIS outcome collection and leakage-safe validation against the model's AOD greater than 0.7 training label
- Brier score, log loss, ROC-AUC, PR-AUC, calibration, alert metrics, failure slices, and simple baseline comparisons

## Prediction design

### Current operational prediction

The deployed classifier returns one binary dust-event probability. The backend builds its input from:

- a 72-hour atmospheric window containing wind, temperature, pressure, precipitation, boundary-layer and moisture-related variables;
- recent SMAP soil moisture and vegetation water content;
- previous available MODIS AOD;
- latitude, longitude, and seasonal encoding.

The result is translated into four operational levels:

| Probability | Level | Behaviour |
|---:|---|---|
| Below 0.30 | Clear | Stored, but no alert broadcast is created |
| 0.30 to below 0.50 | Watch | Conditions require attention |
| 0.50 to below 0.70 | Warning | Dust-producing conditions are increasingly likely |
| 0.70 and above | Alert | Highest operational risk level |

The progressive pipeline accepts both increases and decreases. If newer environmental evidence reduces the estimated risk, the new lower result is stored and the alert can be downgraded. Forecast API values remain labelled as forecasts, CAMS values as analyses, and SMAP or MODIS values as delayed observations.

### Continuous reinforcement

The background worker creates monitoring jobs without waiting for users. For each active forecast grid cell it:

1. creates or finds current-day and next-day jobs;
2. atomically claims the job from PostgreSQL;
3. retrieves and fingerprints updated atmospheric and surface evidence;
4. runs inference only when the evidence has meaningfully changed;
5. stores a new immutable snapshot and its evidence;
6. creates an outbox event only for a meaningful risk-level transition;
7. schedules the next hourly evaluation; and
8. stops after the target monitoring window expires.

The user application reads these central snapshots and does not run inference during login or location switching. Cities, towns, villages, and communities are stored in PostgreSQL and mapped to forecast grid cells. Several nearby places can therefore share one hourly prediction instead of making duplicate model calls. The recent-history endpoint can contain centrally generated snapshots as well as explicitly requested diagnostic predictions. The 90-day policy is a retention maximum, not a fabricated historical backfill. A date before the service began recording legitimately returns no prediction snapshots.

### Geographic coverage

Coverage is not restricted to AERONET station locations. AERONET is an independent evaluation source where a station exists, while operational inputs are obtained from gridded Open-Meteo, SMAP, and MODIS products. The database catalogue distinguishes `operational` places from `provisional` places whose local performance checks are still continuing. A broad coordinate boundary is an input guard, not proof that every point inside it has been validated.

`GET /api/v1/coverage/places` returns the active catalogue and supports text and country filtering. `GET /api/v1/coverage/nearest` maps a device coordinate to the nearest monitored community and its shared forecast cell. Migration `010_coverage_catalogue.sql` seeds the original locations plus regional and rural communities in Niger, Nigeria, Burkina Faso, Mali, Chad, Senegal, and Mauritania. Nearby communities such as Libore, Wamakko, Kumbotso, Jere, and Saaba demonstrate the shared-cell mapping.

### Multi-horizon limitation

The available dust-event ground truth is daily MODIS AOD. It cannot support separately trained 12-hour, 24-hour, 36-hour, and 48-hour labels. The correct research extension uses day+0, day+1, and day+2 labels for the same grid cell, with missing satellite days masked rather than interpolated.

The three-head PyTorch extension and date-aware label builder are retained in `ml/`, but the production endpoint returns HTTP 501 and the frontend marks the feature as coming soon. It will remain disabled until training, final evaluation, and ONNX export are complete.

## System architecture

```text
SvelteKit web application on Vercel
                 |
                 v
FastAPI API on Render
  |              |                 |
  v              v                 v
Open-Meteo   Google Earth      Model service
weather      Engine satellite  on Hugging Face
                 |
                 v
DigitalOcean Managed PostgreSQL
  |                     |
  v                     v
Reinforcement worker    Alert-delivery worker
  |                     |
  v                     v
Prediction revisions    SMS provider integration
and alert outbox         and delivery records
```

## Technology stack

| Area | Technology |
|---|---|
| Frontend | SvelteKit, TypeScript, Vite, MapLibre GL |
| Backend | Python, FastAPI, Pydantic, HTTPX |
| Machine learning | PyTorch, ONNX Runtime, dual encoder with cross-modal attention |
| Atmospheric data | Open-Meteo |
| Surface and aerosol data | Google Earth Engine, SMAP, MODIS |
| Database | DigitalOcean Managed PostgreSQL |
| Web hosting | Vercel |
| API and workers | Render |
| Model hosting | Hugging Face Spaces |
| Authentication and SMS | Firebase Phone Authentication and Twilio alert delivery, with a temporary Africa's Talking rollback adapter during migration |

## Installation and local execution

### Prerequisites

- Git
- Python 3.11 or newer
- Node.js 22 and npm
- PostgreSQL for the complete backend workflow
- Google Earth Engine project and service account for live SMAP and MODIS access
- Access to the configured model endpoint

### 1. Clone the repository

```bash
git clone https://github.com/idarapatrick/sahel-duststorm-prediction.git
cd sahel-duststorm-prediction
```

### 2. Create the backend environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Edit `backend/.env`. At minimum, a production-like setup needs:

```dotenv
HF_SPACE_URL=https://mavencodes-saheldust-api.hf.space/predict
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE?sslmode=require
DATABASE_REQUIRED=true
HISTORY_RETENTION_DAYS=90
AUTH_SECRET=replace-with-at-least-32-random-characters
CORS_ORIGINS=http://localhost:5173
GEE_PROJECT_ID=your-google-cloud-project-id
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
MULTI_HORIZON_MODEL_URL=
```

Never commit `.env`, database credentials, API keys, authentication secrets, or a Google service-account key.

### 3. Apply database migrations

Use the direct administrator connection as `DATABASE_ADMIN_URL` locally. If it is absent, the migration runner uses `DATABASE_URL`.

```bash
python migrate.py
```

The runner applies every unapplied SQL file in `backend/migrations/` and records it in `schema_migrations`.

### 4. Start the backend API

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- API root: `http://localhost:8000`
- Interactive API documentation: `http://localhost:8000/docs`
- Operational health: `http://localhost:8000/api/v1/health`

### 5. Start the reinforcement worker

In a second terminal, activate the same environment and run:

```bash
cd backend
source .venv/bin/activate
python reinforcement_worker.py
```

### 6. Start the alert-delivery worker

In a third terminal:

```bash
cd backend
source .venv/bin/activate
python alert_delivery_worker.py
```

This worker requires the database and SMS variables to perform real delivery. Without approved live SMS configuration, use it only to verify queue and retry behaviour.

### 7. Install and start the frontend

In another terminal from the repository root:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Set the frontend variable to the local API:

```dotenv
PUBLIC_API_BASE_URL=http://localhost:8000
```

Open `http://localhost:5173`.

### 8. Run repository checks

```bash
cd frontend
npm run check
npm run build
```

The repository also contains focused backend checks for history, current conditions, satellite fallback, monitoring windows, and daily-horizon label construction. Install the development requirements before running them:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Functional and performance testing

The assessed demonstration focuses on functionality testing rather than unit-testing footage. The [five-minute video](https://youtu.be/M0oD24Dbub4) is the primary demonstration evidence.

### Testing strategies and evidence

| Strategy | Demonstration | Expected evidence |
|---|---|---|
| Normal input | Select a monitored community and request a prediction | Probability, risk level, location, conditions, and evidence are returned |
| Different data values | Compare multiple Sahel cities | The system retrieves location-specific inputs and does not hard-code one result |
| Invalid input | Submit coordinates outside the supported range | HTTP 400 response with a clear validation message |
| Missing upstream field | Inspect a result when satellite data is unavailable | Field is marked unavailable or degraded; the client does not invent a value |
| Location switching | Change city in the web application | A fresh location request starts and the previous city's result is not relabelled |
| History | Request recent Niamey history and a recorded target date | Stored user and `background-progressive-open-meteo+gee` snapshots are returned |
| Background execution | Compare worker heartbeat, queue state, and a later history record | A fresh heartbeat and newly stored immutable background snapshot are visible |
| Alert threshold | Compare clear and controlled watch or warning conditions | Clear results create no broadcast; higher levels create an outbox alert event |
| Concurrency | Send several requests for the same coordinates concurrently | Successful responses share cached inference and avoid duplicate work |
| Latency | Measure warm, cold, average, and 95th-percentile response time | HTTP status and measured timing are captured, not estimated |
| Compatibility | Run on desktop and a real mobile browser or alternate browser | Responsive layout and core flow remain usable |

Example latency command:

```bash
curl -o /dev/null -sS \
  -w "HTTP: %{http_code}\nFirst byte: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  "https://saheldust-backend.onrender.com/api/v1/predict/location?lat=13.5127&lon=2.1125"
```

Example concurrent-request command:

```bash
seq 1 20 | xargs -P 5 -I {} \
  curl -o /dev/null -sS \
  -w "Request {}: HTTP %{http_code}, %{time_total}s\n" \
  "https://saheldust-backend.onrender.com/api/v1/predict/location?lat=13.5127&lon=2.1125"
```

### Analysis of results against project objectives

- **End-to-end objective:** Achieved for supported locations. The deployed frontend can request the backend, which obtains environmental inputs, calls the model service, stores the result, and returns user-facing evidence.
- **Continuous monitoring objective:** Achieved. The reinforcement worker creates central jobs, refreshes predictions, records evidence, and reschedules work independently of user activity.
- **History objective:** Achieved as rolling retention for records produced since deployment. It does not fabricate predictions for dates before monitoring began. An immediate retrospective 90-day environmental archive remains future work.
- **Robustness objective:** Substantially achieved through validation, request coalescing, immutable storage, database-backed queues, retries, heartbeats, rate limiting, and degraded-data reporting.
- **Offline alert objective:** The account, subscription, outbox, delivery, and provider adapter architecture is implemented. Production delivery across Sahel countries still requires approved sender configuration and operational agreements with SMS or telecommunications providers.
- **Multi-horizon objective:** Not yet operational. Scientifically valid daily heads are designed, but production remains disabled pending trained and validated weights.

Measured latency and success-rate values should be taken directly from the demonstration run because hosting wake state, network route, Earth Engine response time, and model-service state change between runs.

## Deployment plan and execution

| Component | Platform | Production responsibility |
|---|---|---|
| SvelteKit frontend | Vercel | Responsive user interface and API client |
| FastAPI web service | Render | Validation, data orchestration, inference, history and authentication APIs |
| Reinforcement worker | Render background worker | Central prediction updates and alert transitions |
| Alert-delivery worker | Render background worker | Recipient matching, SMS attempts, retries and dead letters |
| PostgreSQL | DigitalOcean Managed Database | Durable users, jobs, snapshots, evidence, cache and outbox records |
| Model API | Hugging Face Spaces | Deployed binary classifier inference |
| Satellite access | Google Earth Engine | Recent SMAP and MODIS observations |

The detailed production variables, Render commands, migration procedure, worker setup, database guidance, and verification checklist are in [`docs/deployment.md`](docs/deployment.md).

Production verification includes:

1. `/api/v1/health` reports the database, Earth Engine, model, queues, and worker heartbeats.
2. `/api/v1/predict/location` returns a real stored result with current conditions and input provenance.
3. `/api/v1/history/recent` contains worker-generated records for centrally monitored cities.
4. Repeated coordinate requests return successfully without duplicate inference work inside the cache window.
5. Clear conditions do not generate warning broadcasts.
6. Watch, warning, and alert transitions create outbox records for eligible subscriptions.

## Code quality and repository organisation

The implementation separates API routing, data acquisition, prediction models, persistence, monitoring, authentication, alert delivery, and frontend presentation. Database changes are versioned and repeatable. Workers communicate through PostgreSQL rather than process-local memory, allowing services to restart or scale independently.

```text
.
├── backend/
│   ├── main.py                       # FastAPI routes and application middleware
│   ├── model.py                      # API response models and validation
│   ├── data_pipeline.py              # Open-Meteo and Earth Engine input pipeline
│   ├── history_store.py              # Immutable prediction-history persistence
│   ├── monitoring_store.py           # PostgreSQL monitoring queue and evidence
│   ├── prediction_cache.py           # Distributed response cache and coalescing
│   ├── reinforcement_worker.py       # Autonomous central monitoring worker
│   ├── alert_store.py                # Outbox, delivery, heartbeat and queue storage
│   ├── alert_delivery_worker.py      # SMS delivery worker
│   ├── auth_store.py                 # Application sessions and temporary legacy OTP adapter
│   ├── firebase_auth.py              # Firebase token verification and identity linking
│   ├── sms_provider.py               # Twilio alerts and temporary rollback adapter
│   ├── migrations/                   # Versioned PostgreSQL schema changes
│   ├── functional_probe.py            # Deployed per-location, failure and latency probes
│   └── tests/                        # Focused backend checks
├── frontend/
│   ├── src/routes/                   # Dashboard, privacy and terms pages
│   ├── src/lib/api.ts                # Typed backend client
│   ├── src/lib/locations.ts          # Supported locations
│   ├── src/lib/components/           # Onboarding, header and map components
│   └── src/lib/styles/               # Themes, glass surfaces and animation
├── ml/
│   ├── dust_model.py                 # Reusable dual-encoder and attention architecture
│   ├── multi_horizon_model.py        # Pending day+0/day+1/day+2 heads
│   ├── daily_horizon_labels.py       # Date-aware, non-fabricated daily labels
│   └── evaluate_failure_slices.py    # Seasonal, coastal and per-location evaluation
├── notebooks/                        # Preprocessing, evaluation and validation work
├── docs/
│   ├── deployment.md                 # Production deployment instructions
│   └── prediction_architecture.md    # Prediction architecture explanation
├── data/README.md                     # Data notes
└── README.md
```

## Discussion and impact

The principal engineering milestone is the move from an isolated prediction screen to a durable monitoring system. Independent workers check central locations each hour, store every revision, and prepare higher-risk transitions for delivery. Users read the latest completed database snapshot instead of waiting for environmental collection and model inference. This matters in the Sahel because monitoring continues when nobody has the application open and a large group of users can share one prediction result.

The use of forecast atmospheric data with the latest available satellite surface evidence reflects the different update frequencies of the providers. MODIS AOD and SMAP are observational inputs, not future forecasts. Their observation dates and availability must therefore remain visible and must never be represented as future measurements.

The project also demonstrates an important scientific limitation: a daily satellite label cannot validate four independent clock-hour targets. Keeping the unvalidated multi-horizon interface disabled protects the credibility of the system while the correct daily-resolution extension is trained.

## Recommendations and future work

### Community and operational recommendations

1. Pilot the system with national meteorological organisations and affected communities before treating its thresholds as operational warnings.
2. Develop messages in locally appropriate languages and validate that risk wording leads to useful, safe action.
3. Agree on alert authority, escalation, cancellation, and audit procedures with participating organisations.
4. Work with telecommunications providers and WMOs to deliver reliable, affordable offline messages across supported countries.

### Technical future work

1. Complete, evaluate, calibrate, and export the day+0/day+1/day+2 model before enabling multi-horizon forecasts.
2. Add a clearly labelled retrospective environmental-analysis service for the period before prediction monitoring began.
3. Reconcile SMS provider delivery receipts and migrate phone authentication to a production identity provider if selected.
4. Add successful-job duration logs and operational dashboards for worker schedule delay and processing latency.
5. Perform database restore drills and add higher availability for the API, workers, model endpoint, and database.
6. Evaluate the system using new dry-season observations and location-specific calibration with WMO experts.

## Demonstration

The submitted video prioritises the core product flow, environmental evidence, location changes, prediction history, background monitoring, robustness, and deployment rather than spending most of the five-minute limit on account creation.

**Watch the complete demonstration:** [https://youtu.be/M0oD24Dbub4](https://youtu.be/M0oD24Dbub4)
