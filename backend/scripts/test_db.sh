#!/usr/bin/env bash
set -euo pipefail

# Fallback to the project ID if not already exported in the shell environment
export NEON_PROJECT_ID="${NEON_PROJECT_ID:-cold-sky-57169956}"

BRANCH_NAME="test-$(date +%s)-$$"

cleanup() {
  echo "Tearing down Neon branch: $BRANCH_NAME"
  neonctl branches delete "$BRANCH_NAME" --project-id "$NEON_PROJECT_ID" || true
}
trap cleanup EXIT

echo "Creating Neon branch: $BRANCH_NAME"
neonctl branches create \
  --project-id "$NEON_PROJECT_ID" \
  --name "$BRANCH_NAME" \
  --json > /tmp/neon_branch_output.json

export DATABASE_URL=$(neonctl connection-string "$BRANCH_NAME" \
  --project-id "$NEON_PROJECT_ID")

echo "Waiting for branch endpoint to accept connections..."
MAX_ATTEMPTS=60
ATTEMPT=0

# Health check using python/psycopg directly instead of missing psql
CHECK_CMD="import psycopg, os; psycopg.connect(os.environ['DATABASE_URL']).close()"

until uv run python -c "$CHECK_CMD" > /dev/null 2>&1; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
    echo "ERROR: Branch did not accept connections after ${MAX_ATTEMPTS}s" >&2
    exit 1
  fi
  printf "."
  sleep 1
done

echo ""
echo "Branch ready after ${ATTEMPT}s"

echo "Running pytest against $BRANCH_NAME"
uv run pytest "$@"