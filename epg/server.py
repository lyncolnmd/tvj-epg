"""Serve generated files and a live, locally computed health endpoint."""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from epg.health import evaluate


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path.rstrip('/') == '/health':
            self.health()
        else:
            super().do_GET()

    def do_HEAD(self):
        if urlsplit(self.path).path.rstrip('/') == '/health':
            self.health(head=True)
        else:
            super().do_HEAD()

    def health(self, head=False):
        try:
            report = evaluate()
        except Exception:
            report = {'status': 'unhealthy', 'error': 'Health evaluation failed'}
        body = json.dumps(report).encode()
        self.send_response(503 if report['status'] == 'unhealthy' else 200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)


if __name__ == '__main__':
    server = ThreadingHTTPServer(('', int(os.environ.get('PORT', '1876'))),
                                partial(Handler, directory='/app/output'))
    server.serve_forever()
