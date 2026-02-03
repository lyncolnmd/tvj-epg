FROM python:3.11-slim

WORKDIR /app

COPY tvj_epg.py .
COPY tvj.m3u /app/output/tvj.m3u

RUN pip install --no-cache-dir requests

ENV UPDATE_INTERVAL=6
EXPOSE 8787

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
