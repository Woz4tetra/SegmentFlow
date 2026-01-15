#!/usr/bin/env bash
set -e

# Create a new secret password key
# 1) Generate a new strong password
# 2) Update secrets/postgres_password.txt

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="$PROJECT_ROOT/secrets/postgres_password.txt"

if ! command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose is required" >&2
  exit 1
fi

# Generate a 48-char alphanumeric password
NEW_PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)"

# Write secret file with restricted permissions
umask 0077
echo -n "$NEW_PW" > "$SECRET_FILE"

echo "Password rotated successfully."
