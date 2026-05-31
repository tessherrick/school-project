#!/bin/bash
# Production run command. DigitalOcean App Platform sets $PORT.
PORT="${PORT:-8000}"
exec gunicorn backend.main:app \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:$PORT \
  --access-logfile - \
  --error-logfile -
