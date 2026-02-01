#!/usr/bin/env python3

import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ---------------- CONFIG ----------------

EPG_URL = "https://www.1spotmedia.com/index.php/api/epg/get_epg_timeline_by_id"
CHANNEL_ID = "66e312890478fd00235244cb"

TVG_ID = "TVJ.jm@SD"
CHANNEL_NAME = "Television Jamaica"
CHANNEL_ICON = "https://www.televisionjamaica.com/Portals/0/tvj_logo.png"

# Podman/container output path (mount this directory)
OUTPUT_FILE = "/app/output/tvj.xml"

# ----------------------------------------

# Resolve timezone for LOGGING ONLY
TZ_NAME = os.environ.get("TZ", "UTC")
try:
    LOG_TZ = ZoneInfo(TZ_NAME)
except Exception:
    print(f"Invalid TZ '{TZ_NAME}', falling back to UTC")
    LOG_TZ = timezone.utc


def fmt_log_time(dt_utc: datetime) -> str:
    """Format a UTC datetime into the configured log timezone."""
    return dt_utc.astimezone(LOG_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")


def epoch_ms_to_xmltv(ts_ms: int) -> str:
    """Convert epoch milliseconds to XMLTV timestamp (UTC)."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y%m%d%H%M%S +0000")


def clean_text(s):
    if s is None:
        return None
    s = str(s).strip()
    return s if s else None


def get_program_obj(item: dict) -> dict:
    prog = item.get("program")
    return prog if isinstance(prog, dict) else {}


def get_description(item: dict) -> str:
    """
    Extract description from nested program object.
    Treat 'Dummy description.' as missing.
    """
    prog = get_program_obj(item)

    desc = (
        prog.get("longDescription")
        or prog.get("description")
        or prog.get("shortDescription")
    )
    desc = clean_text(desc)

    if desc and desc.lower() == "dummy description.":
        desc = None

    return desc or "No description available."


def get_category(item: dict):
    """Use displayGenre if present."""
    return clean_text(get_program_obj(item).get("displayGenre"))


def add_episode_numbers(programme_el, item: dict):
    """
    Add episode number in xmltv_ns format if possible.
    xmltv_ns: season is 0-based, episode is 0-based.
    """
    prog = get_program_obj(item)

    season = prog.get("tvSeasonNumber")
    episode = prog.get("tvSeasonEpisodeNumber") or prog.get("seriesEpisodeNumber")

    try:
        season_i = int(season) if season is not None else None
    except (ValueError, TypeError):
        season_i = None

    try:
        episode_i = int(episode) if episode is not None else None
    except (ValueError, TypeError):
        episode_i = None

    if season_i is None and episode_i is None:
        return

    # xmltv_ns is 0-based; assume provider values are 1-based if >= 1
    s0 = (season_i - 1) if (season_i is not None and season_i >= 1) else 0
    e0 = (episode_i - 1) if (episode_i is not None and episode_i >= 1) else 0

    ep = ET.SubElement(programme_el, "episode-num", system="xmltv_ns")
    if season_i is not None and episode_i is not None:
        ep.text = f"{s0}.{e0}."
    elif season_i is not None:
        ep.text = f"{s0}.."
    else:
        ep.text = f".{e0}."


def add_date(programme_el, item: dict):
    """
    Add <date>YYYY</date> if we can find a year.
    Try: program.year, else pubDate epoch-ms -> year.
    """
    prog = get_program_obj(item)

    year = prog.get("year")
    year_out = None

    try:
        if year is not None:
            y = int(year)
            if 1800 <= y <= 2100:
                year_out = str(y)
    except (ValueError, TypeError):
        year_out = None

    if year_out is None:
        pub = prog.get("pubDate")
        try:
            if pub is not None:
                dt = datetime.fromtimestamp(int(pub) / 1000, tz=timezone.utc)
                year_out = str(dt.year)
        except (ValueError, TypeError, OSError):
            year_out = None

    if year_out:
        ET.SubElement(programme_el, "date").text = year_out


def add_length(programme_el, item: dict):
    """
    Add <length units="seconds">N</length> from program.runtime if present.
    """
    prog = get_program_obj(item)
    runtime = prog.get("runtime")
    if runtime is None:
        return

    try:
        seconds = int(str(runtime).strip())
        if seconds > 0:
            ET.SubElement(programme_el, "length", units="seconds").text = str(seconds)
    except (ValueError, TypeError):
        return


def main():
    run_time_utc = datetime.now(timezone.utc)
    print(f"[{fmt_log_time(run_time_utc)}] Script run started (TZ={TZ_NAME})")

    resp = requests.get(EPG_URL, params={"id": CHANNEL_ID}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, list) or not data:
        raise RuntimeError("EPG response is empty or invalid (expected a non-empty list).")

    # EPG "updated until" = furthest programme end time in returned schedule
    last_update_epoch = max(int(p["endTime"]) for p in data if "endTime" in p)
    last_update_utc = datetime.fromtimestamp(last_update_epoch / 1000, tz=timezone.utc)

    tv = ET.Element("tv", attrib={"generator-info-name": "1SpotMedia TVJ EPG (enriched)"})

    # Channel block
    ch = ET.SubElement(tv, "channel", id=TVG_ID)
    ET.SubElement(ch, "display-name").text = CHANNEL_NAME
    ET.SubElement(ch, "icon", src=CHANNEL_ICON)

    # Programmes
    for item in data:
        if "startTime" not in item or "endTime" not in item:
            continue

        programme = ET.SubElement(
            tv,
            "programme",
            start=epoch_ms_to_xmltv(int(item["startTime"])),
            stop=epoch_ms_to_xmltv(int(item["endTime"])),
            channel=TVG_ID,
        )

        title = ET.SubElement(programme, "title", lang="en")
        title.text = (
            clean_text(item.get("title"))
            or clean_text(get_program_obj(item).get("title"))
            or "Unknown Program"
        )

        ET.SubElement(programme, "desc", lang="en").text = get_description(item)

        cat = get_category(item)
        if cat:
            ET.SubElement(programme, "category", lang="en").text = cat

        add_episode_numbers(programme, item)
        add_date(programme, item)
        add_length(programme, item)

    # Write XMLTV file (overwrites)
    ET.ElementTree(tv).write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    done_utc = datetime.now(timezone.utc)
    print(f"[{fmt_log_time(done_utc)}] XMLTV written: {OUTPUT_FILE}")
    print(
        f"Summary: Last run={fmt_log_time(run_time_utc)}, "
        f"EPG updated until={fmt_log_time(last_update_utc)}"
    )


if __name__ == "__main__":
    main()
