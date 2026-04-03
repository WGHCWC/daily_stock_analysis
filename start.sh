#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.yml"

# Docker Compose v2 may route builds through buildx bake by default.
# Some servers still ship an older buildx plugin, so force classic compose
# build mode for wider compatibility.
export COMPOSE_BAKE=false

if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
else
  echo "Error: docker-compose or docker compose is required." >&2
  exit 1
fi

cd "$ROOT_DIR"

echo "==> Using compose command: ${COMPOSE_CMD[*]}"
echo "==> Compose file: $COMPOSE_FILE"
echo "==> COMPOSE_BAKE=$COMPOSE_BAKE"
echo "==> Step 1/3: stopping existing containers"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" down

echo "==> Step 2/3: rebuilding images with no cache"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" build --no-cache

echo "==> Step 3/3: starting containers"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up -d

echo "==> Current container status"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps
