create table if not exists ai_chat (
  id text primary key,
  user_id text not null references app_user(id),
  model_id text not null references llm_model(id),
  title text not null default '',
  created_at integer not null,
  updated_at integer not null
);

create index if not exists idx_ai_chat_user_id_updated_at
  on ai_chat(user_id, updated_at desc, created_at desc, id asc);

create table if not exists ai_chat_message (
  id text primary key,
  chat_id text not null references ai_chat(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text,
  model_id text,
  model_name text,
  request_started_at integer,
  message_type text not null default 'text',
  payload_json text,
  tool_call_id text,
  round integer,
  created_at integer not null
);

create index if not exists idx_ai_chat_message_chat_id_created_at
  on ai_chat_message(chat_id, created_at asc, id asc);
