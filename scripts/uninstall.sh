#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/streambox"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/uninstall.sh"
  exit 1
fi

if [[ -d "$APP_DIR" ]]; then
  cd "$APP_DIR"
  docker compose down --remove-orphans || true
fi

rm -rf "$APP_DIR"
echo "Removed: $APP_DIR"