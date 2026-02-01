import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# 1SpotMedia API config
API_URL = "https://www.1spotmedia.com/index.php/api/epg/get_epg_timeline_by_id"
CHANNEL_ID = "66e312890478fd00235244cb"
TVG_ID = "TVJ.jm@SD"

# Output file
OUTPUT_FILE = "/app/output/tvj.xml"

# Record script start time
script_run_time = datetime.now(tz=timezone.utc)
print(f"[{script_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}] Script run started.")

# Fetch EPG data
resp = requests.get(API_URL, params={"id": CHANNEL_ID}, headers={"User-Agent": "Mozilla/5.0"})
data = resp.json()

# Determine last update time from API if available
if isinstance(data, dict) and "lastUpdate" in data:
    # API may provide a timestamp in milliseconds
    api_last_update_ts = data["lastUpdate"]
    last_update_time = datetime.fromtimestamp(api_last_update_ts / 1000, tz=timezone.utc)
elif isinstance(data, list) and len(data) > 0:
    # Fallback: use the latest program endTime
    last_update_time = datetime.fromtimestamp(max(p["endTime"] for p in data) / 1000, tz=timezone.utc)
else:
    last_update_time = script_run_time

# Ensure we have a list of programs
if isinstance(data, dict):
    programs = data.get("data", [])
elif isinstance(data, list):
    programs = data
else:
    programs = []

# Create XMLTV root
tv = ET.Element("tv", attrib={"generator-info-name": "custom-1spotmedia"})

# Add channel
channel = ET.SubElement(tv, "channel", id=TVG_ID)
ET.SubElement(channel, "display-name").text = "TVJ SD"

# Add programs
for p in programs:
    start = datetime.fromtimestamp(p["startTime"] / 1000, tz=timezone.utc)
    stop  = datetime.fromtimestamp(p["endTime"] / 1000, tz=timezone.utc)

    programme = ET.SubElement(tv, "programme",
                              start=start.strftime("%Y%m%d%H%M%S +0000"),
                              stop=stop.strftime("%Y%m%d%H%M%S +0000"),
                              channel=TVG_ID)
    ET.SubElement(programme, "title").text = p["title"]
    if "description" in p:
        ET.SubElement(programme, "desc").text = p["description"]

# Write XMLTV file
tree = ET.ElementTree(tv)
tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

# Log completion with timestamps
completion_time = datetime.now(tz=timezone.utc)
print(f"[{completion_time.strftime('%Y-%m-%d %H:%M:%S UTC')}] XMLTV guide updated successfully: {OUTPUT_FILE}")
print(f"Summary: Script run time = {script_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}, Last guide update from API = {last_update_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
