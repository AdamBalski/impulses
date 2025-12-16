#!/bin/bash
set -e

# Database migration script for Impulses
# Applies all SQL migration files in order

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="$SCRIPT_DIR/sql"

# Check if POSTGRES_CONN_JSON is set
if [ -z "$POSTGRES_CONN_JSON" ]; then
    echo "Error: POSTGRES_CONN_JSON environment variable is not set"
    exit 1
fi

# Parse JSON to extract connection parameters
HOST=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('host', 'localhost'))")
PORT=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('port', 5432))")
DBNAME=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('dbname', 'impulses'))")
USER=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('user', 'postgres'))")
PASSWORD=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('password', ''))")
SSLMODE=$(echo "$POSTGRES_CONN_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('sslmode', 'prefer'))")

# Export for psql
export PGHOST="$HOST"
export PGPORT="$PORT"
export PGDATABASE="$DBNAME"
export PGUSER="$USER"
export PGPASSWORD="$PASSWORD"
export PGSSLMODE="$SSLMODE"

echo "Running database migrations..."
echo "Database: $DBNAME on $HOST:$PORT"

# Apply each SQL file in order
for sql_file in "$SQL_DIR"/*.sql; do
    if [ -f "$sql_file" ]; then
        echo "Applying $(basename "$sql_file")..."
        psql -v ON_ERROR_STOP=1 -f "$sql_file"
        if [ $? -eq 0 ]; then
            echo "✓ $(basename "$sql_file") applied successfully"
        else
            echo "✗ Failed to apply $(basename "$sql_file")"
            exit 1
        fi
    fi
done

echo "All migrations completed successfully"
