#!/bin/bash
set -e

export FRONTEND_DIR="${FRONTEND_DIR:-/app}"

# Initialize database (idempotent)
(cd /app/dashboard && python -c "from database import init_db; init_db(); print('DB initialized')" 2>/dev/null || true)

# Start FastAPI (uvicorn) on internal port 8000
(cd /app/dashboard && exec uvicorn main:app --host 127.0.0.1 --port 8000) &

# Wait for FastAPI to be ready
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then break; fi
  sleep 1
done

# Start nginx in the foreground (serves public traffic on 8080)
exec nginx -g 'daemon off;'
