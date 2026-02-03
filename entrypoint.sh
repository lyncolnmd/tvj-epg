#!/bin/sh
set -eu

mkdir -p /app/output
UPDATE_INTERVAL="${UPDATE_INTERVAL:-6}"

( while true; do
    echo "$(date) - Updating TVJ EPG..."
    python /app/tvj_epg.py
    echo "$(date) - Sleeping for ${UPDATE_INTERVAL} hours..."
    sleep "$((UPDATE_INTERVAL * 3600))"
  done
) &

cd /app/output
exec python3 -m http.server 8787
