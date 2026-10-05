const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/src/js/atreiaLauncher.js'), 'utf8');
function fixture(invoke) {
  const controls = Object.fromEntries(['combat','localization','status'].map(k => [k, {disabled:false,listeners:{},addEventListener(event,fn){this.listeners[event]=fn;}}]));
  let localized = 0;
  vm.runInNewContext(source, {document:{getElementById:key=>controls[key]},window:{__TAURI__:{core:{invoke}},atreiaOpenLocalization:()=>localized++}});
  return {controls,localized:()=>localized};
}
test('startup and localization action never start capture', () => {
  const calls=[]; const page=fixture(command=>calls.push(command));
  assert.deepEqual(calls, []);
  page.controls.localization.listeners.click();
  assert.equal(page.localized(), 1); assert.deepEqual(calls, []);
});
test('combat is explicit, disables while pending and recovers on cancellation', async () => {
  const calls=[]; const page=fixture(async command=>{calls.push(command);throw new Error('cancelled');});
  const pending=page.controls.combat.listeners.click();
  assert.equal(page.controls.combat.disabled, true);
  await pending; assert.deepEqual(calls, ['open_combat']);
  assert.equal(page.controls.combat.disabled, false);
  assert.match(page.controls.status.textContent, /cancelled/);
});
test('initial native window is launcher only, not an overlay', () => {
  const config=JSON.parse(fs.readFileSync(path.join(__dirname,'../src-tauri/tauri.conf.json'),'utf8'));
  assert.equal(config.app.windows.length,1);
  assert.equal(config.app.windows[0].label,'launcher');
  assert.equal(config.app.windows[0].url,'launcher.html');
  assert.equal(config.app.windows[0].alwaysOnTop,false);
});
test('native setup prepares but does not start Npcap capture', () => {
  const source=fs.readFileSync(path.join(__dirname,'../src-tauri/src/app.rs'),'utf8');
  const setup=source.split('.setup(|app| {')[1].split('.invoke_handler')[0];
  assert.ok(setup.includes('CaptureControl(Mutex::new(capturer))'));
  assert.ok(!setup.includes('capturer.start()'));
});
test('localization belongs to launcher, never to the combat overlay', () => {
  const source=fs.readFileSync(path.join(__dirname,'../public/src/js/atreiaLocalization.js'),'utf8');
  assert.ok(source.includes('localization_execute'));
  assert.ok(!source.includes('open_combat'));
  const html=fs.readFileSync(path.join(__dirname,'../index.html'),'utf8');
  assert.ok(!html.includes('atreiaLocalization'));
  const launcher=fs.readFileSync(path.join(__dirname,'../launcher.html'),'utf8');
  assert.ok(launcher.includes('atreiaLocalization.js'));
  assert.ok(!html.includes('<script src="/src/js/checkRelease.js'));
});
test('PURPLE permits a read-only compatibility check but not installation actions', () => {
  const source=fs.readFileSync(path.join(__dirname,'../public/src/js/atreiaLocalization.js'),'utf8');
  const native=fs.readFileSync(path.join(__dirname,'../src-tauri/src/atreia_localization.rs'),'utf8');
  assert.match(source, /inspect_localization_target/);
  assert.match(source, /purple && operation !== "inspect"/);
  assert.match(native, /pub fn inspect_localization_target/);
  assert.match(native, /"supported": false/);
});
