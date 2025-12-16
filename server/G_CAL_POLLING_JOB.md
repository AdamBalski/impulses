# Google Calendar Polling Job

## 1. Overview

The GCal Polling Job is a background job in the Impulses server that periodically fetches events from Google Calendar for registered users and converts relevant events into metric data. This enables tracking custom user-defined metrics over time using calendar events.

Key points:  
- Runs as a background job inside the Impulses server every five minutes.
- Runs once on server startup in addition to the interval schedule.
- Fetches events from users’ primary Google Calendars.  
- Users authenticate using OAuth2.  
- Synchronizes events with the server's persistent datastore.  
- Converts events with special summaries (`#!`) into metrics.  

---
## 2. Flow
![Impulses OAuth2 + GCal + API Flow](https://www.plantuml.com/plantuml/svg/dLDBJzmm4BxdLqnJgGArcxGzKgMyGVHG40jIRyZOGt1nxCWFw9RotpiZhz528u6wbtZjRxx7ZBqLel0n3QOICZeFvm5zDTAMbdeKDa9zD8p910nmVbI3uC_qESpHtw8dJ5a-nHqwrnk4u-qKhpypQhcSHEqAWrO93zidMVMGTYebehWK0Q4-GHzqY4WbUxGPo3eo3lPsgghhbjHmODmTT5t5gM3sbRp31kmQBM-WtdNMeepmJB6k24JG787WX_jdq3h1V6tFM6pv3wpzcB7qxCpTe5slblWYSbydR-eDg9kcgHyoPt6r0JlUtR4bAsvrBo86Y0we81jTHVBNUVqRGOnZbRTViYU5CPT2tcnAfx0Z0-z2915U5Pkh4lk_vBMmFGB3uSfvY1mfJAcTOapU5i0Z6RMT3kSy1P0U5TgeXGcGhABpdWorkQIzZ_ozqEgXNG4-xzufAkrvED71id8pXxl8KJjH-gB-eFVEyz1xcY6CpXXjU_ZfBc7D9ni0YNa1L_eMOT0sHGnVW3GTy2auAn54XFmEndNekXKtVEt8pm56USr4DbAemFo1mofO3S7WYMwLkZLi-WP26WRX5tGpthuX0vQuwW-WC4YlnwYTfHEboGtvwZvzf5-zFjdeGYi231Yzbe5lFXpPYBqNpCIPOWgSwEKxBPszqdsOljP5cHA99vdXFOI5bS1A-0WkO_msF_uEcJYREzsVd_6JXXH4Z-Lb_ckD7tghXx796HkLSg99EoKzxSmckbzgbxXLaonUR1QMLpgIAKGtD6LI_sCiKq2XUAM_BRGg3UOl)
---

## 3. OAuth2 Setup
To allow the server to fetch calendar events, each user must authorize the Impulses app with Google OAuth2.

Steps for the deployer:  
1. Obtain Google OAuth2 credentials for your app from [Google Cloud Console](https://console.cloud.google.com/apis/credentials).  
2. Ensure the OAuth2 client has the following scopes:
   - `https://www.googleapis.com/auth/calendar.readonly`  
   - `https://www.googleapis.com/auth/userinfo.email`  
3. Set `GOOGLE_OAUTH2_CREDS` environment variable on the server with the JSON credentials.  
4. Set `ORIGIN` (UI origin) and `ORIGIN_API` (API origin) environment variables.

Steps for the user
1. UI calls `GET /oauth2/google/auth` (with `X-Data-Token`) and receives `{"url": "..."}`.
2. Browser navigates to the provided URL.
3. After authorization, Google redirects to `GET /oauth2/google/callback?code=...&state=...`.
4. Server stores credentials for the `token_id` and redirects back to the UI (currently `/tokens?...`).
---

## 4. Polling Mechanics

- The job runs every 300 seconds.
- For each user, it:
  1. Loads valid credentials.
  2. Reads last sync token (if available).
  3. Fetches incremental changes from Google Calendar.
  4. Applies changes to local storage (`./data-store/persistent_obj_dir`).
  5. Converts events into metrics using `#!`-prefixed summaries.

Credentials and state are stored per token under:

```text
gcal/tokens/{token_id}/credentials
gcal/tokens/{token_id}/sync_state
gcal/tokens/{token_id}/event_state
```

The server also exposes `GET /oauth2/google/configs` (requires `X-Data-Token`) to list which tokens are connected and their sync state.

---

## 5. Event-to-Metric Conversion

- Only events whose titles start with `#!` are converted into metrics.
- Event start and end times are used to calculate metric values (duration in milliseconds).  
- Metadata from the description can be extracted using the following patterns:  
  - `key:value` → adds a dimension key/value pair to the duration metric and the custom metrics
  - `metric=value` → adds a custom metric.

Example:

```text
Summary: "#!Running"
Description:
"""
where:park
distance=10000
"""
```

- Summary (`#!Running`) → `activity` dimension.  
- `where` → custom dimension.  
- `distance` → custom metric value.  

Metrics are written to the datastore with appropriate names, e.g.:  
- `imp.events.duration`  
- `imp.events.custom.distance`

Both metrics will have three dimensions: `where`, `activity` and `src` (event id in google response).

---
