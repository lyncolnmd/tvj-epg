"""Univtec feed adapter and metadata normalization."""
import html
import re
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import requests
from epg.models import Programme

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

    except (ValueError, TypeError, OSError, OverflowError):
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



def fetch(url, tenant):
    response = requests.get(url, headers={
        "accept": "application/json", "platform": "web", "x-tenant-id": tenant,
    }, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Expected a non-empty Univtec channel list")
    return data


def programmes(data, channel_id):
    channel = next((c for c in data if isinstance(c, dict) and c.get("id") == channel_id), None)
    if channel is None:
        raise ValueError(f"Channel {channel_id} missing from feed")
    epg = channel.get("epgObject")
    events = epg.get("events") if isinstance(epg, dict) else None
    if not isinstance(events, list):
        raise ValueError(f"Channel {channel_id} has no valid events list")
    result = []
    for item in events:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title"))
        if title and title.casefold() == "no program":
            continue
        try:
            start = parse_iso8601(item.get("start"))
            stop = parse_iso8601(item.get("end"))
        except (ValueError, TypeError, AttributeError):
            continue
        if stop <= start:
            continue
        # Normalize existing enriched metadata into provider-independent XMLTV fields.
        metadata = ET.Element("metadata")
        for enrich in (add_categories, add_episode_numbers, add_date,
                       add_length, add_rating, add_icon):
            enrich(metadata, item)
        result.append(Programme(
            start, stop,
            title or clean_text(get_custom(item).get("seriesTitle")) or "Unknown Program",
            get_description(item), tuple(metadata),
        ))
    if not result:
        raise ValueError(f"Channel {channel_id} has no valid programmes")
    return sorted(result, key=lambda p: p.start)
