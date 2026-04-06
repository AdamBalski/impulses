create table if not exists llm_model (
  id text primary key,
  user_id text not null references app_user(id),
  model_name text not null default '',
  settings_json text not null,
  created_at integer not null,
  updated_at integer not null
);

create index if not exists idx_llm_model_user_id on llm_model(user_id);
