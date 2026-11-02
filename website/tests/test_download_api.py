import importlib.util
import http.client
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from uuid import uuid4

SPEC = importlib.util.spec_from_file_location('download_api', Path(__file__).parents[1] / 'server/download_api.py')
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


class Store:
    def __init__(self):
        self.requests = {}
        self.fail = False

    def record(self, request_id, version):
        if self.fail:
            raise RuntimeError('Simulated database failure')
        self.requests.setdefault(request_id, version)

    def statistics(self):
        if self.fail:
            raise RuntimeError('Simulated database failure')
        return {'source': 'official_website', 'count': len(self.requests), 'metric': 'download_clicks'}


class DownloadApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'release.json'
        self.release = dict(version='2.0.62', url='https://{}/releases/v2.0.62/Atreia-Assistant_2.0.62_x64.msi'.format(api.BUCKET))
        self.path.write_text(json.dumps(self.release), encoding='utf-8')
        self.store = Store()
        self.server = api.ThreadingHTTPServer(('127.0.0.1', 0), api.handler_class(self.store, self.path))
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, method='POST', path='/api/download', body=None, origin=api.ORIGIN, accept='text/html'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Origin': origin, 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': accept}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), json.loads(response.read())
        connection.close()
        return result

    def test_reading_statistics_never_counts_visits(self):
        for _ in range(2):
            self.assertEqual(self.request('GET', '/api/downloads')[2]['count'], 0)
        self.assertEqual(len(self.store.requests), 0)

    def test_download_records_and_redirects_to_exact_s3_installer(self):
        status, headers, _ = self.request(body='version=2.0.62&request_id=' + str(uuid4()))
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], self.release['url'])
        self.assertEqual(len(self.store.requests), 1)

    def test_repeated_request_id_counts_once(self):
        body = 'version=2.0.62&request_id=' + str(uuid4())
        self.request(body=body)
        self.request(body=body)
        self.assertEqual(len(self.store.requests), 1)

    def test_enhanced_download_returns_json_without_following_s3(self):
        status, headers, data = self.request(body='version=2.0.62', accept='application/json')
        self.assertEqual(status, 200)
        self.assertEqual(data, {'download_url': self.release['url']})
        self.assertNotIn('Location', headers)
        self.assertEqual(len(self.store.requests), 1)

    def test_get_prefetch_does_not_count_or_start_download(self):
        self.assertEqual(self.request('GET')[0], 404)
        self.assertEqual(len(self.store.requests), 0)

    def test_other_origins_rejected(self):
        self.assertEqual(self.request(body='version=2.0.62', origin='https://other.example')[0], 403)
        self.assertEqual(len(self.store.requests), 0)

    def test_stale_version_rejected_without_increment(self):
        self.assertEqual(self.request(body='version=2.0.61')[0], 409)
        self.assertEqual(len(self.store.requests), 0)

    def test_no_javascript_form_still_downloads(self):
        self.assertEqual(self.request(body='version=2.0.62')[0], 303)
        self.assertEqual(len(self.store.requests), 1)

    def test_malformed_fields_rejected(self):
        for body in ('version=2.0.62&version=2.0.62', 'version=2.0.62&url=https://evil.example',
                     'version=2.0.62&request_id=invalid', 'x=' + 'a' * 300):
            self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(len(self.store.requests), 0)

    def test_database_failure_preserves_download_not_fake_zero(self):
        self.store.fail = True
        self.assertEqual(self.request(body='version=2.0.62')[0], 303)
        self.assertEqual(self.request('GET', '/api/downloads')[0], 503)

    def test_unapproved_redirect_destination_rejected(self):
        self.release['url'] = 'https://evil.example/installer.msi'
        self.path.write_text(json.dumps(self.release), encoding='utf-8')
        self.assertEqual(self.request(body='version=2.0.62')[0], 400)
        self.assertEqual(len(self.store.requests), 0)


if __name__ == '__main__':
    unittest.main()
