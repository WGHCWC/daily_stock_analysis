#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.yml"
IMAGE_NAME="daily-stock-analysis:latest"

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
echo "==> Image name: $IMAGE_NAME"
echo "==> Mode: full rebuild without compose build"
echo "==> Step 1/3: stopping existing containers"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" down

echo "==> Step 2/3: rebuilding image with classic docker build"
DOCKER_BUILDKIT=0 docker build -f docker/Dockerfile -t "$IMAGE_NAME" .

echo "==> Step 3/3: starting containers without compose build"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" up -d --no-build --force-recreate

echo "==> Current container status"
"${COMPOSE_CMD[@]}" -f "$COMPOSE_FILE" ps
