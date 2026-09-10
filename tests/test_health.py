import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from epg.config import BUILTINS
from epg.engine import run
from epg.health import evaluate, record, state_path
from epg.providers import univtec

NOW = datetime(2026, 9, 10, 12, 30, tzinfo=timezone.utc)


def feed():
    return [{'id': c.channel_id, 'epgObject': {'events': [
        {'title': 'Sport', 'start': '2026-09-10T12:00:00Z', 'end': '2026-09-10T14:00:00Z'}
    ]}} for c in BUILTINS.values()]


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.xml = Path(self.directory.name) / 'tvj.xml'
        self.env = {'CHANNELS': 'tvj,tvjsn', 'OUTPUT_FILE': str(self.xml)}

    def update(self):
        with patch.object(univtec, 'fetch', return_value=feed()):
            run(self.env)
        report = json.loads(state_path(self.xml).read_text())
        report['checked_at'] = NOW.isoformat()
        record(self.xml, report)

    def test_startup_and_success(self):
        self.assertEqual(evaluate(self.env, NOW)['status'], 'unhealthy')
        self.update()
        health = evaluate(self.env, NOW)
        self.assertEqual(health['status'], 'healthy')
        self.assertTrue(all(health['outputs'].values()))
        self.assertEqual(len(health['channels']), 2)

    def test_failure_retains_usable_guide(self):
        self.update()
        before = self.xml.read_bytes()
        with patch.object(univtec, 'fetch', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                run(self.env)
        self.assertEqual(self.xml.read_bytes(), before)
        health = evaluate(self.env, NOW)
        self.assertEqual(health['status'], 'degraded')
        self.assertEqual(health['providers']['univtec']['status'], 'unhealthy')
        self.assertEqual(evaluate(self.env, NOW + timedelta(hours=2))['status'], 'unhealthy')

    def test_missing_channel_and_corrupt_outputs(self):
        self.update()
        with patch.object(univtec, 'fetch', return_value=feed()[:1]):
            with self.assertRaises(ValueError):
                run(self.env)
        health = evaluate(self.env, NOW)
        self.assertEqual(health['status'], 'degraded')
        self.assertEqual(health['channels']['TVJSN.jm@SD']['last_update']['status'], 'unhealthy')
        self.xml.with_suffix('.m3u').write_text('#EXTM3U\n')
        self.assertEqual(evaluate(self.env, NOW)['status'], 'unhealthy')
        self.xml.write_text('broken xml')
        self.assertFalse(evaluate(self.env, NOW)['outputs']['xmltv'])

    def test_future_only_and_overdue(self):
        self.update()
        self.assertEqual(evaluate(self.env, NOW - timedelta(hours=1))['status'], 'unhealthy')
        report = json.loads(state_path(self.xml).read_text())
        report['checked_at'] = (NOW - timedelta(hours=7)).isoformat()
        record(self.xml, report)
        self.assertEqual(evaluate(self.env, NOW)['status'], 'degraded')

    def test_health_requests_do_not_fetch(self):
        self.update()
        with patch.object(univtec, 'fetch') as fetch:
            evaluate(self.env, NOW)
            evaluate(self.env, NOW)
        fetch.assert_not_called()
