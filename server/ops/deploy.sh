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

ssh "${REMOTE_USERNAME}@${REMOTE_HOST}" -p "$REMOTE_PORT" bash <<EOF
    set -euo pipefail
    echo "==> Killing previous app..."
    pkill -f 'python3 -m src.run' || true

    echo "==> Cloning/updating repo..."
    if [ -d "impulses" ]; then
        git fetch --all && git reset --hard origin/main
        cd impulses/server
        source ./venv/bin/activate
    else
        git clone $REPO_URL impulses
        cd impulses/server
        python3 -m venv venv
        source ./venv/bin/activate
        pip3 install bcrypt
    fi

    echo "==> Starting app..."
    HASHED_TOKEN="\`cat ~/.hashed_impulses_token\`"\
        TOKEN='$TOKEN'\
        nohup python3 -m src.run > stdout 2>&1 &
    disown
    for i in `seq 20`; do
    server_status=DOWN
        echo "Waiting for /healthz endpoint to report the server is up..."
        if curl -fs http://localhost:8080/health | grep UP; then
            server_status=UP
            break
        fi
        sleep 0.5
    done

    if [ \$server_status = UP ]; then
        echo "Deployment complete at \$(date)"
    else
        echo "Deployment failed at \$(date)"
        false
    fi
EOF

echo "Deployed successfully to $REMOTE_HOST"

