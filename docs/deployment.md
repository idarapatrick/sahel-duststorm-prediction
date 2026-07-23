# SahelWatch deployment guide

This document describes the production topology, configuration contract, deployment sequence, and verification procedure for maintainers of SahelWatch.

## Production topology

| Service | Platform | Responsibility |
|---|---|---|
| Web application | Vercel | SvelteKit user interface |
| API | Render web service | Data acquisition, inference orchestration, authentication, history, and alerts |
| Reinforcement worker | Render background worker | Scheduled prediction revisions for centrally monitored locations |
| Alert worker | Render background worker | Transactional-outbox delivery and retry processing |
| Database | DigitalOcean Managed PostgreSQL | Durable application, history, monitoring, cache, and alert state |
| Model API | Hugging Face Spaces | Binary dust-event inference |
| Satellite provider | Google Earth Engine | SMAP soil moisture and MODIS AOD observations |
| Atmospheric provider | Open-Meteo | Current conditions and atmospheric forecast windows |

## Configuration

Configuration is supplied through environment variables. Secrets must be stored in the hosting platform's secret manager and must never be committed.

### API and reinforcement worker

```dotenv
HF_SPACE_URL=https://mavencodes-saheldust-api.hf.space/predict
DATABASE_URL=postgresql://APP_USER:PASSWORD@POOL_HOST:PORT/DATABASE?sslmode=require
DATABASE_REQUIRED=true
HISTORY_RETENTION_DAYS=90
CORS_ORIGINS=https://saheldust-frontend.vercel.app,http://localhost:5173
GEE_PROJECT_ID=registered-google-cloud-project-id
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
MONITOR_INTERVAL_HOURS=1
WORKER_POLL_SECONDS=30
MONITOR_RETRY_MINUTES=15
MONITOR_MAX_ATTEMPTS=8
PREDICTION_CACHE_TTL_SECONDS=300
PREDICTION_CACHE_BUCKET_SECONDS=300
MODEL_VERSION=single-head-current
MULTI_HORIZON_MODEL_URL=
```

`MULTI_HORIZON_MODEL_URL` remains unset until the day+0, day+1, and day+2 model completes evaluation and ONNX validation.

Google Earth Engine may instead use a Render secret file. In that configuration, `GOOGLE_APPLICATION_CREDENTIALS` contains the absolute path to the JSON key and `GEE_SERVICE_ACCOUNT_JSON` is omitted. The Google Cloud project must have Earth Engine enabled and registered.

### Authentication and alert delivery

```dotenv
AUTH_SECRET=at-least-32-random-characters
FIREBASE_PROJECT_ID=sahelwatch-firebase-project
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
ALERT_SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=provider-secret
TWILIO_MESSAGING_SERVICE_SID=MG...
# Use TWILIO_FROM_NUMBER instead when no Messaging Service is configured.
TWILIO_FROM_NUMBER=+1...
ALERT_WORKER_POLL_SECONDS=15
ALERT_MAX_ATTEMPTS=8

# Temporary rollback values. Remove after migration acceptance tests pass.
AFRICASTALKING_USERNAME=provider-application-username
AFRICASTALKING_API_KEY=provider-secret-key
AFRICASTALKING_SANDBOX=false
AFRICASTALKING_SENDER_ID=approved-transactional-sender-id
```

Firebase sends and verifies authentication codes. The backend verifies Firebase ID tokens and links the trusted Firebase UID to the existing PostgreSQL phone identity, preserving subscriptions and alert history. Twilio sends dust-alert SMS only. `AUTH_SECRET` remains required for application-session and IP hashes during the transition. Live alert delivery depends on account funding, an approved sender or Messaging Service, supported routes, and country-specific telecommunications requirements.

### Frontend

```dotenv
PUBLIC_API_BASE_URL=https://saheldust-backend.onrender.com
PUBLIC_AUTH_PROVIDER=firebase
PUBLIC_FIREBASE_API_KEY=browser-api-key
PUBLIC_FIREBASE_AUTH_DOMAIN=project.firebaseapp.com
PUBLIC_FIREBASE_PROJECT_ID=project-id
PUBLIC_FIREBASE_APP_ID=web-app-id
PUBLIC_FIREBASE_MESSAGING_SENDER_ID=sender-id
```

The public Firebase web configuration identifies the Firebase project and is expected in the browser. Firebase service-account JSON and Twilio credentials are backend secrets and must never use `PUBLIC_` variables.

## PostgreSQL deployment

DigitalOcean's direct administrator connection is used only for migrations. Runtime services use a restricted application user through the transaction-pool connection.

```bash
cd backend
python migrate.py
```

The migration runner:

- discovers numbered SQL files in `backend/migrations/`;
- records applied versions in `schema_migrations`;
- skips completed migrations; and
- uses `DATABASE_ADMIN_URL`, falling back to `DATABASE_URL` when necessary.

The production database requires automated backups, restricted network access, separate administrator and application credentials, and periodic restore drills. Schema migrations and retention cleanup are not backups.

## Render API service

```text
Service type: Web Service
Root directory: backend
Build command: pip install -r requirements.txt
Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
Health path: /api/v1/health
```

The API must receive the database, model, Earth Engine, authentication, CORS, cache, and retention variables described above.

The Render backend is deployed from `backend/` using the native Python build above. The separately deployed model service is containerised in its own [Hugging Face Space repository](https://huggingface.co/spaces/mavencodes/saheldust-api/tree/main), which contains its Dockerfile, inference application, pinned service dependencies, and ONNX model artifact.

## Render reinforcement worker

```text
Service type: Background Worker
Root directory: backend
Build command: pip install -r requirements.txt
Start command: python reinforcement_worker.py
```

The worker uses the same `DATABASE_URL`, `DATABASE_REQUIRED`, `HF_SPACE_URL`, Earth Engine variables, model version, and monitoring configuration as the API.

The worker maintains one central target-day job for each active forecast grid cell, claims due work using PostgreSQL row locks, obtains new evidence, stores an immutable hourly prediction revision, creates risk-transition outbox events, and aligns the next evaluation to the next UTC hour. Multiple settlements may map to the same cell, so expanding the place catalogue does not require duplicate inference for nearby communities. Superseded target-day work is cancelled during calendar rollover. Multiple instances can operate safely because a monitoring job can be claimed by only one worker at a time.

The user-facing application reads the latest completed central snapshot from PostgreSQL. Login and location switching do not invoke the model service. All users assigned to a forecast cell share its latest result.

## Render alert-delivery worker

```text
Service type: Background Worker
Root directory: backend
Build command: pip install -r requirements.txt
Start command: python alert_delivery_worker.py
```

This worker requires the database, authentication secret, provider credentials, poll interval, and retry configuration. Delivery idempotency prevents the same event-recipient pair from being sent twice. Exhausted events move to the dead-letter state for investigation.

## Vercel frontend

```text
Root directory: frontend
Framework preset: SvelteKit
Install command: npm install
Build command: npm run build
```

The production frontend origin must also appear in the API's `CORS_ORIGINS` list.

## Deployment order

1. Provision PostgreSQL, application credentials, network rules, and backups.
2. Apply every unapplied database migration.
3. Configure and deploy the model service.
4. Configure and deploy the FastAPI web service.
5. Deploy the reinforcement worker with the same prediction configuration.
6. Deploy the alert worker when provider configuration is ready.
7. Deploy the SvelteKit frontend with the production API URL.
8. Execute the verification checklist and retain the evidence with the release record.

## Verification

### Health and providers

```bash
BACKEND=https://saheldust-backend.onrender.com
curl "$BACKEND/api/v1/health"
curl "$BACKEND/api/v1/conditions/current?lat=13.51&lon=2.11"
curl "$BACKEND/api/v1/predict/location?lat=13.51&lon=2.11"
curl "$BACKEND/api/v1/history/recent?lat=13.51&lon=2.11&limit=10"
curl "$BACKEND/api/v1/coverage/places?country=NE"
curl "$BACKEND/api/v1/coverage/nearest?lat=14.20&lon=1.46"
```

The health response should report:

- PostgreSQL available;
- Earth Engine available;
- model service configured;
- fresh reinforcement-worker heartbeat;
- bounded due and failed job counts; and
- bounded pending, failed, and dead-letter outbox counts.

Prediction responses should contain current conditions, surface values, and field-level provenance. A missing satellite observation must be marked unavailable or degraded rather than silently presented as a real zero reading.

### Concurrency

```bash
seq 1 20 | xargs -P 5 -I {} \
  curl -o /dev/null -sS \
  -w "request {}: HTTP %{http_code}, %{time_total}s\n" \
  "$BACKEND/api/v1/predict/location?lat=13.51&lon=2.11"
```

Identical requests inside the cache window should complete successfully and share the distributed cached result. Only the lock holder performs inference and writes the initial snapshot.

### Operational checks

- A newer `background-progressive-open-meteo+gee` history record appears after a worker cycle.
- Clear predictions do not create warning broadcasts.
- Risk upgrades and downgrades produce the expected outbox transitions.
- Delivery records remain unique for each event-recipient pair.
- Failed external calls enter the configured retry path.
- GEE provenance contains the real SMAP and MODIS observation dates.
- Database backup restoration is tested independently of the live cluster.

## Reliability considerations

Free or scale-to-zero hosting can introduce cold-start delay and does not provide continuous production availability. Operational use requires non-sleeping service plans, health monitoring, alerting, database backups, provider quotas, and an agreed incident-response process.

The current multi-horizon endpoint is intentionally unavailable. Daily MODIS labels support day+0, day+1, and day+2 training targets, not fabricated independent 12-hour clock labels. Production enablement requires trained weights, held-out evaluation, calibration, ONNX export, and end-to-end validation.
