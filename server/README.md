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
- **PostgresqlDB** Store users and access tokens

---

## 2. Prerequisites

- **Python:** 3.13.1+ recommended
- **OS:** Linux or macOS
- **Database:** PostgreSQL 12+
- **Python dependencies:** See `requirements.txt` (includes FastAPI, PostgreSQL driver, Google client libraries, etc.)

**Environment Variables:**

| Variable Name | Needed to run locally? | Needed for `deploy.sh`? | Needed as GH Action Secret? | Description |
|---------------|----------------------|------------------------|----------------------------|-------------|
| `PORT` | ✔ | ✔ | ✔ | Port the application listens on |
| `GOOGLE_OAUTH2_CREDS` | ✔ | ✔ | ✔ | Google OAuth2 client credentials JSON [(look at the gcal job specific doc)](./G_CAL_POLLING_JOB.md) |
| `ORIGIN` | ✔ | ✔ | ✔ | Protocol + domain + port (for OAuth2 redirects) |
| `POSTGRES_CONN_JSON` | ✔ | ✔ | ✔ | PostgreSQL connection config as JSON string |
| `SESSION_TTL_SEC` | ✘ (defaults to 1800) | ✘ (optional) | ✘ (optional) | Session cookie TTL in seconds |
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
pip install --upgrade pip
pip install -r requirements.txt
```

4. Set up PostgreSQL database and run migrations:

```bash
# Set your PostgreSQL connection config
export POSTGRES_CONN_JSON='{"host":"localhost","port":5432,"dbname":"impulses","user":"your_user","password":"your_password","sslmode":"prefer"}'

# Run database migrations
bash ./ops/db_migrate.sh
```

5. Set additional environment variables:

```bash
export PORT=8000
export GOOGLE_OAUTH2_CREDS='json-string-of-creds'
export ORIGIN='http://localhost:8000'
export POSTGRES_CONN_JSON='{"host":"localhost","port":5432,"dbname":"impulses","user":"your_user","password":"your_password","sslmode":"prefer"}'
# Optional: export SESSION_TTL_SEC=1800
```

6. Run the server:

```bash
python3 -m src.run
```

The server should start and be reachable at `http://localhost:<PORT>`.

---

## 4. Deployment

### 4.1 Docker Deployment (Recommended)

**Quick start with Docker Compose:**

```bash
cd ..  # Go to repository root
cp .env.example .env
# Edit .env and set GOOGLE_OAUTH2_CREDS
make up
```

**What you get:**
- PostgreSQL database (persistent volume)
- Application server with migrations
- File storage for metrics and GCal data (persistent volume)
- Automatic health checks and restarts

**Common commands:**
```bash
make help        # Show all available commands
make logs        # View logs
make db-shell    # Access PostgreSQL
make backup-db   # Backup database
make down        # Stop services
```

See [DOCKER.md](../DOCKER.md) for complete documentation.

### 4.2 Local Development (Manual)
- Run the server directly on your machine without Docker
- Requires manual PostgreSQL setup and venv configuration
- Follow steps in section 3 above

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

Refer to the separate [Google Calendar Polling Job README](./G_CAL_POLLING_JOB.md) for detailed instructions on OAuth2 setup, user authorization, and metric conversion.

---

## 6. API Usage

### Key Endpoints

- `/data` (requires access token)
    - List metrics
    - Fetch datapoints
    - Ingest datapoints
    - Delete metric
- `/user` (session-based authentication)
    - Create user account
    - Login (sets session cookie)
    - Logout (clears session)
    - Refresh session
    - Get current user info
    - Delete user account
- `/token` (requires session authentication)
    - List user's API tokens
    - Create new API token (returns plaintext token once)
    - Delete token by ID
- `/oauth2/google/auth`
    - Redirects user to Google OAuth2 consent page.
- `/oauth2/google/callback`
    - Handles the OAuth2 code exchange and stores credentials.
- `/healthz`
    - Reports whether system is healthy

---

## 7. Data Persistence

- Persistent storage is in: `./data-store/persistent_obj_dir` and postgresql if you wished to back-up the data

---

## 8. Maintenance / Operations

- **Restart server:** Kill previous processes or redeploy.  
- **Monitoring logs:** Logs are stored in a file, e.g. at `./log-2025-09-23_20-01-43`. Latest log is always symlinked from `./log-latest`
- **Updating dependencies:** Update `pip` packages in the virtual environment.
