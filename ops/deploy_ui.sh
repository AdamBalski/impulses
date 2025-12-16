#!/usr/bin/env bash
set -euo pipefail

required_vars=(REMOTE_HOST REMOTE_PORT REMOTE_USERNAME ORIGIN_UI ORIGIN_API)

for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var environment variable not set."
        exit 1
    fi
done

UI_PORT="${UI_PORT:-443}"

repo_root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ui_src_dir="$repo_root_dir/ui"
ui_dist_dir="$ui_src_dir/dist"

rm -rf "$ui_dist_dir"

(
    cd "$ui_src_dir"
    npm ci
    VITE_API_URL="$ORIGIN_API" npm run build
)

tmp_tar="$(mktemp -t impulses-ui-dist.XXXXXX).tgz"
trap 'rm -f "$tmp_tar"' EXIT

tar -czf "$tmp_tar" -C "$ui_dist_dir" .

scp -P "$REMOTE_PORT" "$tmp_tar" "${REMOTE_USERNAME}@${REMOTE_HOST}:impulses-ui.tgz"

ssh "${REMOTE_USERNAME}@${REMOTE_HOST}" -p "$REMOTE_PORT" bash <<EOF
    set -euo pipefail

    mkdir -p impulses-ui
    rm -rf impulses-ui-tmp
    tar -xzf impulses-ui.tgz -C impulses-ui-tmp
    mv impulses-ui-tmp impulses-ui
EOF

echo "Deployed successfully to $REMOTE_HOST"
