const fs=require('node:fs'),vm=require('node:vm'),test=require('node:test'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../public/src/js/atreiaUpdate.js'),'utf8');
function fixture(invoke) {
 const controls=Object.fromEntries(['update-check','update-install','update-status'].map(k=>[k,{hidden:k==='update-install',disabled:false,listeners:{},addEventListener(k,f){this.listeners[k]=f;}}]));
 let startup,progress;
 vm.runInNewContext(source,{document:{getElementById:k=>controls[k]},window:{__TAURI__:{core:{invoke},event:{listen:async(_,f)=>{progress=f;}}}},setTimeout:f=>{startup=f;}});
 return {controls,start:()=>startup(),progress:p=>progress({payload:p})};
}
test('startup automatically checks but never downloads or starts capture',async()=>{
 const calls=[];const f=fixture(async name=>{calls.push(name);return {status:'available',message:'new version'};});
 assert.deepEqual(calls,[]);await f.start();assert.deepEqual(calls,['atreia_check_update']);assert.equal(f.controls['update-install'].hidden,false);
});
test('no release, latest, failure and retry remain actionable',async()=>{
 for(const status of ['no_release','up_to_date']){const f=fixture(async()=>({status,message:status}));await f.start();assert.equal(f.controls['update-install'].hidden,true);assert.equal(f.controls['update-check'].disabled,false);}
 const f=fixture(async()=>{throw Error('offline');});await f.start();assert.match(f.controls['update-status'].textContent,/offline/);assert.equal(f.controls['update-check'].disabled,false);
});
test('install is explicit, duplicate requests blocked, cancellation recovers',async()=>{
 const calls=[];let reject;const f=fixture(name=>{calls.push(name);if(name==='atreia_check_update')return Promise.resolve({status:'available',message:'new'});return new Promise((_,r)=>{reject=r;});});
 await f.start();const pending=f.controls['update-install'].listeners.click();await f.controls['update-install'].listeners.click();
 f.progress(42);assert.match(f.controls['update-status'].textContent,/42%/);assert.equal(f.controls['update-check'].disabled,true);
 reject(Error('cancelled'));await pending;assert.deepEqual(calls,['atreia_check_update','atreia_install_update']);assert.equal(f.controls['update-install'].disabled,false);assert.match(f.controls['update-status'].textContent,/cancelled/);
});
