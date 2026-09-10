"""Health from local update results and the files actually served to clients."""
import json
import os
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from epg.config import load
from epg.writers import atomic_write


def state_path(xml_path):
    return xml_path.with_suffix('.health.json')


def record(xml_path, report):
    atomic_write(state_path(xml_path), json.dumps(report).encode())


def evaluate(environ=None, now=None):
    channels, xml_path, m3u_path = load(environ)
    now = now or datetime.now(timezone.utc)
    try:
        report = json.loads(state_path(xml_path).read_text())
        if not isinstance(report, dict):
            raise ValueError('Invalid health state')
    except (OSError, ValueError):
        report = {}
    outputs = {'xmltv': False, 'm3u': False}
    root = None
    playlist = ''
    try:
        root = ET.parse(xml_path).getroot()
        outputs['xmltv'] = root.tag == 'tv'
    except (OSError, ET.ParseError):
        pass
    try:
        playlist = m3u_path.read_text()
        outputs['m3u'] = playlist.startswith('#EXTM3U\n')
    except (OSError, UnicodeError):
        pass
    details = {}
    for channel in channels:
        intervals = []
        declared = False
        if outputs['xmltv']:
            declared = any(c.get('id') == channel.id for c in root.findall('channel'))
            for p in root.findall('programme'):
                if p.get('channel') != channel.id:
                    continue
                try:
                    start, stop = (datetime.strptime(p.get(k, ''), '%Y%m%d%H%M%S %z') for k in ('start', 'stop'))
                    if stop > start and p.findtext('title'):
                        intervals.append((start, stop))
                except ValueError:
                    pass
        current = any(start <= now < stop + timedelta(seconds=1) for start, stop in intervals)
        future = any(stop > now for _, stop in intervals)
        lines = playlist.splitlines()
        in_playlist = any(
            line.startswith('#EXTINF:') and f'tvg-id="{channel.id}"' in line
            and i + 1 < len(lines) and lines[i + 1] == channel.stream_url
            for i, line in enumerate(lines)
        )
        usable = declared and current and future and outputs['m3u'] and in_playlist
        details[channel.id] = {
            'name': channel.name, 'status': 'healthy' if usable else 'unhealthy',
            'programmes': len(intervals), 'covers_now': current, 'has_future_data': future,
            'in_playlist': in_playlist,
            'guide_until': max((stop for _, stop in intervals), default=None).isoformat() if intervals else None,
            'last_update': report.get('channels', {}).get(channel.id),
        }
    env = os.environ if environ is None else environ
    try:
        last_attempt = datetime.fromisoformat(report['checked_at'])
        overdue = now - last_attempt > timedelta(hours=int(env.get('UPDATE_INTERVAL', '6')), minutes=5)
    except (KeyError, ValueError, TypeError):
        overdue = True
    usable = all(c['status'] == 'healthy' for c in details.values()) and all(outputs.values())
    status = 'unhealthy' if not usable else ('degraded' if overdue or not report.get('success') else 'healthy')
    return {
        'status': status, 'checked_at': now.isoformat(),
        'last_attempt': report.get('checked_at'), 'update_overdue': overdue,
        'last_update_success': report.get('success', False),
        'providers': report.get('providers', {}), 'channels': details, 'outputs': outputs,
        'output_error': report.get('output_error'),
    }
