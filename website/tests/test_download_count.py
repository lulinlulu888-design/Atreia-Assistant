import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('download_count', Path(__file__).parents[1] / 'deploy/update_download_count.py')
stats = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stats)


def release(count=7, asset_id=1, **options):
    return dict(draft=False, prerelease=False, assets=[dict(
        id=asset_id, name='Atreia-Assistant_2.0.62_x64.msi', state='uploaded', download_count=count)], **options)


class DownloadCountTests(unittest.TestCase):
    def test_official_installers_only(self):
        rows = [release(7), release(9, 2), dict(release(100, 3), draft=True),
                dict(release(100, 4), prerelease=True)]
        rows[0]['assets'].append(dict(id=5, name='materials.zip', download_count=999))
        self.assertEqual(stats.collect(lambda _: rows)['count'], 16)

    def test_all_pages_including_empty_last_page(self):
        rows = [release(1, i + 1) for i in range(100)]
        pages = []
        def fetch(page):
            pages.append(page)
            return rows if page == 1 else []
        self.assertEqual(stats.collect(fetch)['count'], 100)
        self.assertEqual(pages, [1, 2])

    def test_valid_zero(self):
        self.assertEqual(stats.collect(lambda _: [release(0)])['count'], 0)

    def test_invalid_counts_and_duplicate_assets(self):
        for invalid in [-1, True, None, 2 ** 53, '5']:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                stats.collect(lambda _: [release(invalid)])
        with self.assertRaises(ValueError):
            stats.collect(lambda _: [release(), release()])

    def test_malformed_response(self):
        for response in [dict(message='rate limited'), [None], [{}], [dict(draft=False, prerelease=False)]]:
            with self.subTest(response=response), self.assertRaises(ValueError):
                stats.collect(lambda _: response)

    def test_failed_later_page_preserves_previous_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'downloads.json'
            path.write_text('{"count": 123}', encoding='utf-8')
            def fetch(page):
                if page == 2:
                    raise TimeoutError('Simulated timeout')
                return [release(1, i + 1) for i in range(100)]
            with self.assertRaises(TimeoutError):
                stats.refresh(path, fetch)
            self.assertEqual(json.loads(path.read_text())['count'], 123)

    def test_successful_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'downloads.json'
            result = stats.refresh(path, lambda _: [release(42)])
            self.assertEqual(json.loads(path.read_text()), result)
            self.assertEqual(result['source'], 'github')
            self.assertFalse(path.with_suffix('.tmp').exists())


if __name__ == '__main__':
    unittest.main()
