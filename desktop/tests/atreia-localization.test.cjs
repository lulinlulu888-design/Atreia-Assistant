const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/src/js/atreiaLocalization.js'), 'utf8');

function setup(invoke) {
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.events = {}; this.value = ''; this.disabled = false; }
    append(...items) { this.children.push(...items); if (this.tag === 'select' && !this.value) this.value = items[0].value; }
    setAttribute() {}
    addEventListener(name, fn) { this.events[name] = fn; }
    querySelectorAll(tag) { return this.children.filter(child => child.tag === tag); }
    showModal() {}
    close() { this.events.close?.(); }
    remove() {}
  }
  const body = new Element('body');
  const window = { __TAURI__: { core: { invoke } } };
  vm.runInNewContext(source, { window, document: { body, createElement: tag => new Element(tag), querySelector: () => null } });
  window.atreiaOpenLocalization();
  const dialog = body.children[0];
  const [, client, root, status, actions] = dialog.children;
  return { dialog, client, root, status, buttons: actions.children };
}

for (const clientName of ['steam', 'purple']) {
  test(`${clientName}: all three operations use the native selected-client component`, async () => {
    const calls = [];
    const ui = setup(async (command, args) => { calls.push([command, { ...args }]); return { message: 'passed' }; });
    ui.client.value = clientName;
    ui.root.value = ' D:/Game ';
    for (const button of ui.buttons.slice(0, 3)) await button.events.click();
    assert.deepEqual(calls.map(([command, args]) => [command, args.client, args.operation, args.root]),
      ['inspect', 'install', 'restore'].map(operation => ['localization_execute', clientName, operation, 'D:/Game']));
    assert.equal(ui.status.textContent, 'passed');
  });
}
test('empty target never invokes an operation', async () => {
  const ui = setup(() => { throw new Error('must not invoke'); });
  await ui.buttons[1].events.click();
  assert.equal(ui.status.textContent, '请填写游戏目录。');
});
test('pending operation locks the selected client, root, actions and closing', async () => {
  let finish;
  const ui = setup(() => new Promise(resolve => { finish = resolve; }));
  ui.root.value = 'D:/Game';
  const pending = ui.buttons[1].events.click();
  assert.equal(ui.client.disabled, true);
  assert.equal(ui.root.disabled, true);
  assert.ok(ui.buttons.every(button => button.disabled));
  let prevented = false;
  ui.dialog.events.cancel({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  finish({ message: 'completed' }); await pending;
  assert.equal(ui.client.disabled, false);
  assert.equal(ui.root.disabled, false);
  assert.ok(ui.buttons.every(button => !button.disabled));
});
test('component failure is visible and restores the controls', async () => {
  const ui = setup(async () => { throw new Error('missing translation'); });
  ui.root.value = 'D:/Game';
  await ui.buttons[1].events.click();
  assert.match(ui.status.textContent, /missing translation/);
  assert.ok(ui.buttons.every(button => !button.disabled));
});
