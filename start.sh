#!/bin/bash
set -e

# Set frontend directory
export FRONTEND_DIR="/app"

# Initialize database
cd /app/dashboard
python -c "from database import init_db; init_db(); print('DB initialized')" 2>/dev/null || true

# Start the combined server (serves both API + frontend static files)
exec uvicorn main:app --host 0.0.0.0 --port 8080
