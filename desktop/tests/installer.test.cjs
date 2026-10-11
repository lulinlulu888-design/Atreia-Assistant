const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

test('MSI requires the built-in desktop shortcut without creating a duplicate', () => {
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, '../src-tauri/tauri.conf.json'), 'utf8'));
  assert.ok(config.bundle.targets.includes('msi'));
  assert.equal(config.bundle.windows.wix.componentRefs.filter(id => id === 'ApplicationShortcutDesktop').length, 1);
});
