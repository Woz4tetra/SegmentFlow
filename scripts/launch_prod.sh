#!/usr/bin/env bash
set -euo pipefail

# Bring the stack up, then rotate the DB password so backend and Postgres stay in sync.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

docker-compose up -d

# Rotate the password after services are up so the new secret is applied and backend restarts.
./scripts/rotate_db_password.sh
