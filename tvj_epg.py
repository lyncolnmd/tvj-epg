#!/usr/bin/env python3

import os
import re
import html
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ---------------- CONFIG ----------------

EPG_URL = "https://insight-api-shared.univtec.com/interface/epg"

# Stable TVJ object ID returned by the new Univtec API
CHANNEL_ID = "66e312890478fd00235244cb"

TVG_ID = "TVJ.jm@SD"
CHANNEL_NAME = "Television Jamaica"
CHANNEL_ICON = "https://www.televisionjamaica.com/Portals/0/tvj_logo.png"

# Podman/container output path
OUTPUT_FILE = os.environ.get(
    "OUTPUT_FILE",
    "/app/output/tvj.xml",
)

REQUEST_HEADERS = {
    "accept": "application/json",
    "platform": "web",
    "x-tenant-id": "rjr",
}

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


def parse_iso8601(value: str) -> datetime:
    """Parse an ISO-8601 timestamp returned by Univtec."""
    if not value:
        raise ValueError("Empty timestamp")

    # Python accepts +00:00 more consistently than trailing Z.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def datetime_to_xmltv(dt: datetime) -> str:
    """Convert datetime to XMLTV UTC timestamp."""
    return dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000")


def clean_text(value):
    if value is None:
        return None

    value = str(value).strip()
    return value if value else None


def strip_html(value):
    """Convert provider HTML descriptions to normal text."""
    value = clean_text(value)
    if not value:
        return None

    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)

    lines = [line.strip() for line in value.splitlines()]
    value = " ".join(line for line in lines if line)

    return clean_text(value)


def get_custom(item: dict) -> dict:
    custom = item.get("custom")
    return custom if isinstance(custom, dict) else {}


def get_description(item: dict) -> str:
    """
    Prefer the normal description.
    Fall back to custom.longDescription with HTML removed.
    """
    custom = get_custom(item)

    desc = (
        clean_text(item.get("description"))
        or strip_html(custom.get("longDescription"))
    )

    return desc or "No description available."


def add_categories(programme_el, item: dict):
    """Add each provider genre as an XMLTV category."""
    custom = get_custom(item)
    genres = custom.get("genre")

    if isinstance(genres, str):
        genres = [genres]

    if not isinstance(genres, list):
        return

    for genre in genres:
        genre = clean_text(genre)
        if genre:
            ET.SubElement(
                programme_el,
                "category",
                lang="en"
            ).text = genre


def add_episode_numbers(programme_el, item: dict):
    """
    Add episode number using xmltv_ns when available.

    xmltv_ns is zero-based.
    """
    custom = get_custom(item)

    season = custom.get("seasonNumber")
    episode = custom.get("episodeNumber")

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

    s0 = (
        season_i - 1
        if season_i is not None and season_i >= 1
        else 0
    )

    e0 = (
        episode_i - 1
        if episode_i is not None and episode_i >= 1
        else 0
    )

    ep = ET.SubElement(
        programme_el,
        "episode-num",
        system="xmltv_ns"
    )

    if season_i is not None and episode_i is not None:
        ep.text = f"{s0}.{e0}."
    elif season_i is not None:
        ep.text = f"{s0}.."
    else:
        ep.text = f".{e0}."


def add_date(programme_el, item: dict):
    """
    Add <date>YYYY</date> using custom.airDate when available.
    """
    custom = get_custom(item)
    air_date = custom.get("airDate")

    if air_date is None:
        return

    try:
        dt = datetime.fromtimestamp(
            int(air_date) / 1000,
            tz=timezone.utc,
        )

        ET.SubElement(programme_el, "date").text = str(dt.year)

    except (ValueError, TypeError, OSError):
        pass


def add_length(programme_el, item: dict):
    """
    Add programme duration from custom.duration.

    Univtec duration appears to be seconds.
    """
    custom = get_custom(item)
    duration = custom.get("duration")

    if duration is None:
        return

    try:
        seconds = int(duration)

        if seconds > 0:
            ET.SubElement(
                programme_el,
                "length",
                units="seconds"
            ).text = str(seconds)

    except (ValueError, TypeError):
        pass


def add_rating(programme_el, item: dict):
    """Add provider content rating."""
    rating = clean_text(get_custom(item).get("rating"))

    if not rating:
        return

    rating_el = ET.SubElement(programme_el, "rating")
    ET.SubElement(rating_el, "value").text = rating


def add_icon(programme_el, item: dict):
    """Add programme artwork if supplied by Univtec."""
    custom = get_custom(item)

    image = custom.get("image")
    poster = custom.get("poster")

    image_url = None

    if isinstance(image, dict):
        image_url = clean_text(image.get("downloadUrl"))

    if not image_url and isinstance(poster, dict):
        image_url = clean_text(poster.get("downloadUrl"))

    if image_url:
        ET.SubElement(
            programme_el,
            "icon",
            src=image_url,
        )


def fetch_tvj_events():
    """
    Fetch the complete RJR EPG response and extract the TVJ object.
    """
    resp = requests.get(
        EPG_URL,
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()

    data = resp.json()

    if not isinstance(data, list) or not data:
        raise RuntimeError(
            "EPG response is empty or invalid "
            "(expected a non-empty list)."
        )

    channel = next(
        (
            item
            for item in data
            if item.get("id") == CHANNEL_ID
        ),
        None,
    )

    if channel is None:
        raise RuntimeError(
            f"TVJ channel ID {CHANNEL_ID} "
            "was not found in EPG response."
        )

    epg_object = channel.get("epgObject")

    if not isinstance(epg_object, dict):
        raise RuntimeError(
            "TVJ EPG response has no valid epgObject."
        )

    events = epg_object.get("events")

    if not isinstance(events, list):
        raise RuntimeError(
            "TVJ epgObject.events is missing or invalid."
        )

    return events


def main():
    run_time_utc = datetime.now(timezone.utc)

    print(
        f"[{fmt_log_time(run_time_utc)}] "
        f"Script run started (TZ={TZ_NAME})"
    )

    events = fetch_tvj_events()

    # Discard malformed entries and provider filler.
    valid_events = []

    for item in events:
        if not isinstance(item, dict):
            continue

        if not item.get("start") or not item.get("end"):
            continue

        title = clean_text(item.get("title"))

        if title and title.casefold() == "no program":
            continue

        try:
            start_dt = parse_iso8601(item["start"])
            end_dt = parse_iso8601(item["end"])
        except (ValueError, TypeError):
            continue

        if end_dt <= start_dt:
            continue

        valid_events.append((item, start_dt, end_dt))

    if not valid_events:
        raise RuntimeError(
            "No valid TVJ programmes were returned."
        )

    # Sort defensively in case provider changes ordering.
    valid_events.sort(key=lambda x: x[1])

    last_update_utc = max(
        end_dt
        for _, _, end_dt in valid_events
    )

    tv = ET.Element(
        "tv",
        attrib={
            "generator-info-name":
                "Univtec / 1SpotMedia TVJ EPG (enriched)"
        },
    )

    # Channel block
    ch = ET.SubElement(tv, "channel", id=TVG_ID)

    ET.SubElement(
        ch,
        "display-name",
    ).text = CHANNEL_NAME

    ET.SubElement(
        ch,
        "icon",
        src=CHANNEL_ICON,
    )

    # Programmes
    for item, start_dt, end_dt in valid_events:

        programme = ET.SubElement(
            tv,
            "programme",
            start=datetime_to_xmltv(start_dt),
            stop=datetime_to_xmltv(end_dt),
            channel=TVG_ID,
        )

        title = (
            clean_text(item.get("title"))
            or clean_text(get_custom(item).get("seriesTitle"))
            or "Unknown Program"
        )

        ET.SubElement(
            programme,
            "title",
            lang="en",
        ).text = title

        ET.SubElement(
            programme,
            "desc",
            lang="en",
        ).text = get_description(item)

        add_categories(programme, item)
        add_episode_numbers(programme, item)
        add_date(programme, item)
        add_length(programme, item)
        add_rating(programme, item)
        add_icon(programme, item)

    # Ensure output directory exists.
    output_dir = os.path.dirname(OUTPUT_FILE)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Write XMLTV file.
    ET.ElementTree(tv).write(
        OUTPUT_FILE,
        encoding="utf-8",
        xml_declaration=True,
    )

    done_utc = datetime.now(timezone.utc)

    print(
        f"[{fmt_log_time(done_utc)}] "
        f"XMLTV written: {OUTPUT_FILE}"
    )

    print(
        f"Summary: Programmes={len(valid_events)}, "
        f"Last run={fmt_log_time(run_time_utc)}, "
        f"EPG updated until={fmt_log_time(last_update_utc)}"
    )


if __name__ == "__main__":
    main()