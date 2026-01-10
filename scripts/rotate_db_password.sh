#!/usr/bin/env bash
set -e

# Rotate the Postgres application user's password and update the Docker secret.
# This script assumes docker-compose is available and the current working
# directory is the project root. It will:
# 1) Generate a new strong password
# 2) Update secrets/postgres_password.txt
# 3) Apply the password to the Postgres role
# 4) Restart the backend to pick up the new secret

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_FILE="$PROJECT_ROOT/secrets/postgres_password.txt"
ROLE="segmentflow"
DB_NAME="segmentflow"

if ! command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose is required" >&2
  exit 1
fi

# Generate a 48-char alphanumeric password
NEW_PW="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)"

# Write secret file with restricted permissions
umask 0077
echo -n "$NEW_PW" > "$SECRET_FILE"

# Apply the password inside the Postgres container
set +e
APPLY_OUTPUT=$(docker-compose exec -T postgres sh -lc "psql -v ON_ERROR_STOP=1 -U $ROLE -d $DB_NAME -c \"ALTER ROLE $ROLE WITH PASSWORD '$NEW_PW';\"" 2>&1)
STATUS=$?
set -e
if [ $STATUS -ne 0 ]; then
  echo "$APPLY_OUTPUT" >&2
  echo "Failed to apply password to Postgres role. Secret file was updated; backend will not authenticate until this is resolved." >&2
  exit $STATUS
fi

# Restart backend to pick up the new secret
docker-compose restart backend

echo "Password rotated successfully. Backend restarted."
