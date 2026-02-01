# Use slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy script
COPY tvj_epg.py .

# Install requests
RUN pip install --no-cache-dir requests

# Default update interval (hours)
ENV UPDATE_INTERVAL=6

# Run the script in a loop, using UPDATE_INTERVAL env variable
CMD sh -c 'while true; do \
      echo "$(date) - Updating TVJ EPG..."; \
      python tvj_epg.py; \
      echo "$(date) - Sleeping for ${UPDATE_INTERVAL} hours..."; \
      sleep $((${UPDATE_INTERVAL}*3600)); \
    done'
