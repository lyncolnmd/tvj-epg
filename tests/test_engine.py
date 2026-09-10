import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from epg.config import BUILTINS, load
from epg.engine import run
from epg.providers import univtec


def feed():
    return [{"id": c.channel_id, "epgObject": {"events": [
        {"title": "Match & highlights", "start": "2026-09-10T12:00:00Z",
         "end": "2026-09-10T13:00:00Z", "custom": {
             "longDescription": "<p>Live &amp; replay</p>", "genre": ["Sports"],
             "seasonNumber": 2, "episodeNumber": 3, "rating": "G"}},
        {"title": "No Program", "start": "2026-09-10T13:00:00Z", "end": "2026-09-10T14:00:00Z"},
        {"title": "Broken", "start": 123, "end": None},
    ]}} for c in BUILTINS.values()]


class EngineTests(unittest.TestCase):
    def test_selection_validation(self):
        self.assertEqual([c.id for c in load({})[0]], [BUILTINS['tvj'].id])
        self.assertEqual(len(load({'CHANNELS': 'tvjsn,tvjsn'})[0]), 1)
        for selection in ('', 'unknown'):
            with self.assertRaises(ValueError):
                load({'CHANNELS': selection})

    def test_outputs_and_shared_fetch(self):
        for selection in ('tvj', 'tvjsn', 'jnn', 'tvj,tvjsn', 'tvj,tvjsn,jnn'):
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'tvj.xml'
                with patch.object(univtec, 'fetch', return_value=feed()) as fetch:
                    run({'CHANNELS': selection, 'OUTPUT_FILE': str(output)})
                fetch.assert_called_once()
                root = ET.parse(output).getroot()
                ids = [BUILTINS[k].id for k in selection.split(',')]
                self.assertEqual([c.get('id') for c in root.findall('channel')], ids)
                self.assertEqual([p.get('channel') for p in root.findall('programme')], ids)
                playlist = output.with_suffix('.m3u').read_text()
                for key in selection.split(','):
                    self.assertIn(f'tvg-id="{BUILTINS[key].id}"', playlist)
                    self.assertIn(BUILTINS[key].stream_url, playlist)
                self.assertEqual(root.findtext('programme/desc'), 'Live & replay')
                self.assertEqual(root.findtext('programme/episode-num'), '1.2.')
                self.assertEqual(root.findtext('programme/category'), 'Sports')

    def test_failed_update_preserves_files(self):
        for response in ([], feed()[:1]):
            with tempfile.TemporaryDirectory() as directory:
                xml = Path(directory) / 'tvj.xml'
                playlist = Path(directory) / 'tvj.m3u'
                xml.write_text('previous guide')
                playlist.write_text('previous playlist')
                with patch.object(univtec, 'fetch', return_value=response):
                    with self.assertRaises(ValueError):
                        run({'CHANNELS': 'tvj,tvjsn', 'OUTPUT_FILE': str(xml)})
                self.assertEqual(xml.read_text(), 'previous guide')
                self.assertEqual(playlist.read_text(), 'previous playlist')


if __name__ == '__main__':
    unittest.main()
