#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PROJECT_NAME="impulses-test"
COMPOSE_CMD="docker-compose -p $PROJECT_NAME -f $SCRIPT_DIR/docker-compose.test.yml"

cleanup() {
    echo "Tearing down..."
    $COMPOSE_CMD down -v
}

trap cleanup EXIT

echo "Starting isolated test stack..."
$COMPOSE_CMD up --build -d postgres app

echo "Running tester container..."
TEST_ARGS="$*" $COMPOSE_CMD up --build --abort-on-container-exit tester

echo "Tests completed successfully."
