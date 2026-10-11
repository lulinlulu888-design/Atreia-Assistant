const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../../docs/assets/site.js'), 'utf8');

async function load(response) {
  const elements = Object.fromEntries(['#download-button', '#download-label', '#release-status'].map(id => [id, {
    textContent: '', disabled: true,
    classList: { add() {}, remove() {} },
    setAttribute() { this.disabled = true; },
    removeAttribute() { this.disabled = false; },
    addEventListener() {},
  }]));
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
