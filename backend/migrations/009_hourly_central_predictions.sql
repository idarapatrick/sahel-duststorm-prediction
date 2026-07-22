-- Support low-latency central hourly prediction reads.

alter table public.environmental_observations
  add column if not exists dewpoint_c double precision;

create index if not exists prediction_snapshot_latest_location
  on public.prediction_snapshots (lat, lon, recorded_at desc);

create index if not exists environmental_observation_latest_received
  on public.environmental_observations (location_id, received_at desc);
