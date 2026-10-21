(() => {
  const $=id=>document.getElementById(id), invoke=(cmd,args)=>window.__TAURI__.core.invoke(cmd,args);
  const canvas=$('radar'),ctx=canvas.getContext('2d');
  const settingsMode=window.__TAURI__.window.getCurrentWindow().label==='radar-settings';
  if(settingsMode){document.body.classList.add('settings-window');$('settings').hidden=false;}
  let state=null,busy=false,discoveries=null,audio=null,lastError='';
  let opacityRevision=0;
  const controls=['range','opacity','player-color','cube-color','sound','volume'];
  function applyAppearance(saved) {
    for(const id of controls) {
      const el=$(id),v=saved[id];
      if(id==='opacity')continue;
      if(el.type==='checkbox') el.checked=v===true;
      else if(el.type==='color' && /^#[a-f0-9]{6}$/i.test(v)) el.value=v;
      else if(id==='range' && ['50','150','300'].includes(String(v))) el.value=String(v);
      else if(el.type==='range' && Number.isFinite(Number(v))) el.value=String(Math.max(Number(el.min),Math.min(Number(el.max),Number(v))));
    }
  }
  try { applyAppearance(JSON.parse(localStorage.getItem('atreia.radar.appearance')||'{}')); } catch {}
  function save(broadcast=false) {
    const settings=Object.fromEntries(controls.map(id=>[id,$(id).type==='checkbox'?$(id).checked:$(id).value]));
    try { localStorage.setItem('atreia.radar.appearance',JSON.stringify(settings)); } catch {}
    document.querySelector('.radar-shell').style.setProperty('--window-opacity',Number($('opacity').value)/100);
    $('opacity-value').textContent=`${$('opacity').value}%`; $('volume-value').textContent=`${$('volume').value}%`;
    $('range-label').textContent=`${$('range').value} m`; render();
    if(broadcast)window.__TAURI__.event?.emit('atreia-radar-appearance',settings).catch(()=>{});
  }
  function ping() {
    try {
      audio||=new AudioContext(); audio.resume();
      const oscillator=audio.createOscillator(),gain=audio.createGain(),at=audio.currentTime;
      oscillator.frequency.setValueAtTime(1050,at); oscillator.frequency.exponentialRampToValueAtTime(700,at+.18);
      gain.gain.setValueAtTime(Math.max(.0001,Number($('volume').value)/100*.12),at);
      gain.gain.exponentialRampToValueAtTime(.0001,at+.24);
      oscillator.connect(gain);gain.connect(audio.destination);oscillator.start(at);oscillator.stop(at+.25);
    } catch {}
  }
  const settings=open=>{ $('settings').hidden=!open;$('settings-toggle').setAttribute('aria-expanded',String(open));if(open)$('range').focus();else $('settings-toggle').focus(); };
  $('settings-toggle').onclick=async()=>{try{await invoke('open_radar_settings');}catch(error){$('status').textContent=String(error);}};
  $('settings-close').onclick=()=>settingsMode?window.__TAURI__.window.getCurrentWindow().close():settings(false);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&settingsMode)window.__TAURI__.window.getCurrentWindow().close();});
  controls.forEach(id=>$(id).addEventListener('input',()=>{
    if(id==='opacity'){
      opacityRevision++;
      invoke('update_settings',{key:'dpsMeter.windowOpacity',value:$('opacity').value}).catch(()=>{});
    }
    save(true);
  }));$('sound-preview').onclick=ping;
  function sharedSetting(key,value){
    if(key==='dpsMeter.windowOpacity'&&String(value).trim()!==''&&Number.isFinite(Number(value))){
      opacityRevision++;$('opacity').value=String(Math.max(0,Math.min(100,Math.round(Number(value)))));save(false);
    }
    if(key==='dpsMeter.betaUi')document.body.classList.toggle('legacyUi',value==='false');
  }
  window.__TAURI__.event?.listen('setting-changed',({payload})=>{if(payload)sharedSetting(payload.key,payload.value);}).catch(()=>{});
  const initialOpacityRevision=opacityRevision;
  invoke('get_settings').then(values=>{
    if(!values||typeof values!=='object')return;
    if(initialOpacityRevision===opacityRevision)sharedSetting('dpsMeter.windowOpacity',values['dpsMeter.windowOpacity']??40);
    sharedSetting('dpsMeter.betaUi',values['dpsMeter.betaUi']);
  }).catch(()=>{});
  window.__TAURI__.event?.listen('atreia-radar-appearance',({payload})=>{
    if(!payload||typeof payload!=='object')return;
    applyAppearance(payload);save(false);
  }).catch(()=>{});
  $('drag').onpointerdown=e=>{ if(e.button===0&&!e.target.closest('button'))window.__TAURI__.window.getCurrentWindow().startDragging(); };
  $('close').onclick=()=>window.__TAURI__.window.getCurrentWindow().close();
  $('power').onclick=async()=>{
    if(busy)return;busy=true;lastError='';$('power').disabled=true;
    try {
      if(state?.active) await invoke('stop_radar');
      else { $('status').textContent='等待开启确认…';await invoke('start_radar'); }
      await refresh();
    } catch(error) { lastError=String(error);$('status').textContent=lastError; }
    finally {busy=false;$('power').disabled=false;}
  };
  function render() {
    const data=state?.data,range=Number($('range').value),fresh=data?.player&&Number.isFinite(data.position_age_ms)&&data.position_age_ms>=0&&data.position_age_ms<5000;
    const cubes=(fresh?data.cubes:[]).map(c=>{
      const dx=(c.position.x-data.player.x)/100,dy=(c.position.y-data.player.y)/100,dz=(c.position.z-data.player.z)/100;
      return {...c,dx,dy,dz,distance:Math.hypot(dx,dy,dz)};
    }).sort((a,b)=>a.distance-b.distance);
    const visible=cubes.filter(c=>c.distance<=range),size=660,center=330,radius=278;
    ctx.clearRect(0,0,size,size);ctx.lineWidth=1.5;ctx.strokeStyle='#ffffff19';
    for(const r of [radius/2,radius]){ctx.beginPath();ctx.arc(center,center,r,0,Math.PI*2);ctx.stroke();}
    ctx.beginPath();ctx.moveTo(center,center-radius);ctx.lineTo(center,center+radius);ctx.moveTo(center-radius,center);ctx.lineTo(center+radius,center);ctx.stroke();
    if(visible[0]) {const c=visible[0];ctx.strokeStyle=$('cube-color').value+'66';ctx.beginPath();ctx.moveTo(center,center);ctx.lineTo(center+c.dx/range*radius,center-c.dy/range*radius);ctx.stroke();}
    for(const c of visible){const x=center+c.dx/range*radius,y=center-c.dy/range*radius;ctx.fillStyle=$('cube-color').value;ctx.beginPath();ctx.moveTo(x,y-8);ctx.lineTo(x+8,y);ctx.lineTo(x,y+8);ctx.lineTo(x-8,y);ctx.closePath();ctx.fill();}
    ctx.fillStyle=fresh?$('player-color').value:'#6f8590';ctx.beginPath();ctx.arc(center,center,6,0,Math.PI*2);ctx.fill();
    $('nearest').replaceChildren(document.createTextNode(visible[0]?visible[0].distance.toFixed(1):'—'));const unit=document.createElement('small');unit.textContent=' m';$('nearest').append(unit);
    $('elevation').replaceChildren(document.createTextNode(visible[0]?`${visible[0].dz>=0?'+':''}${visible[0].dz.toFixed(1)}`:'—'));$('elevation').append(unit.cloneNode(true));
    $('visible').firstChild.textContent=String(visible.length);$('count').textContent=String(data?.cubes.length||0);
    $('cubes').replaceChildren(...visible.slice(0,20).map((c,i)=>{const li=document.createElement('li');li.textContent=`隐藏宝箱 ${i+1}`;const detail=document.createElement('span');detail.textContent=`${c.distance.toFixed(1)} m · ${c.dz>=0?'↑':'↓'} ${Math.abs(c.dz).toFixed(1)} m`;li.append(detail);return li;}));
  }
  async function refresh() {
    state=await invoke('radar_snapshot');const data=state.data;
    $('power').setAttribute('aria-pressed',String(state.active));const action=state.active?'暂停雷达':'开启雷达';$('power').title=action;$('power').setAttribute('aria-label',action);
    if(discoveries!==null && data.discoveries>discoveries && $('sound').checked)ping();discoveries=data.discoveries;
    if(!busy)$('status').textContent=lastError||(!state.active?'未开启':!data.frames?'等待游戏连接 · 当前识别端口 13320 / 13328':!data.player?'等待角色定位 · 请切换地图后跳跃或滑翔':data.position_age_ms>=5000?'坐标已过期 · 请跳跃或滑翔刷新定位':data.cubes.length?'已定位 · 正北朝上':'已定位 · 暂未发现隐藏宝箱');
    $('status').title=$('status').textContent;
    render();
  }
  async function poll(){try{await refresh();}catch(error){state=null;render();$('status').textContent=`状态读取失败：${String(error)}`;}setTimeout(poll,300);}
  window.lucide?.createIcons();save();if(!settingsMode){
    invoke('fit_radar_window',{scale:window.devicePixelRatio||1}).catch(()=>{lastError='请重启开发版以应用紧凑窗口';});
    poll();
  }
})();
