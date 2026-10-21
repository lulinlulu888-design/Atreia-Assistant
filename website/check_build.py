"""Read-only static output checks; no network calls or game access."""
from html.parser import HTMLParser
from fnmatch import fnmatchcase
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / '.output/public'


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.canonical = []
        self.headings = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('img', 'script') and attrs.get('src'):
            self.assets.append(attrs['src'])
        if tag == 'link' and attrs.get('rel') == 'stylesheet':
            self.assets.append(attrs['href'])
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonical.append(attrs['href'])
        self.headings += tag == 'h1'


def main():
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    url = urlsplit(release['url'])
    assert url.scheme == 'https'
    assert url.hostname == 'atreia-downloads-487694861369.s3.ap-southeast-1.amazonaws.com'
    assert url.path == f"/releases/v{release['version']}/Atreia-Assistant_{release['version']}_x64.msi"
    assert len(release['sha256']) == 64 and int(release['sha256'], 16) >= 0
    assert release['size'] > 0
    for name in ('index.html', 'guides/localization.html', 'guides/combat.html'):
        path = PUBLIC / name
        page = Page()
        raw = path.read_text(encoding='utf-8')
        page.feed(raw)
        assert page.headings == 1, name
        assert len(page.canonical) == 1 and page.canonical[0].startswith('https://a2go.cc/'), name
        for asset in page.assets:
            parts = urlsplit(asset)
            if parts.scheme or parts.netloc:
                continue
            target = PUBLIC / unquote(parts.path.lstrip('/')) if parts.path.startswith('/') else path.parent / unquote(parts.path)
            assert target.is_file(), (name, asset)
    home = (PUBLIC / 'index.html').read_text(encoding='utf-8')
    assert release['url'] in home and release['version'] in home
    policy = json.loads((ROOT / 'deploy/s3-download-policy.json').read_text(encoding='utf-8'))
    assert len(policy['Statement']) == 1
    statement = policy['Statement'][0]
    assert statement['Action'] == 's3:GetObject'
    assert all('/releases/*/' in resource for resource in statement['Resource'])
    assert statement['Condition']['Bool']['aws:SecureTransport'] == 'true'
    trust = json.loads((ROOT / 'deploy/github-oidc-trust.json').read_text())['Statement'][0]
    assert trust['Action'] == 'sts:AssumeRoleWithWebIdentity'
    conditions = trust['Condition']
    assert conditions['StringEquals'] == {'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com'}
    subjects = conditions['StringLike']['token.actions.githubusercontent.com:sub']
    for subject in ('repo:lulinlulu888-design/Atreia-Assistant:ref:refs/tags/v2.0.63',
                    'repo:lulinlulu888-design@336265304/Atreia-Assistant@1404887480:ref:refs/tags/v2.0.63'):
        assert any(fnmatchcase(subject, pattern) for pattern in subjects)
    for subject in ('repo:lulinlulu888-design/Atreia-Assistant:ref:refs/heads/main',
                    'repo:lulinlulu888-design/Atreia-Assistant:pull_request',
                    'repo:other/Atreia-Assistant:ref:refs/tags/v2.0.63'):
        assert not any(fnmatchcase(subject, pattern) for pattern in subjects)
    publisher = json.loads((ROOT / 'deploy/github-s3-publish-policy.json').read_text())['Statement'][0]
    assert publisher['Action'] == ['s3:GetObject', 's3:PutObject']
    assert publisher['Condition']['Bool']['aws:SecureTransport'] == 'true'
    for resource in ('arn:aws:s3:::atreia-downloads-487694861369/private.txt',
                     'arn:aws:s3:::atreia-downloads-487694861369/releases/v2.0.63/source.zip',
                     'arn:aws:s3:::hczs-cdn-487694861369/releases/v2.0.63/SHA256SUMS.txt'):
        assert not any(fnmatchcase(resource, pattern) for pattern in publisher['Resource'])
    for name in ('nginx-http.conf', 'nginx-https.conf'):
        conf = (ROOT / 'deploy' / name).read_text(encoding='utf-8')
        assert 'default_server' not in conf and 'hczs' not in conf
        assert '/srv/atreia/www/current' in conf
    print('PASS: generated pages, assets, canonical URLs, release binding and isolated deployment configuration')


if __name__ == '__main__':
    main()
