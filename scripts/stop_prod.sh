#!/usr/bin/env bash
set -euo pipefail

# Bring the stack down (stop all services).
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

docker-compose down
