#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running Alembic migrations..."
  runuser -u skp -- env DATABASE_URL="$DATABASE_URL" alembic upgrade head
fi

if [ "${APP_ROLE:-api}" = "connector-sync-worker" ]; then
  exec runuser -u skp -- python -m app.workers.connector_sync_worker
fi

exec runuser -u skp -- uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${UVICORN_WORKERS:-1}"
