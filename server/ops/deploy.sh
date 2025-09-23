#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/AdamBalski/impulses"

required_vars=(TOKEN REMOTE_HOST REMOTE_PORT REMOTE_USERNAME PORT GOOGLE_OAUTH2_CREDS ORIGIN)

for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var environment variable not set."
        exit 1
    fi
done

ssh "${REMOTE_USERNAME}@${REMOTE_HOST}" -p "$REMOTE_PORT" bash <<EOF
    set -euo pipefail
    echo "==> Killing previous app..."
    pkill -f 'IMPULSES_APP' || true

    echo "==> Cloning/updating repo..."
    [ -d "impulses" ] || git clone $REPO_URL impulses
    cd impulses/server
    [ -d "venv" ] || python3 -m venv venv
    git fetch --all && git reset --hard origin/main
    source ./venv/bin/activate
    pip3 install --upgrade bcrypt uvicorn fastapi apscheduler httpx
    pip3 install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

    echo "==> Starting app..."
    # the last python3 parameter is not used by the app, 
    # but simplifies the above pkill command
    HASHED_TOKEN="\`cat ~/.hashed_impulses_token\`" \
        TOKEN='$TOKEN' \
        PORT='$PORT' \
        GOOGLE_OAUTH2_CREDS='$GOOGLE_OAUTH2_CREDS' \
        ORIGIN='$ORIGIN' \
        nohup python3 -m src.run IMPULSES_APP > stdout 2>&1 &
    disown

    server_status=DOWN
    for i in \`seq 20\`; do
        echo "Waiting for /healthz endpoint to report the server is up..."
        if curl http://localhost:$PORT/healthz | grep UP; then
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

