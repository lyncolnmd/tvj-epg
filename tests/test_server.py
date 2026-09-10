import json
import tempfile
import threading
import unittest
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from epg.server import Handler


class ServerTests(unittest.TestCase):
    def test_health_codes_and_static_files(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'tvj.m3u').write_text('#EXTM3U\n')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for status, expected in [('healthy', 200), ('degraded', 200), ('unhealthy', 503)]:
                    with patch('epg.server.evaluate', return_value={'status': status}):
                        connection = HTTPConnection(*server.server_address, timeout=5)
                        connection.request('GET', '/health')
                        response = connection.getresponse()
                        self.assertEqual(response.status, expected)
                        self.assertEqual(json.loads(response.read())['status'], status)
                        connection.close()
                connection = HTTPConnection(*server.server_address, timeout=5)
                connection.request('GET', '/tvj.m3u')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'#EXTM3U\n')
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
