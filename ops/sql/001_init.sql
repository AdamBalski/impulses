create table if not exists app_user (
  id text primary key,
  email text unique not null,
  password_hash text not null,
  role text not null default 'STANDARD' check (role in ('ADMIN', 'STANDARD')),
  created_at integer not null,
  deleted_at integer
);

-- Data tokens table
create table if not exists data_token (
  id text primary key,
  user_id text not null references app_user(id),
  name text not null,
  token_hash text not null,
  capability text not null check (capability in ('API', 'INGEST', 'SUPER')),
  expires_at integer not null,
  created_at integer not null
);

-- Indexes for performance
create index if not exists idx_app_user_email on app_user(email) where deleted_at is null;
create index if not exists idx_data_token_user_id on data_token(user_id);
create index if not exists idx_data_token_expires_at on data_token(expires_at);

-- Local storage sync table
create table if not exists local_storage_entry (
  id text primary key,
  user_id text not null references app_user(id),
  key text not null,
  value text not null,
  created_at integer not null,
  updated_at integer not null,
  unique (user_id, key)
);

create index if not exists idx_local_storage_entry_user_id on local_storage_entry(user_id);
