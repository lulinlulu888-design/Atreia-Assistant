const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/src/js/atreiaConfirmation.js'),'utf8');
const prompt={id:1,title:'确认安装',message:'<风险说明>',confirm_label:'确认安装',details:[['客户端','PURPLE'],['目标','D:/Game']]};
function setup(invoke){
  const elements={};const events={};
  const make=()=>({disabled:true,textContent:'',children:[],addEventListener(n,f){this[n]=f;},append(...x){this.children.push(...x);},focus(){this.focused=true;}});
  vm.runInNewContext(source,{window:{__TAURI__:{core:{invoke}}},document:{getElementById:id=>elements[id]??(elements[id]=make()),createElement:make,addEventListener:(n,f)=>events[n]=f}});
  return {elements,events};
}
const flush=()=>new Promise(r=>setImmediate(r));
test('confirmation renders literal text and defaults focus to cancellation',async()=>{
  const ui=setup(async()=>prompt);await flush();
  assert.equal(ui.elements['confirmation-message'].textContent,'<风险说明>');
  assert.equal(ui.elements['confirmation-cancel'].focused,true);
  assert.equal(ui.elements['confirmation-accept'].disabled,false);
  assert.equal(ui.elements['confirmation-details'].children[1].textContent,'PURPLE');
});
test('approval is explicit, identified and duplicate clicks are blocked',async()=>{
  const calls=[];const ui=setup(async(c,a)=>{calls.push([c,a]);return prompt;});await flush();
  ui.elements['confirmation-accept'].click();ui.elements['confirmation-accept'].click();await flush();
  assert.equal(calls.length,2);assert.equal(calls[1][0],'confirmation_respond');
  assert.equal(calls[1][1].id,1);assert.equal(calls[1][1].accepted,true);
});
test('Escape before loading cancels without inventing an approval id',async()=>{
  const calls=[];const ui=setup((c,a)=>{calls.push([c,a]);return c==='confirmation_request'?new Promise(()=>{}):Promise.resolve();});
  let prevented=false;ui.events.keydown({key:'Escape',preventDefault(){prevented=true;}});await flush();
  assert.equal(prevented,true);assert.equal(calls[1][0],'confirmation_cancel');assert.equal(calls[1][1],undefined);
});
test('invalid request cannot approve, and cancellation remains available',async()=>{
  const calls=[];const ui=setup(async(c,a)=>{calls.push([c,a]);return {...prompt,id:0};});await flush();
  assert.equal(ui.elements['confirmation-accept'].disabled,true);
  ui.elements['confirmation-accept'].click();assert.equal(calls.length,1);
  ui.elements['confirmation-cancel'].click();await flush();assert.equal(calls[1][0],'confirmation_cancel');
});
test('failed submission restores cancellation and shows the error',async()=>{
  const ui=setup(async c=>{if(c==='confirmation_request')return prompt;throw Error('closed');});await flush();
  ui.elements['confirmation-cancel'].click();await flush();
  assert.equal(ui.elements['confirmation-cancel'].disabled,false);assert.match(ui.elements['confirmation-status'].textContent,/closed/);
});
