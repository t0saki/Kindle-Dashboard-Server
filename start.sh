#!/bin/bash
set -e

# Default Port if not set
PORT=${PORT:-5000}

# Start the application in the background
echo "[Entrypoint] Starting application on port $PORT..."
# Using exec format from Dockerfile but in shell:
# "uv run gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 app:app"
# We need to ensure we capture the PID
uv run gunicorn -w 2 --worker-class gthread --threads 4 -b 0.0.0.0:$PORT --timeout 120 app:app &
APP_PID=$!

# Wait for the app to initialize
echo "[Entrypoint] Waiting for application to start..."
sleep 10

# Start the watchdog in the background
echo "[Entrypoint] Starting watchdog (uptime monitor)..."
uv run python3 uptime_monitor.py &
WATCHDOG_PID=$!

# Wait for any process to exit
# If the app crashes, we want the container to exit (so Docker restarts it)
# If the watchdog kills the container (PID 1), it kills this script.
# We use `wait -n` to wait for the first process to exit.
wait -n

# Exit with the status of the process that exited first
exit $?
