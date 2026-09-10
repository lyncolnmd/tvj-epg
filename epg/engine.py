"""Fetch each provider feed once and publish selected channels."""
from datetime import datetime, timezone
import sys
from epg.config import load
from epg.health import record
from epg.providers import PROVIDERS
from epg.writers import atomic_write, m3u, xmltv


def run(environ=None):
    channels, xml_path, m3u_path = load(environ)
    feeds = {}
    schedules = {}
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'success': False, 'providers': {}, 'channels': {}}
    errors = []
    for channel in channels:
        provider = PROVIDERS[channel.provider]
        key = (channel.provider, channel.feed_url, channel.tenant)
        if key not in feeds:
            try:
                feeds[key] = provider.fetch(channel.feed_url, channel.tenant)
                report['providers'][channel.provider] = {'status': 'healthy'}
            except Exception as error:
                feeds[key] = error
                report['providers'][channel.provider] = {
                    'status': 'unhealthy', 'error': type(error).__name__}
        try:
            if isinstance(feeds[key], Exception):
                raise feeds[key]
            schedules[channel.id] = provider.programmes(feeds[key], channel.channel_id)
            report['channels'][channel.id] = {'status': 'healthy'}
        except Exception as error:
            errors.append(error)
            report['channels'][channel.id] = {
                'status': 'unhealthy', 'error': type(error).__name__}
    if errors:
        record(xml_path, report)
        raise errors[0]
    # Fetch and render everything before replacing any previous output.
    try:
        xml_content = xmltv(channels, schedules)
        playlist = m3u(channels)
        atomic_write(xml_path, xml_content)
        atomic_write(m3u_path, playlist)
        report['success'] = True
    except Exception as error:
        report['output_error'] = type(error).__name__
        raise
    finally:
        record(xml_path, report)
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
