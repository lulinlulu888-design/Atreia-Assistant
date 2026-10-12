const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

test('launcher uses planned client area and all controls remain in its fixed grid', () => {
  const config = JSON.parse(read('src-tauri/tauri.conf.json'));
  const window = config.app.windows[0];
  assert.deepEqual([window.width, window.height], [680, 500]);
  assert.equal(window.theme, 'Light');
  const css = read('src/launcher.css');
  assert.match(css, /height: 100dvh/);
  assert.match(css, /grid-template-rows:/);
  assert.match(css, /max-height: 380px/);
  assert.match(css, /html, \.launcher-body[^}]*overflow: hidden/);
  for (const id of ['combat', 'localization', 'status', 'update-check', 'update-install', 'update-status']) {
    assert.ok(read('launcher.html').includes(`id="${id}"`));
  }
});

test('launcher, localization and all combat tool windows share the same material', () => {
  for (const entry of ['launcher.html', 'index.html']) assert.match(read(entry), /src\/neumorphic.css/);
  assert.match(read('index.html'), /src\/neumorphic-meter.css/);
  assert.match(read('src/atreia.css'), /var\(--neo-surface\)/);
  assert.match(read('src/neumorphic.css'), /--neo-inset: inset/);
  assert.match(read('src/neumorphic.css'), /prefers-reduced-motion/);
  assert.ok(!read('public/src/js/atreiaLocalization.js').includes("background:'#142230'"));
  const meter = read('src/neumorphic-meter.css');
  for (const name of ['settingsPanel','historyPanel','detailsPanel','legacyUi']) assert.ok(meter.includes(name));
  assert.match(meter, /\.settingsFooter[^}]*flex-shrink: 0/);
  assert.match(meter, /\.settingsBody[^}]*overflow-y: auto/);
});

test('long status messages keep full text available and version badge matches native version', () => {
  for (const file of ['public/src/js/atreiaLauncher.js','public/src/js/atreiaUpdate.js']) {
    assert.match(read(file), /status\.title = message/);
  }
  const version = JSON.parse(read('package.json')).version;
  assert.equal(JSON.parse(read('src-tauri/tauri.conf.json')).version, version);
  assert.ok(read('launcher.html').includes(`v${version}`));
});

test('native simulation fixtures cannot be shipped as desktop resources', () => {
  assert.ok(!fs.existsSync(path.join(root, 'dist/visual-tests')));
  assert.ok(!read('dist/launcher.html').includes('native-fixture'));
  assert.ok(!read('dist/index.html').includes('native-fixture'));
  assert.match(read('vite.config.ts'), /configureServer\(server\)/);
  assert.ok(!read('launcher.html').includes('__visual'));
});
