#!/usr/bin/env bash
set -euo pipefail

# Bring the stack up, then rotate the DB password so backend and Postgres stay in sync.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

docker-compose down
