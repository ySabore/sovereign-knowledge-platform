#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running Alembic migrations..."
  runuser -u skp -- env DATABASE_URL="$DATABASE_URL" alembic upgrade head
fi

exec runuser -u skp -- \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
