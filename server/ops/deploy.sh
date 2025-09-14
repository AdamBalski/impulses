#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/AdamBalski/impulses"

# Require TOKEN and REMOTE_HOST in env
if [ -z "${TOKEN:-}" ]; then
    echo "ERROR: TOKEN environment variable not set."
    exit 1
fi
if [ -z "${REMOTE_HOST:-}" ]; then
    echo "ERROR: REMOTE_HOST environment variable not set."
    exit 1
fi
if [ -z "${REMOTE_PORT:-}" ]; then
    echo "ERROR: REMOTE_PORT environment variable not set."
    exit 1
fi
if [ -z "${REMOTE_USERNAME:-}" ]; then
    echo "ERROR: REMOTE_USERNAME environment variable not set."
    exit 1
fi
if [ -z "${PORT:-}" ]; then
    echo "ERROR: PORT environment variable not set."
    exit 1
fi
if [ -z "${CREDS:-}" ]; then
    echo "ERROR: CREDS environment variable not set (google oauth2 related)."
    exit 1
fi
if [ -z "${ORIGIN:-}" ]; then
    echo "ERROR: ORIGIN environment variable not set."
    exit 1
fi

ssh "${REMOTE_USERNAME}@${REMOTE_HOST}" -p "$REMOTE_PORT" bash <<EOF
    set -euo pipefail
    echo "==> Killing previous app..."
    pkill -f 'IMPULSES_APP' || true

    echo "==> Cloning/updating repo..."
    [ -d "impulses" ] || git clone $REPO_URL impulses
    cd impulses/server
    [ -d "venv" ] || python3 -m venv venv
    pip3 install bcrypt uvicorn fastapi apscheduler httpx
    git fetch --all && git reset --hard origin/main
    source ./venv/bin/activate

    echo "==> Starting app..."
    # the last python3 parameter is not used by the app, 
    # but simplifies the above pkill command
    HASHED_TOKEN="\`cat ~/.hashed_impulses_token\`" \
        TOKEN='$TOKEN' \
        PORT='$PORT' \
        GOOGLE_OAUTH2_CREDS='$CREDS' \
        nohup python3 -m src.run IMPULSES_APP > stdout 2>&1 &
    disown

    server_status=DOWN
    for i in \`seq 20\`; do
        echo "Waiting for /healthz endpoint to report the server is up..."
        if curl http://localhost:8000/healthz | grep UP; then
            server_status=UP
            break
        fi
        sleep 0.5
    done

    if [ "\$server_status" = "UP" ]; then
        echo "Deployment complete at \$(date)"
    else
        echo "Deployment failed at \$(date)"
        false
    fi
EOF

echo "Deployed successfully to $REMOTE_HOST"

