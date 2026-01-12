#!/usr/bin/env bash
set -euo pipefail

# Run SegmentFlow database migrations from Bash.
# Uses DATABASE_URL if set; otherwise falls back to config loading defaults.
# Optional: set SEGMENTFLOW_SQLITE_POOL=NullPool for SQLite tests.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON_BIN="${PYTHON_BIN:-$BACKEND_DIR/venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found at $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN or create the backend venv." >&2
  exit 1
fi

cd "$BACKEND_DIR"

echo "Running migrations with $PYTHON_BIN ..."
"$PYTHON_BIN" -m app.scripts.apply_migrations

echo "Migrations complete."
