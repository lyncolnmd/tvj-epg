FROM python:3.11-slim

WORKDIR /app
COPY epg ./epg
COPY tvj_epj.py .
RUN pip install --no-cache-dir requests

ENV UPDATE_INTERVAL=6 PORT=1876
EXPOSE 1876
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD ["python", "-m", "epg.healthcheck"]
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
