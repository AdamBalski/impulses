-- User role enum
do $$ begin
  create type user_role as enum ('ADMIN', 'STANDARD');
exception when duplicate_object then null; end $$;

-- Users table
create table if not exists app_user (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text not null,
  role user_role not null default 'STANDARD',
  created_at timestamptz not null default now(),
  deleted_at timestamptz
);

-- Token capability enum
-- API is for querying data and maybe later for setting up dashboards
-- INGEST is for ingesting data
-- SUPER is for everything
do $$ begin
  create type token_capability as enum ('API', 'INGEST', 'SUPER');
exception when duplicate_object then null; end $$;

-- Data tokens table
create table if not exists data_token (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references app_user(id),
  name text not null,
  token_hash text not null,
  capability token_capability not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

-- Indexes for performance
create index if not exists idx_app_user_email on app_user(email) where deleted_at is null;
create index if not exists idx_data_token_user_id on data_token(user_id);
create index if not exists idx_data_token_expires_at on data_token(expires_at);
