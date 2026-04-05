#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$SCRIPT_DIR/sql"
DB_PATH="${SQLITE_DB_PATH:-$SCRIPT_DIR/../server/data-store/impulses.sqlite3}"

echo "Running database migrations..."
echo "Database: $DB_PATH"

mkdir -p "$(dirname "$DB_PATH")"

for sql_file in "$SQL_DIR"/*.sql; do
    if [ -f "$sql_file" ]; then
        echo "Applying $(basename "$sql_file")..."
        python3 - "$DB_PATH" "$sql_file" <<'PY'
import pathlib
import sqlite3
import sys

db_path = sys.argv[1]
sql_path = pathlib.Path(sys.argv[2])
sql = sql_path.read_text()

with sqlite3.connect(db_path) as conn:
    conn.execute("pragma foreign_keys = on")
    conn.executescript(sql)
    conn.commit()
PY
        echo "✓ $(basename "$sql_file") applied successfully"
    fi
done

echo "All migrations completed successfully"
