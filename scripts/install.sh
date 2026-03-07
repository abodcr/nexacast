#!/usr/bin/env bash
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root"
  exit 1
fi

apt-get update
apt-get install -y docker.io docker-compose-plugin git

systemctl enable --now docker

mkdir -p /opt/streambox
cp -r . /opt/streambox
cd /opt/streambox

docker compose up -d --build
docker compose ps