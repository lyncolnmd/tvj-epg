FROM python:3.11-slim

WORKDIR /app
COPY epg ./epg
COPY tvj_epj.py .
RUN pip install --no-cache-dir requests

ENV UPDATE_INTERVAL=6 PORT=1876
EXPOSE 1876
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
