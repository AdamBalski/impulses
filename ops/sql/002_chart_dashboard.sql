create table if not exists chart (
  id text primary key,
  user_id text not null references app_user(id),
  name text not null,
  description text not null default '',
  program text not null,
  variables_json text not null,
  format_y_as_duration_ms integer not null default 0 check (format_y_as_duration_ms in (0, 1)),
  interpolate_to_latest integer not null default 0 check (interpolate_to_latest in (0, 1)),
  cut_future_datapoints integer not null default 0 check (cut_future_datapoints in (0, 1)),
  default_zoom_window text,
  created_at integer not null,
  updated_at integer not null
);

create index if not exists idx_chart_user_id_name on chart(user_id, name);

create table if not exists dashboard (
  id text primary key,
  user_id text not null references app_user(id),
  name text not null,
  description text not null default '',
  program text not null default '',
  default_zoom_window text,
  override_chart_zoom integer not null default 0 check (override_chart_zoom in (0, 1)),
  layout_json text not null,
  created_at integer not null,
  updated_at integer not null
);

create index if not exists idx_dashboard_user_id_name on dashboard(user_id, name);
