# Google Calendar Polling Job

## 1. Overview

The GCal Polling Job is a background job in the Impulses server that periodically fetches events from Google Calendar for registered users and converts relevant events into metric data. This enables tracking custom user-defined metrics over time using calendar events.

Key points:  
- Runs as a background job inside the Impulses server every two minutes.
- Fetches events from users’ primary Google Calendars.  
- Users authenticate using OAuth2.  
- Synchronizes events with the server's persistent datastore.  
- Converts events with special summaries (`#!`) into metrics.  

---
## 2. Flow
![Impulses OAuth2 + GCal + API Flow](https://img.plantuml.biz/plantuml/png/dPJRRjim38Rl_HISTzC2gxFjCe3Nmv86tSLQ9Eq3C1BdQ9KbGuTbtTEFKcmd7J8Wg6yiqpz_Vg9eN_c0BiHM5oY2TV3aoHKTXvHG7Pe0vLtRHUt9muhSBt8buB1yhLjOssY2--iODf-pQhSyglgAcen41zSFTrcxu4WXCU0QFK7vGCuh7uXJPXpqZ4PPDxifYhhkhU5MsotKTP6euU9BpmLJMCmVOM8nYIPDBZb93qKlO6bEcSAIf78a0WGxy0vcVOqffBjrwWy1TbtHXuzOh54ymrQ53GWhwIGeWLgdjCkKKLTLTK0urf__5Xiq3MLR-C6d5Emp6N-0CjPOKeZE38AzsIXOfLP2J6p2aUGEAzG-zRJX8u3EQgrC0p_j6ivSD1w8yruWR2sqoiH0_ZnrVE-SJevzRoc8JHARuDa-UUHJaw_APF4HtZxlZAgc0X_R5jtB5ChtxnZ1i5Vv0IHvuLGNb3NyHl9qe15KV_h8Ltb-03Ix6RVPs_BSj1IS4ZuFptA-Uao3nvZ8NVtl_AHndAYsgtOsbOmEK_b_Qoq9vLY08nT7DZZazhhHOZz6trRtt_UOfn69o3rkgw4PRm7RMS1WSIBV5N-zwQVn5m00iagram)
---

## 3. OAuth2 Setup
To allow the server to fetch calendar events, each user must authorize the Impulses app with Google OAuth2.

Steps for the deployer:  
1. Obtain Google OAuth2 credentials for your app from [Google Cloud Console](https://console.cloud.google.com/apis/credentials).  
2. Ensure the OAuth2 client has the following scopes:
   - `https://www.googleapis.com/auth/calendar.readonly`  
   - `https://www.googleapis.com/auth/userinfo.email`  
3. Set `GOOGLE_OAUTH2_CREDS` environment variable on the server with the JSON credentials.  

Steps for the user
1. User visits the `/oauth2/google/auth` endpoint to authorize the app.  
---

## 4. Polling Mechanics

- The job runs every 120 seconds.
- For each user, it:
  1. Loads valid credentials.
  2. Reads last sync token (if available).
  3. Fetches new events from Google Calendar.
  4. Applies changes to local storage (`./data-store/persistent_obj_dir`).
  5. Converts events into metrics using `#!`-prefixed summaries.

---

## 5. Event-to-Metric Conversion

- Only events whose titles start with `#!` are converted into metrics.
- Event start and end times are used to calculate metric values (duration in milliseconds).  
- Metadata from the description can be extracted using the following patterns:  
  - `key:value` → adds a dimension key/value pair to the duration metric and the custom metrics
  - `metric=value` → adds a custom metric.

Example:

```text
#!Running
where:park
distance=10000
```

- Summary (`#!Running`) → `activity` dimension.  
- `where` → custom dimension.  
- `distance` → custom metric value.  

Metrics are written to the datastore with appropriate names, e.g.:  
- `imp.events.duration`  
- `imp.events.custom.distance`

Both metrics will have three dimensions: `where`, `activity` and `src` (event id in google response).

---
