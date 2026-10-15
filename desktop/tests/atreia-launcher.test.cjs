const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../public/src/js/atreiaLauncher.js'), 'utf8');
function fixture(invoke) {
  const controls = Object.fromEntries(['combat','localization','status','npcap-download'].map(k => [k, {disabled:false,hidden:k==='npcap-download',listeners:{},addEventListener(event,fn){this.listeners[event]=fn;}}]));
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

test('Npcap help is initially hidden and opens only the fixed official page after an explicit click', async () => {
  const html=fs.readFileSync(path.join(__dirname,'../launcher.html'),'utf8');
  assert.match(html, /<button\b[^>]*id="npcap-download"[^>]*\bhidden>/);
  const calls=[];
  const page=fixture(async (command,args)=>{
    calls.push([command,args]);
    if(command==='open_combat') throw '未能加载 Npcap。请从 Npcap 官网安装驱动，安装完成后重试。';
  });
  const help=page.controls['npcap-download'];
  assert.equal(help.hidden,true);
  await help.listeners.click(); assert.equal(calls.length,0);
  await page.controls.combat.listeners.click();
  assert.equal(help.hidden,false);
  assert.equal(calls.length,1); // No automatic browser, download or capture.
  await help.listeners.click();
  assert.equal(JSON.stringify(calls[1]),JSON.stringify(['open_url',{url:'https://npcap.com/#download'}]));
  assert.equal(help.disabled,false);
  assert.equal(help.hidden,false);
  assert.match(page.controls.status.textContent,/未能加载 Npcap/);
});

test('Npcap help is not offered for unrelated errors and disappears on retry and success', async () => {
  let attempt=0;
  const page=fixture(async ()=>{
    attempt++;
    if(attempt===1) throw new Error('未能加载 Npcap。请安装驱动。');
    if(attempt===2) throw '请等待汉化操作完成。';
  });
  await page.controls.combat.listeners.click(); assert.equal(page.controls['npcap-download'].hidden,false);
  const retry=page.controls.combat.listeners.click(); assert.equal(page.controls['npcap-download'].hidden,true);
  await retry; assert.equal(page.controls['npcap-download'].hidden,true);
  await page.controls.combat.listeners.click();
  assert.equal(page.controls.status.textContent,'战斗统计已开启');
  assert.equal(page.controls['npcap-download'].hidden,true);
});

test('Npcap page opening blocks duplicate clicks and remains retryable on failure', async () => {
  let rejectOpen,opens=0;
  const page=fixture(command=>{
    if(command==='open_combat') return Promise.reject('未能加载 Npcap。请安装驱动。');
    opens++; return new Promise((_,reject)=>{rejectOpen=reject;});
  });
  await page.controls.combat.listeners.click();
  const help=page.controls['npcap-download'];
  const pending=help.listeners.click();
  assert.equal(help.disabled,true);
  await help.listeners.click(); assert.equal(opens,1);
  rejectOpen('浏览器启动失败'); await pending;
  assert.equal(help.disabled,false); assert.equal(help.hidden,false);
  assert.match(page.controls.status.textContent,/https:\/\/npcap.com\/#download/);
  assert.equal(page.controls.status.title,page.controls.status.textContent);
});

test('a delayed browser error cannot overwrite a subsequent combat status', async () => {
  let rejectOpen,attempt=0;
  const page=fixture(command=>{
    if(command==='open_combat') return ++attempt===1 ? Promise.reject('未能加载 Npcap。请安装驱动。') : Promise.resolve();
    return new Promise((_,reject)=>{rejectOpen=reject;});
  });
  await page.controls.combat.listeners.click();
  const pending=page.controls['npcap-download'].listeners.click();
  await page.controls.combat.listeners.click();
  rejectOpen('late error'); await pending;
  assert.equal(page.controls.status.textContent,'战斗统计已开启');
  assert.equal(page.controls['npcap-download'].hidden,true);
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
test('PURPLE is routed to the selected client and has installation actions', () => {
  const source=fs.readFileSync(path.join(__dirname,'../public/src/js/atreiaLocalization.js'),'utf8');
  const native=fs.readFileSync(path.join(__dirname,'../src-tauri/src/atreia_localization.rs'),'utf8');
  assert.match(source, /const command = "localization_execute"/);
  assert.ok(!source.includes('inspect_localization_target'));
  assert.ok(!source.includes('purple && operation !== "inspect"'));
  assert.match(native, /pub fn inspect_localization_target/);
  assert.match(native, /arg\(&client\)/);
});
