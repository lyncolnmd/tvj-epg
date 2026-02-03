FROM python:3.11-slim

WORKDIR /app

# Copy the EPG script
COPY tvj_epg.py .

# Copy static M3U playlist
COPY tvj.m3u /app/output/tvj.m3u

# Install requests for API fetching
RUN pip install --no-cache-dir requests

# Default update interval in hours
ENV UPDATE_INTERVAL=6

# Expose the new HTTP server port
EXPOSE 8787

# Start the EPG update loop in background, then start HTTP server
CMD ["python", "tvj_epg.py"]
mkdir -p /app/output; \
# Run update loop in background \
while true; do \
  echo "$(date) - Updating TVJ EPG..."; \
  python tvj_epg.py; \
  echo "$(date) - Sleeping for ${UPDATE_INTERVAL} hours..."; \
  sleep $((${UPDATE_INTERVAL}*3600)); \
done & \
# Start HTTP server to serve XML file on port 8787 \
cd /app/output && python3 -m http.server 8787'
