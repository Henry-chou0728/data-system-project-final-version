#!/bin/bash
set -e

python - <<'PY'
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database import engine

for attempt in range(1, 31):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database is ready.")
        break
    except OperationalError as exc:
        print(f"Waiting for database... attempt {attempt}/30")
        if attempt == 30:
            raise exc
        time.sleep(2)
PY

if [ "${RUN_CREATE_TABLES:-true}" = "true" ]; then
  python create_tables.py
fi

if [ "${RUN_SEED:-false}" = "true" ]; then
  python seed.py
fi

# Start the FastAPI server.
# Railway private networking may require listening on IPv6 (::).
exec uvicorn app.main:app --host "${BIND_HOST:-0.0.0.0}" --port "${PORT:-8000}"
