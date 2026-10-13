const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../../docs/assets/site.js'), 'utf8');

async function load(response, cached = null, statsFetch = null) {
  const elements = Object.fromEntries(['#download-button', '#download-label', '#release-status'].map(id => [id, {
    textContent: '', disabled: true,
    classList: { add() {}, remove() {} },
    setAttribute() { this.disabled = true; },
    removeAttribute() { this.disabled = false; },
    addEventListener() {},
  }]));
  if (statsFetch) elements['#download-count'] = { textContent: '', hidden: true };
  if (cached) elements['#download-button'].dataset = cached;
  vm.runInNewContext(code, {
    document: { querySelector: id => elements[id] },
    window: { addEventListener() {} },
    AbortSignal,
    fetch: async (url, options) => url.endsWith('/latest') ? response : statsFetch(url, options),
  });
  await new Promise(resolve => setImmediate(resolve));
  return elements;
}

test('download page does not confuse API rate limiting with an unpublished release', async () => {
  const elements = await load({ ok: false, status: 403 });
  assert.equal(elements['#download-label'].textContent, '前往 GitHub 下载');
  assert.equal(elements['#download-button'].disabled, false);
  assert.match(elements['#download-button'].href, /Atreia-Assistant\/releases$/);
});

test('download page preserves the unpublished state for a missing latest release', async () => {
  const elements = await load({ ok: false, status: 404 });
  assert.equal(elements['#download-label'].textContent, '正式版尚未发布');
  assert.equal(elements['#download-button'].disabled, true);
});

test('download page selects the versioned MSI from a successful release response', async () => {
  const url = 'https://github.com/lulinlulu888-design/Atreia-Assistant/releases/download/v2.0.50/Atreia-Assistant_2.0.50_x64.msi';
  const elements = await load({ ok: true, json: async () => ({ tag_name: 'v2.0.50', assets: [
    { name: 'Atreia-Assistant_2.0.50_x64.msi', size: 29503896, browser_download_url: url },
  ] }) });
  assert.equal(elements['#download-button'].href, url);
  assert.equal(elements['#download-button'].disabled, false);
  assert.equal(elements['#download-label'].textContent, '下载 Windows 2.0.50');
});

test('website keeps the published installer directly downloadable when the release API is unavailable', async () => {
  for (const status of [403, 404, 500]) {
    const elements = await load({ ok: false, status }, { version: '2.0.50', size: '29503896' });
    assert.equal(elements['#download-button'].disabled, false);
    assert.equal(elements['#download-label'].textContent, '下载 Windows 2.0.50');
    assert.equal(elements['#download-button'].href,
      'https://github.com/lulinlulu888-design/Atreia-Assistant/releases/download/v2.0.50/Atreia-Assistant_2.0.50_x64.msi');
    assert.match(elements['#release-status'].textContent, /28\.1 MB/);
  }
});

test('homepage and updater fallback describe the same published installer', () => {
  const html = fs.readFileSync(path.join(__dirname, '../../docs/index.html'), 'utf8');
  const release = JSON.parse(fs.readFileSync(path.join(__dirname, '../../docs/updates/latest.json'), 'utf8'));
  assert.equal(release.draft, false);
  assert.equal(release.prerelease, false);
  assert.match(release.tag_name, /^v\d+\.\d+\.\d+$/);
  const version = release.tag_name.slice(1);
  const name = `Atreia-Assistant_${version}_x64.msi`;
  const assets = release.assets.filter(asset => asset.name === name);
  assert.equal(assets.length, 1);
  const [asset] = assets;
  const url = `https://github.com/lulinlulu888-design/Atreia-Assistant/releases/download/${release.tag_name}/${name}`;
  assert.equal(asset.browser_download_url, url);
  assert.equal(asset.state, 'uploaded');
  assert.match(asset.digest, /^sha256:[a-f0-9]{64}$/);
  assert.ok(Number.isSafeInteger(asset.size) && asset.size > 0);
  assert.ok(html.includes(`data-version="${version}" data-size="${asset.size}" href="${url}"`));
  assert.ok(html.includes(`href="${url}" id="footer-download"`));
  assert.ok(html.includes(`<span class="release-number">${version}</span>`));
  assert.match(html, /id="download-count"[^>]*role="status"[^>]*hidden/);
});

const msi = count => ({ name: 'Atreia-Assistant_2.0.54_x64.msi', download_count: count });
const stable = assets => ({ draft: false, prerelease: false, assets });
const ok = data => ({ ok: true, json: async () => data });
const fallback = { version: '2.0.54', size: '31060604' };

test('download count sums only official Windows installers across releases', async () => {
  const elements = await load({ ok: false, status: 403 }, fallback, async (url, options) => {
    assert.ok(url.endsWith('/releases?per_page=100&page=1'));
    assert.ok(options.signal instanceof AbortSignal);
    return ok([
      stable([msi(1200), { name: 'Atreia-Assistant_2.0.54_build-materials.zip', download_count: 99 }]),
      stable([{ name: 'Atreia-Assistant_2.0.53_x64.msi', download_count: 34 }]),
      { ...stable([msi(500)]), prerelease: true },
      { ...stable([msi(500)]), draft: true },
      stable([{ name: 'SHA256SUMS.txt', download_count: 100 }]),
    ]);
  });
  assert.equal(elements['#download-count'].textContent, '累计下载 1,234 次');
  assert.equal(elements['#download-count'].hidden, false);
  assert.equal(elements['#download-button'].disabled, false);
  assert.equal(elements['#download-label'].textContent, '下载 Windows 2.0.54');
});

test('download count includes all release pages, including an empty last page', async () => {
  for (const lastPage of [[], [stable([msi(7)])]]) {
    const urls = [];
    const elements = await load({ ok: false, status: 403 }, fallback, async url => {
      urls.push(url);
      return ok(urls.length === 1 ? Array.from({ length: 100 }, () => stable([msi(2)])) : lastPage);
    });
    assert.equal(urls.length, 2);
    assert.ok(urls[1].endsWith('&page=2'));
    assert.equal(elements['#download-count'].textContent, `累计下载 ${lastPage.length ? 207 : 200} 次`);
  }
});

test('zero downloads is shown only after a successful valid response', async () => {
  for (const data of [[], [stable([msi(0)])]]) {
    const elements = await load({ ok: false, status: 403 }, fallback, async () => ok(data));
    assert.equal(elements['#download-count'].textContent, '累计下载 0 次');
  }
});

test('rate limits, timeouts and malformed statistics do not disable installer downloads or show fake zero', async () => {
  const cases = [
    async () => ({ ok: false, status: 403 }),
    async () => ({ ok: false, status: 500 }),
    async () => { throw new Error('Network error'); },
    async () => { throw new DOMException('Timed out', 'TimeoutError'); },
    async () => ({ ok: true, json: async () => { throw new Error('Invalid JSON'); } }),
    async () => ok({ message: 'Not releases' }),
    async () => ok([{ draft: false, prerelease: false }]),
    ...[undefined, -1, 1.5, '12', NaN, Infinity, Number.MAX_SAFE_INTEGER + 1].map(count => async () => ok([stable([msi(count)])])),
    async () => ok([stable([msi(Number.MAX_SAFE_INTEGER), msi(1)])]),
  ];
  for (const statsFetch of cases) {
    const elements = await load({ ok: false, status: 403 }, fallback, statsFetch);
    assert.equal(elements['#download-count'].textContent, '下载统计暂不可用');
    assert.equal(elements['#download-button'].disabled, false);
    assert.match(elements['#download-button'].href, /Atreia-Assistant_2\.0\.54_x64\.msi$/);
  }
});

test('a failed later page never displays a partial download total', async () => {
  let calls = 0;
  const elements = await load({ ok: false, status: 403 }, fallback, async () => {
    calls += 1;
    return calls === 1 ? ok(Array.from({ length: 100 }, () => stable([msi(1)]))) : { ok: false, status: 403 };
  });
  assert.equal(calls, 2);
  assert.equal(elements['#download-count'].textContent, '下载统计暂不可用');
});
