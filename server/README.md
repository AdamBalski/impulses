# Impulses Server

## 1. Overview

The Impulses Server is a Python-based backend that provides:

- Persistent storage for metric data and metadata.
- Background jobs for data processing, including Google Calendar integration.
- A REST API for clients to ingest and fetch metric data.
- OAuth2-based user authentication for accessing Google Calendar events.

**Components:**

- **API server:** FastAPI-based REST API handling requests from clients.
- **Background jobs:** Heartbeat job, Google Calendar polling job.
- **Datastore:** Persistent storage for metrics under `./data-store/persistent_obj_dir`.
- **OAuth2 handling:** Manages user credentials and refresh tokens for Google Calendar access.

---

## 2. Prerequisites

- **Python:** 3.10+ recommended
- **OS:** Linux or macOS
- **Python dependencies:** `bcrypt`, `uvicorn`, `fastapi`, `apscheduler`, `httpx`, Google client libraries (`google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`).

**Environment Variables:**

| Variable Name | Needed to run locally? | Needed for `deploy.sh`? | Needed as GH Action Secret? | Description |
|---------------|----------------------|------------------------|----------------------------|-------------|
| `PORT` | ✔ | ✔ | ✔ | Port the application listens on |
| `TOKEN` | ✔ | ✔ | ✔ | Server authentication token |
| `HASHED_TOKEN` | ✔ | ✘ | ✘ | Bcrypt hash of `TOKEN` |
| `GOOGLE_OAUTH2_CREDS` | ✔ | ✔ | ✔ | Google OAuth2 client credentials JSON (look at the gcal specific doc) |
| `ORIGIN` | ✔ | ✔ | ✔ | Protocol + domain + port (for OAuth2 redirects) |
| `REMOTE_HOST` | ✘ | ✔ | ✔ | Hostname for SSH deployment |
| `REMOTE_PORT` | ✘ | ✔ | ✔ | SSH port for remote host |
| `REMOTE_USERNAME` | ✘ | ✔ | ✔ | Username for SSH deployment |


## 3. Run locally

1. Clone the repository:

```bash
git clone https://github.com/AdamBalski/impulses.git
cd impulses/server
```

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source ./venv/bin/activate
```

3. Install dependencies:

```bash
pip install --upgrade bcrypt uvicorn fastapi apscheduler httpx
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

4. Set environment variables:

```bash
export PORT=8000
export TOKEN='your-token'
export HASHED_TOKEN='bcrypt-hashed-token'
export GOOGLE_OAUTH2_CREDS='json-string-of-creds'
export ORIGIN='http://localhost:8000'
```

5. Run the server:

```bash
python3 -m src.run
```

The server should start and be reachable at `http://localhost:<PORT>`.

---

## 4. Deployment

### 4.1 Local Deployment
- Simply run the server as above on your local machine.
- Useful for development and testing.

### 4.2. Token rotation
- The deployment via `deploy.sh` and the GH action require the hashed token to be available on the server, to set it up run:
```bash
# needs `bcrypt` python3 package, so best to run it in a virtual environment with `bcrypt` installed
chmod +x ./server/ops/token_update.sh
./server/ops/token_update.sh
```
### 4.3 Deploy via `deploy.sh`
- Requires SSH access and environment variables set (look at the table).
- Usage:

```bash
chmod +x ./server/ops/deploy.sh
./server/ops/deploy.sh
```

- The script will:
  1. Kill any previous instance of the server.
  2. Clone or update the repo on the remote host.
  3. Set up a virtual environment and install dependencies.
  4. Start the server in the background.
  5. Wait for `/healthz` to report the server is UP.

### 4.4 Deploy via GitHub Actions
- Indirect deployment using the `deploy.sh` script.
- Workflow triggers the remote deployment via SSH automatically.
- Ensure all required secrets are configured in the GitHub repository (look at the table)

---

## 5. Background Jobs

### Heartbeat Job
- Runs periodically to check server health.
- Updates internal status for monitoring.

### Google Calendar Polling Job
- Runs every 120 seconds to fetch user events.
- Converts events with summaries starting with `#!` into metric data.
- Reads last sync tokens to fetch only new events.
- Updates local persistent datastore at `./data-store/persistent_obj_dir`.

Refer to the separate [Google Calendar Polling Job README](./gcal_polling_job.md) for detailed instructions on OAuth2 setup, user authorization, and metric conversion.

---

## 6. API Usage

### Authentication
- Clients must provide `X-Token` header with the app token. The token is the same as the token used to run the app.

### Key Endpoints (TODO auto-generated docs)

- `/data` (requires `X-Token`)
  - List metrics
  - Fetch datapoints
  - Ingest datapoints
  - Delete metric
- `/oauth2/google/auth`  
  - Redirects user to Google OAuth2 consent page.
- `/oauth2/google/callback`  
  - Handles the OAuth2 code exchange and stores credentials.
- `/healthz`  
  - Reports whether system is healthy

---

## 7. Data Persistence

- Persistent storage is in: `text ./data-store/persistent_obj_dir` if you wished to back-up the data

---

## 8. Maintenance / Operations

- **Rotate tokens:** Use `./server/token_update.sh` to update the hashed token on the remote host.  
- **Restart server:** Kill previous processes or redeploy.  
- **Monitoring logs:** Logs are stored in a file, e.g. at `./log-2025-09-23_20-01-43`. Latest log is always symlinked from `./log-latest`
- **Updating dependencies:** Update `pip` packages in the virtual environment.
