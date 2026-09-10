"""Fetch each provider feed once and publish selected channels."""
from datetime import datetime
import sys
from epg.config import load
from epg.providers import PROVIDERS
from epg.writers import atomic_write, m3u, xmltv


def run(environ=None):
    channels, xml_path, m3u_path = load(environ)
    feeds = {}
    schedules = {}
    for channel in channels:
        provider = PROVIDERS[channel.provider]
        key = (channel.provider, channel.feed_url, channel.tenant)
        if key not in feeds:
            feeds[key] = provider.fetch(channel.feed_url, channel.tenant)
        schedules[channel.id] = provider.programmes(feeds[key], channel.channel_id)
    # Fetch and render everything before replacing any previous output.
    xml_content = xmltv(channels, schedules)
    playlist = m3u(channels)
    atomic_write(xml_path, xml_content)
    atomic_write(m3u_path, playlist)
    print(f"[{datetime.now().astimezone().isoformat()}] Wrote {xml_path} and {m3u_path}", flush=True)
    for channel in channels:
        programmes = schedules[channel.id]
        print(f"{channel.name}: {len(programmes)} programmes, through {max(p.stop for p in programmes).isoformat()}", flush=True)


def main():
    try:
        run()
    except Exception as error:
        print(f"EPG update failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
