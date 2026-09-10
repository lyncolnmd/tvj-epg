#!/bin/sh
set -eu

mkdir -p /app/output
UPDATE_INTERVAL="${UPDATE_INTERVAL:-6}"
export UPDATE_INTERVAL
UPDATE_INTERVAL="$(python -c 'import os; value = os.environ["UPDATE_INTERVAL"]; assert value.isascii() and value.isdigit() and int(value) > 0, "UPDATE_INTERVAL must be a positive integer (hours)"; print(int(value))')"
# Fail fast on invalid channel/output configuration.
python -c 'from epg.config import load; load()'

( while true; do
    echo "$(date) - Updating EPG and playlist..."
    if ! python -m epg.engine; then
        echo "$(date) - Update failed; retrying after ${UPDATE_INTERVAL} hours." >&2
    fi
    sleep "$((UPDATE_INTERVAL * 3600))"
  done
) &

cd /app/output
exec python3 -m http.server 8787
