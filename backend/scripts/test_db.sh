#!/usr/bin/env bash
set -euo pipefail

# Requires: neonctl installed + authenticated, NEON_PROJECT_ID set
: "${NEON_PROJECT_ID:?Set NEON_PROJECT_ID in your environment}"

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

echo "Running pytest against $BRANCH_NAME"
uv run pytest "$@"