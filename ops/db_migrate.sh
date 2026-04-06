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
sql_name = sql_path.name
sql = sql_path.read_text()

with sqlite3.connect(db_path) as conn:
    conn.execute("pragma foreign_keys = on")
    conn.execute(
        """
        create table if not exists schema_migration (
            name text primary key,
            applied_at integer not null default (strftime('%s', 'now'))
        )
        """
    )
    already_applied = conn.execute(
        "select 1 from schema_migration where name = ?",
        [sql_name],
    ).fetchone()
    if already_applied:
        print(f"Skipping {sql_name}, already applied")
        conn.commit()
        raise SystemExit(0)

    try:
        conn.executescript(sql)
    except sqlite3.OperationalError as exc:
            raise

    conn.execute(
        "insert into schema_migration(name) values (?)",
        [sql_name],
    )
    conn.commit()
PY
        echo "✓ $(basename "$sql_file") applied successfully"
    fi
done

echo "All migrations completed successfully"
