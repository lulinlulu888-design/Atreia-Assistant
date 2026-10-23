"""Cache public GitHub installer counts without visitor tracking or credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

API = 'https://api.github.com/repos/lulinlulu888-design/Atreia-Assistant/releases'
INSTALLER = re.compile(r'Atreia-Assistant_\d+\.\d+\.\d+_x64\.msi\Z')
MAX_INTEGER = 2 ** 53 - 1


def fetch_page(page):
    request = Request('{}?per_page=100&page={}'.format(API, page), headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'Atreia-Website-Download-Stats'})
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def collect(fetch=fetch_page):
    total = 0
    seen = set()
    for page in range(1, 101):
        releases = fetch(page)
        if not isinstance(releases, list):
            raise ValueError('Invalid releases')
        for release in releases:
            if not isinstance(release, dict):
                raise ValueError('Invalid release')
            if type(release.get('draft')) is not bool or type(release.get('prerelease')) is not bool:
                raise ValueError('Invalid release status')
            if release['draft'] or release['prerelease']:
                continue
            if not isinstance(release.get('assets'), list):
                raise ValueError('Invalid assets')
            for asset in release['assets']:
                if not isinstance(asset, dict):
                    raise ValueError('Invalid asset')
                if not INSTALLER.fullmatch(str(asset.get('name', ''))):
                    continue
                if asset.get('state') != 'uploaded':
                    raise ValueError('Incomplete installer')
                asset_id, count = asset.get('id'), asset.get('download_count')
                if type(asset_id) is not int or asset_id <= 0 or asset_id in seen:
                    raise ValueError('Invalid or repeated asset')
                seen.add(asset_id)
                if type(count) is not int or count < 0 or count > MAX_INTEGER - total:
                    raise ValueError('Invalid count')
                total += count
        if len(releases) < 100:
            return {'source': 'github', 'count': total,
                    'updated_at': datetime.now(timezone.utc).isoformat()}
    raise ValueError('Pagination limit exceeded')


def refresh(destination, fetch=fetch_page):
    # Never replace the last complete result with a failed or partial total.
    result = collect(fetch)
    destination = Path(destination)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(result) + '\n', encoding='utf-8')
    temporary.replace(destination)
    return result


if __name__ == '__main__':
    print(json.dumps(refresh(sys.argv[1])))
