#!/usr/bin/env bash

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

ssh "$REMOTE_HOST" bash <<EOF
    set -euo pipefail
    echo "==> Killing previous app..."
    pkill -f 'python3 run.py' || true

    echo "==> Cloning/updating repo..."
    if [ -d "impulses" ]; then
        cd impulses/server && git fetch --all && git reset --hard origin/main
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
        nohup python3 run.py > stdout 2>&1 &
    disown
    echo "Deployment complete at \$(date)"
EOF

echo "Deployed successfully to $REMOTE_HOST"

