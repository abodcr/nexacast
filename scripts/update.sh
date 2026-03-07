#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/streambox"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/update.sh"
  exit 1
fi

cd "$APP_DIR"
docker compose pull
docker compose up -d
docker compose ps