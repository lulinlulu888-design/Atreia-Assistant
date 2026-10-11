const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../public/src/js/atreiaLocalization.js'), 'utf8');

function setup(invoke) {
  class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.events = {}; this.value = ''; this.disabled = false; }
    append(...items) { this.children.push(...items); if (items.length && this.tag === 'select' && !this.value) this.value = items[0].value; }
    replaceChildren(...items) { this.children = []; this.append(...items); }
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
  const [, client, pathRow, status, candidates, actions] = dialog.children;
  const [root, browse] = pathRow.children;
  return { dialog, client, root, browse, candidates, status, buttons: actions.children };
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
  assert.equal(ui.status.textContent, '请先点击检测，或选择游戏目录。');
});
test('pending operation locks the selected client, root, actions and closing', async () => {
  let finish;
  const ui = setup(() => new Promise(resolve => { finish = resolve; }));
  ui.root.value = 'D:/Game';
  const pending = ui.buttons[1].events.click();
  assert.equal(ui.client.disabled, true);
  assert.equal(ui.root.disabled, true);
  assert.ok(ui.buttons.every(button => button.disabled));
  assert.equal(ui.browse.disabled, true);
  let prevented = false;
  ui.dialog.events.cancel({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  finish({ message: 'completed' }); await pending;
  assert.equal(ui.client.disabled, false);
  assert.equal(ui.root.disabled, false);
  assert.ok(ui.buttons.every(button => !button.disabled));
});

test('empty detection discovers the selected client and inspects the unique path without installing', async () => {
  const calls = [];
  const ui = setup(async (command, args) => {
    calls.push([command, {...args}]);
    return command === 'discover_localization_roots' ? ['D:/SteamLibrary/AION2'] : {message:'verified'};
  });
  await ui.buttons[0].events.click();
  assert.equal(ui.root.value, 'D:/SteamLibrary/AION2');
  assert.equal(ui.status.textContent, 'verified');
  assert.deepEqual(calls, [
    ['discover_localization_roots', {client:'steam'}],
    ['localization_execute', {root:'D:/SteamLibrary/AION2',client:'steam',operation:'inspect'}],
  ]);
});

test('missing or multiple installations do not start the engine until a target is chosen', async () => {
  for (const roots of [[], ['D:/AION2', 'E:/AION2']]) {
    const calls = [];
    const ui = setup(async command => {calls.push(command); return roots;});
    await ui.buttons[0].events.click();
    assert.deepEqual(calls, ['discover_localization_roots']);
    assert.equal(ui.root.value, '');
    assert.ok(ui.buttons.every(button => !button.disabled));
    if (roots.length) {
      assert.equal(ui.candidates.hidden, false);
      ui.candidates.value = roots[1]; ui.candidates.events.change();
      assert.equal(ui.root.value, roots[1]);
    } else assert.match(ui.status.textContent, /未找到/);
  }
});

test('switching client clears a previous target and cancelled browsing preserves it', async () => {
  const calls = [];
  const ui = setup(async (command, args) => {calls.push([command,args]);return null;});
  ui.root.value = 'D:/Steam/AION2'; ui.client.value = 'purple'; ui.client.events.change();
  assert.equal(ui.root.value, '');
  ui.root.value = 'E:/Purple/AION2'; await ui.browse.events.click();
  assert.equal(ui.root.value, 'E:/Purple/AION2');
  assert.equal(calls[0][0], 'browse_localization_root');
  assert.equal(ui.browse.disabled, false);
});
test('component failure is visible and restores the controls', async () => {
  const ui = setup(async () => { throw new Error('missing translation'); });
  ui.root.value = 'D:/Game';
  await ui.buttons[1].events.click();
  assert.match(ui.status.textContent, /missing translation/);
  assert.ok(ui.buttons.every(button => !button.disabled));
});
