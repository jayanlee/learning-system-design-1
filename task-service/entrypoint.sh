#!/bin/sh
set -e
if [ "${ROLE:-api}" = "consumer" ]; then
  exec python -m app.consumer
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
