"""Local-only website download gateway; no GitHub totals or visitor identifiers."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs
from uuid import UUID, uuid4

ORIGIN = 'https://a2go.cc'
BUCKET = 'atreia-downloads-487694861369.s3.ap-southeast-1.amazonaws.com'


def load_release(path):
    release = json.loads(Path(path).read_text(encoding='utf-8'))
    version = release['version']
    if not re.fullmatch(r'2\.[0-9]+\.[0-9]+', version):
        raise ValueError('Invalid release version')
    expected = 'https://{}/releases/v{}/Atreia-Assistant_{}_x64.msi'.format(BUCKET, version, version)
    if release['url'] != expected:
        raise ValueError('Download destination must be the official versioned S3 installer')
    return release


class MongoStore:
    def __init__(self, uri):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000,
                                  socketTimeoutMS=3000, retryWrites=False)
        self.database = self.client['atreia_website']
        self.events = self.database['download_requests']

    def record(self, request_id, version):
        # Unique request IDs deduplicate browser retries; no IP, UA or user ID is stored.
        self.events.update_one({'_id': request_id}, {'$setOnInsert': {
            'version': version, 'requested_at': datetime.now(timezone.utc)}}, upsert=True)

    def statistics(self):
        return {'source': 'official_website', 'count': self.events.count_documents({}),
                'metric': 'download_clicks', 'since': '2026-10-28'}


def handler_class(store, release_path):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'AtreiaDownload'

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_):
            pass

        def respond(self, status, payload, location=None):
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if location:
                self.send_header('Location', location)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != '/api/downloads':
                self.respond(404, {'error': 'not_found'})
                return
            try:
                self.respond(200, store.statistics())
            except Exception:
                self.respond(503, {'error': 'statistics_unavailable'})

        def do_POST(self):
            if self.path != '/api/download':
                self.respond(404, {'error': 'not_found'})
                return
            if self.headers.get('Origin') != ORIGIN:
                self.respond(403, {'error': 'origin_rejected'})
                return
            if self.headers.get('Sec-Fetch-Site') not in (None, 'same-origin'):
                self.respond(403, {'error': 'cross_site_rejected'})
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                self.respond(415, {'error': 'unsupported_content_type'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                body = self.rfile.read(length) if 0 < length <= 4096 else b''
                if not 0 < length <= 256:
                    raise ValueError('Invalid size')
                fields = parse_qs(body.decode('ascii'), strict_parsing=True)
                if set(fields) - {'version', 'request_id'} or any(len(v) != 1 for v in fields.values()):
                    raise ValueError('Invalid fields')
                release = load_release(release_path)
                if fields.get('version') != [release['version']]:
                    self.respond(409, {'error': 'release_changed_reload_page'})
                    return
                request_id = str(UUID(fields.get('request_id', [str(uuid4())])[0]))
            except (ValueError, KeyError, UnicodeError):
                self.respond(400, {'error': 'invalid_request'})
                return
            except Exception:
                self.respond(503, {'error': 'download_unavailable'})
                return
            try:
                store.record(request_id, release['version'])
            except Exception:
                # A database outage must not prevent a real installer download.
                # Do not invent a successful statistic when recording failed.
                print('Download counter write failed; redirect preserved', file=sys.stderr, flush=True)
            if 'application/json' in self.headers.get('Accept', ''):
                self.respond(200, {'download_url': release['url']})
            else:
                self.respond(303, {'status': 'redirecting'}, release['url'])

    return Handler


if __name__ == '__main__':
    store = MongoStore(os.environ.get('MONGODB_URI', 'mongodb://127.0.0.1:27017'))
    if '--check' in sys.argv:
        print(json.dumps(store.statistics()))
        sys.exit(0)
    release_path = os.environ.get('ATREIA_RELEASE_FILE', '/srv/atreia/www/current/download-release.json')
    load_release(release_path)
    ThreadingHTTPServer(('127.0.0.1', 8765), handler_class(store, release_path)).serve_forever()
