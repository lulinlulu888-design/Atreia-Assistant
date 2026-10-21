const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../public/src/js/atreiaRadar.js'),'utf8');
function fixture(handler, saved={}, label='radar') {
  class Element {
    constructor(){this.children=[];this.attributes={};this.events={};this.style={setProperty(){}};this.value='';this.type='';this.hidden=false;}
    setAttribute(k,v){this.attributes[k]=v;} append(...nodes){this.children.push(...nodes);}
    replaceChildren(...nodes){this.children=nodes;} get firstChild(){return this.children[0];}
    addEventListener(k,fn){this.events[k]=fn;} focus(){this.focused=true;}
    cloneNode(){const e=new Element();e.textContent=this.textContent;return e;}
  }
  const ids=['radar','range','opacity','player-color','cube-color','sound','volume','opacity-value','volume-value','range-label','settings','settings-toggle','settings-close','sound-preview','drag','close','power','status','nearest','elevation','visible','count','cubes'];
  const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));const el=elements;
  Object.assign(el.range,{value:'150'});Object.assign(el.opacity,{value:'40',type:'range',min:'0',max:'100'});
  Object.assign(el.volume,{value:'40',type:'range',min:'0',max:'100'});
  Object.assign(el['player-color'],{value:'#7bdac6',type:'color'});Object.assign(el['cube-color'],{value:'#e8bd75',type:'color'});
  Object.assign(el.sound,{checked:false,type:'checkbox'});el.settings.hidden=true;el.visible.append({textContent:'0'});
  el.radar.getContext=()=>new Proxy({},{get:(o,k)=>o[k]||(()=>{}),set:(o,k,v)=>(o[k]=v,true)});
  const timers=[],calls=[],listeners={};let closed=0;
  vm.runInNewContext(source,{
    document:{body:{classList:{add(){},toggle(){}}},getElementById:id=>el[id],querySelector:()=>new Element(),addEventListener(){},createElement:()=>new Element(),createTextNode:text=>({textContent:text})},
    window:{__TAURI__:{core:{invoke:async command=>{calls.push(command);return handler(command);}},event:{listen:(name,fn)=>{listeners[name]=fn;return Promise.resolve(()=>{});},emit:()=>Promise.resolve()},window:{getCurrentWindow:()=>({label,close:()=>closed++,startDragging(){}})}}},
    localStorage:{getItem:()=>JSON.stringify(saved),setItem(){}},setTimeout:fn=>timers.push(fn),
  });
  return {el,calls,timers,listeners,closed:()=>closed};
}
const snapshot=(extra={})=>({active:false,data:{player:null,cubes:[],position_age_ms:null,frames:0,discoveries:0,...extra}});
const tick=()=>new Promise(setImmediate);
test('radar opens stopped and never starts capture or audio on its own',async()=>{
  const ui=fixture(()=>snapshot());await tick();assert.deepEqual(ui.calls,['get_settings','fit_radar_window','radar_snapshot']);
  assert.equal(ui.el.status.textContent,'未开启');assert.equal(ui.el.power.attributes['aria-pressed'],'false');
});
test('start is explicit, duplicates are blocked, and cancellation remains visible',async()=>{
  let reject;const ui=fixture(cmd=>cmd==='start_radar'?new Promise((_,r)=>reject=r):snapshot());await tick();
  const pending=ui.el.power.onclick();await ui.el.power.onclick();await tick();
  assert.equal(ui.el.power.disabled,true);assert.equal(ui.calls.filter(c=>c==='start_radar').length,1);
  reject('已取消');await pending;await ui.timers.shift()();assert.equal(ui.el.power.disabled,false);assert.equal(ui.el.status.textContent,'已取消');
});
test('radar shows 3D distance and elevation only with fresh self coordinates',async()=>{
  const data=snapshot({player:{x:0,y:0,z:0},position_age_ms:0,frames:1,cubes:[{position:{x:300,y:0,z:400}}]});data.active=true;
  const ui=fixture(()=>data);await tick();assert.equal(ui.el.nearest.firstChild.textContent,'5.0');assert.equal(ui.el.elevation.firstChild.textContent,'+4.0');
  data.data.position_age_ms=5000;await ui.timers.shift()();assert.equal(ui.el.nearest.firstChild.textContent,'—');assert.equal(ui.el.cubes.children.length,0);
  data.data.position_age_ms=null;await ui.timers.shift()();assert.equal(ui.el.nearest.firstChild.textContent,'—');
});
test('appearance settings are bounded and closing never closes the launcher',async()=>{
  const ui=fixture(()=>snapshot(),{range:'evil',opacity:999,volume:-4,'cube-color':'javascript:bad'});await tick();
  assert.equal(ui.el.range.value,'150');assert.equal(ui.el.opacity.value,'40');assert.equal(ui.el.volume.value,'0');assert.equal(ui.el['cube-color'].value,'#e8bd75');
  await ui.el['settings-toggle'].onclick();assert.equal(ui.el.settings.hidden,true);assert.equal(ui.calls.at(-1),'open_radar_settings');
  ui.el.close.onclick();assert.equal(ui.closed(),1);assert.deepEqual(ui.calls,['get_settings','fit_radar_window','radar_snapshot','open_radar_settings']);
});
test('settings use a separate window without polling or starting capture',async()=>{
  const ui=fixture(()=>snapshot(),{},'radar-settings');await tick();
  assert.equal(ui.el.settings.hidden,false);assert.deepEqual(ui.calls,['get_settings']);assert.deepEqual(ui.timers,[]);
  ui.el['settings-close'].onclick();assert.equal(ui.closed(),1);
});
test('cross-window preferences are validated before they affect the overlay',async()=>{
  const ui=fixture(()=>snapshot());await tick();
  ui.listeners['atreia-radar-appearance']({payload:{range:'300',opacity:1,'cube-color':'bad'}});
  assert.equal(ui.el.range.value,'300');assert.equal(ui.el.opacity.value,'40');assert.equal(ui.el['cube-color'].value,'#e8bd75');
});
test('DPS and radar share material, opacity setting and shadow-free chrome',async()=>{
  const ui=fixture(command=>command==='get_settings'?{'dpsMeter.windowOpacity':'25'}:snapshot());await tick();
  assert.equal(ui.el.opacity.value,'25');
  ui.listeners['setting-changed']({payload:{key:'dpsMeter.windowOpacity',value:'65'}});
  assert.equal(ui.el.opacity.value,'65');
  for(const entry of ['index.html','radar.html'])assert.match(fs.readFileSync(path.join(__dirname,'..',entry),'utf8'),/overlay-material.css/);
  const css=fs.readFileSync(path.join(__dirname,'../src/overlay-material.css'),'utf8');
  assert.match(css,/--overlay-bg:9,13,24/);assert.match(css,/box-shadow:none/);assert.match(css,/--overlay-text:#ffffff/);
});
test('compact overlay uses a fixed small client area and a separate settings route',()=>{
  const native=fs.readFileSync(path.join(__dirname,'../src-tauri/src/atreia_radar.rs'),'utf8');
  const css=fs.readFileSync(path.join(__dirname,'../src/radar-compact.css'),'utf8');
  assert.match(native,/inner_size\(210\.,240\.\)\.resizable\(false\)/);
  assert.match(native,/pub async fn open_radar_settings/);assert.match(css,/width:160px;height:160px/);
  assert.match(native,/pub fn fit_radar_window/);assert.match(native,/set_min_size\(Option::<tauri::Size>::None\)/);
  assert.match(source,/invoke\('fit_radar_window',\{scale:window.devicePixelRatio\|\|1\}\)/);
  assert.match(css,/#cubes\{display:none\}/);
});
