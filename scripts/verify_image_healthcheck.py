"""Fail publication if the built image lost its automatic healthcheck."""
import json
import sys

images = json.load(sys.stdin)
healthcheck = images[0].get("Config", {}).get("Healthcheck") or {}
expected = ["CMD", "python", "-m", "epg.healthcheck"]
if healthcheck.get("Test") != expected:
    sys.exit("Image healthcheck missing or incorrect; refusing publication")
print("Image healthcheck verified")
