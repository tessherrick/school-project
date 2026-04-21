-- 001_initial_schema.sql
-- Motif N1 — initial schema.
--
-- Apply via either:
--   1. python -m backend.db.migrate   (needs SUPABASE_DB_URL in .env)
--   2. Paste into Supabase dashboard → SQL editor → Run

create extension if not exists pgcrypto;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  created_at timestamptz default now()
);

create table if not exists wearable_readings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  date date not null,
  hrv_rmssd float,
  recovery_score float,
  resting_hr float,
  sleep_performance float,
  strain float,
  raw_payload jsonb,
  source text default 'whoop',
  created_at timestamptz default now()
);

create table if not exists interventions (
  id uuid primary key default gen_random_uuid(),
  key text unique not null,
  label text not null,
  description text,
  prior_mean_effect float default 0,
  prior_sd_effect float default 5
);

create table if not exists daily_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  date date not null,
  intervention_states jsonb,
  created_at timestamptz default now(),
  unique (user_id, date)
);

create table if not exists experiments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  intervention_id uuid references interventions(id) on delete cascade,
  protocol_type text,
  start_date date,
  end_date date,
  status text default 'planned',
  schedule jsonb,
  created_at timestamptz default now()
);

create table if not exists personal_estimates (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  intervention_id uuid references interventions(id) on delete cascade,
  posterior_mean float,
  posterior_sd float,
  num_observations int default 0,
  last_updated timestamptz default now(),
  unique (user_id, intervention_id)
);

create table if not exists experiment_results (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid references experiments(id) on delete cascade,
  summary_text text,
  effect_estimate float,
  confidence float,
  completed_at timestamptz default now()
);

create table if not exists whoop_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  access_token text,
  refresh_token text,
  expires_at timestamptz
);

create index if not exists idx_wearable_readings_user_date on wearable_readings(user_id, date desc);
create index if not exists idx_daily_logs_user_date on daily_logs(user_id, date desc);
create index if not exists idx_experiments_user on experiments(user_id);
create index if not exists idx_personal_estimates_user on personal_estimates(user_id);
