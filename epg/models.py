"""Common channel and programme definitions shared by providers and writers."""
from dataclasses import dataclass
from datetime import datetime
from xml.etree.ElementTree import Element


@dataclass(frozen=True)
class Channel:
    id: str
    name: str
    stream_url: str
    provider: str = "univtec"
    channel_id: str = ""
    feed_url: str = "https://insight-api-shared.univtec.com/interface/epg"
    tenant: str = "rjr"
    icon: str = ""
    group: str = "General"


@dataclass(frozen=True)
class Programme:
    start: datetime
    stop: datetime
    title: str
    description: str
    # Optional XMLTV elements normalized by the provider (category, rating, etc.).
    metadata: tuple[Element, ...] = ()
