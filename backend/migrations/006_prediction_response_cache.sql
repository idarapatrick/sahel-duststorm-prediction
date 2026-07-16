-- Short-lived response cache used to coalesce concurrent inference requests.

create table if not exists public.prediction_response_cache (
  cache_key text primary key,
  lat double precision not null,
  lon double precision not null,
  target_date date not null,
  model_version text not null,
  payload jsonb not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null
);

create index if not exists prediction_response_cache_expiry
  on public.prediction_response_cache (expires_at);

create or replace function public.purge_expired_prediction_cache()
returns bigint language plpgsql as $$
declare removed bigint;
begin
  delete from public.prediction_response_cache where expires_at <= now();
  get diagnostics removed = row_count;
  return removed;
end;
$$;

