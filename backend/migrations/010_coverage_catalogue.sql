-- Database-backed settlement catalogue and shared forecast grid cells.
-- Multiple communities may share one forecast cell, preventing duplicate inference.

create table if not exists public.forecast_grid_cells (
  id uuid primary key default gen_random_uuid(),
  cell_key text not null unique,
  centre_lat double precision not null check (centre_lat between 10 and 25),
  centre_lon double precision not null check (centre_lon between -18 and 25),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (centre_lat, centre_lon)
);

create table if not exists public.covered_places (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  country text not null,
  country_code char(2) not null,
  place_type text not null default 'town'
    check (place_type in ('city','town','village','community')),
  lat double precision not null check (lat between 10 and 25),
  lon double precision not null check (lon between -18 and 25),
  forecast_cell_id uuid not null references public.forecast_grid_cells(id),
  coverage_status text not null default 'provisional'
    check (coverage_status in ('validated','operational','provisional')),
  priority integer not null default 100,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (name, country_code)
);

create index if not exists covered_places_search
  on public.covered_places (country_code, lower(name));
create index if not exists covered_places_cell
  on public.covered_places (forecast_cell_id) where active;

-- Initial operational locations and additional underserved regional centres.
-- Provisional means the pipeline can serve the place, while location-specific
-- performance evaluation is still required. It does not imply AERONET coverage.
with seed(name,country,country_code,place_type,lat,lon,status,priority) as (
  values
    ('Niamey','Niger','NE','city',13.51,2.11,'operational',10),
    ('Sokoto','Nigeria','NG','city',13.06,5.24,'operational',10),
    ('Kano','Nigeria','NG','city',12.00,8.52,'operational',10),
    ('Maiduguri','Nigeria','NG','city',11.85,13.16,'operational',10),
    ('Agadez','Niger','NE','city',16.97,7.99,'operational',10),
    ('N''Djamena','Chad','TD','city',12.13,15.06,'operational',10),
    ('Bamako','Mali','ML','city',12.64,-8.00,'operational',10),
    ('Timbuktu','Mali','ML','town',16.77,-3.01,'operational',10),
    ('Ouagadougou','Burkina Faso','BF','city',12.36,-1.48,'operational',10),
    ('Dakar','Senegal','SN','city',14.69,-17.44,'operational',10),
    ('Nouakchott','Mauritania','MR','city',18.09,-15.98,'operational',10),
    ('Tillaberi','Niger','NE','town',14.21,1.45,'provisional',30),
    ('Maradi','Niger','NE','city',13.50,7.10,'provisional',30),
    ('Zinder','Niger','NE','city',13.81,8.99,'provisional',30),
    ('Diffa','Niger','NE','town',13.32,12.61,'provisional',30),
    ('Tahoua','Niger','NE','town',14.89,5.27,'provisional',30),
    ('Katsina','Nigeria','NG','city',12.99,7.60,'provisional',30),
    ('Gusau','Nigeria','NG','city',12.17,6.66,'provisional',30),
    ('Damaturu','Nigeria','NG','town',11.75,11.96,'provisional',30),
    ('Gashua','Nigeria','NG','town',12.87,11.04,'provisional',30),
    ('Dori','Burkina Faso','BF','town',14.03,-0.03,'provisional',30),
    ('Djibo','Burkina Faso','BF','town',14.10,-1.63,'provisional',30),
    ('Gorom-Gorom','Burkina Faso','BF','town',14.44,-0.23,'provisional',30),
    ('Gao','Mali','ML','city',16.27,-0.04,'provisional',30),
    ('Mopti','Mali','ML','city',14.49,-4.20,'provisional',30),
    ('Kidal','Mali','ML','town',18.44,1.41,'provisional',30),
    ('Menaka','Mali','ML','town',15.92,2.40,'provisional',30),
    ('Abeche','Chad','TD','city',13.83,20.83,'provisional',30),
    ('Moussoro','Chad','TD','town',13.64,16.49,'provisional',30),
    ('Faya-Largeau','Chad','TD','town',17.93,19.10,'provisional',30),
    ('Podor','Senegal','SN','town',16.65,-14.96,'provisional',30),
    ('Matam','Senegal','SN','town',15.66,-13.26,'provisional',30),
    ('Linguere','Senegal','SN','town',15.40,-15.12,'provisional',30),
    ('Nema','Mauritania','MR','town',16.62,-7.25,'provisional',30),
    ('Atar','Mauritania','MR','town',20.52,-13.05,'provisional',30),
    ('Kiffa','Mauritania','MR','town',16.62,-11.40,'provisional',30)
), inserted_cells as (
  insert into public.forecast_grid_cells(cell_key,centre_lat,centre_lon)
  select 'point:' || to_char(lat,'FM990.00') || ':' || to_char(lon,'FM990.00'), lat, lon
  from seed
  on conflict (centre_lat,centre_lon) do update set active=true
  returning id,cell_key,centre_lat,centre_lon
)
insert into public.covered_places
  (name,country,country_code,place_type,lat,lon,forecast_cell_id,coverage_status,priority)
select s.name,s.country,s.country_code,s.place_type,s.lat,s.lon,c.id,s.status,s.priority
from seed s join inserted_cells c
  on c.cell_key='point:' || to_char(s.lat,'FM990.00') || ':' || to_char(s.lon,'FM990.00')
on conflict (name,country_code) do update set
  country=excluded.country, place_type=excluded.place_type,
  lat=excluded.lat, lon=excluded.lon, forecast_cell_id=excluded.forecast_cell_id,
  coverage_status=excluded.coverage_status, priority=excluded.priority,
  active=true, updated_at=now();

-- Nearby communities share the established cell instead of triggering a
-- duplicate inference. Their own coordinates remain available for display.
with shared(name,country,country_code,place_type,lat,lon,cell_lat,cell_lon) as (
  values
    ('Libore','Niger','NE','community',13.41,2.19,13.51,2.11),
    ('Wamakko','Nigeria','NG','community',13.04,5.10,13.06,5.24),
    ('Kumbotso','Nigeria','NG','community',11.89,8.50,12.00,8.52),
    ('Jere','Nigeria','NG','community',11.84,13.10,11.85,13.16),
    ('Saaba','Burkina Faso','BF','community',12.38,-1.41,12.36,-1.48)
)
insert into public.covered_places
  (name,country,country_code,place_type,lat,lon,forecast_cell_id,coverage_status,priority)
select s.name,s.country,s.country_code,s.place_type,s.lat,s.lon,c.id,'provisional',40
from shared s join public.forecast_grid_cells c
  on c.cell_key='point:' || to_char(s.cell_lat,'FM990.00') || ':' || to_char(s.cell_lon,'FM990.00')
on conflict (name,country_code) do update set
  country=excluded.country, place_type=excluded.place_type,
  lat=excluded.lat, lon=excluded.lon, forecast_cell_id=excluded.forecast_cell_id,
  coverage_status=excluded.coverage_status, priority=excluded.priority,
  active=true, updated_at=now();
