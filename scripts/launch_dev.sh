#!/usr/bin/env bash
set -euo pipefail

# Bring the stack up, then rotate the DB password so backend and Postgres stay in sync.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
export VITE_API_URL=http://megamind:8000/api/v1

PW_FILE="${PROJECT_ROOT}"/secrets/postgres_password.txt

if [[ -f "${PW_FILE}" || -s "${PW_FILE}" ]]; then
    ./scripts/create_db_password.sh
fi

docker-compose down backend frontend || true

docker-compose up -d --build

./scripts/rotate_db_password.sh || true
