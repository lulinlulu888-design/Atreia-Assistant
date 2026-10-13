const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../../docs/assets/site.js'), 'utf8');

async function load(response, cached = null) {
  const elements = Object.fromEntries(['#download-button', '#download-label', '#release-status'].map(id => [id, {
    textContent: '', disabled: true,
    classList: { add() {}, remove() {} },
    setAttribute() { this.disabled = true; },
    removeAttribute() { this.disabled = false; },
    addEventListener() {},
  }]));
  if (cached) elements['#download-button'].dataset = cached;
  vm.runInNewContext(code, {
    document: { querySelector: id => elements[id] },
    window: { addEventListener() {} },
    fetch: async () => response,
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
});
