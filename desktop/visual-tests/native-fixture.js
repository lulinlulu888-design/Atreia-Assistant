// Loaded only by Vite's /__visual routes, never by the packaged desktop app.
(() => {
  const query = new URLSearchParams(location.search);
  const state = query.get('state') || 'latest';
  const sampleDps = {targetName:'界面示例 · 训练目标',targetMode:'bossTargets',targetId:990,battleTime:120000,localPlayerId:1,dungeonId:0,targetMaxHp:10000000,targetTotalDamage:3840000,targetCurrentHp:6160000,map:{
    1:{nickname:'示例 · 剑星',job:'검성',dps:24000,amount:2880000,damageContribution:75,combatPower:3800},
    2:{nickname:'示例 · 魔道星',job:'마도성',dps:8000,amount:960000,damageContribution:25,combatPower:3600},
  }};
  window.__A2_VIEW__ = query.get('view') || 'main';
  const messages = {
    latest: {status:'up_to_date',message:'已是最新版本 · 2.0.52'},
    available: {status:'available',message:'发现新版本 2.0.53，可下载并更新。'},
    error: null,
  };
  window.__TAURI__ = {
    core: {invoke: async (command, args) => {
      if (command === 'atreia_check_update') {
        if (state === 'error') throw new Error('连接暂时不可用，请检查网络后重试。https://api.github.com/repos/example/example/releases/latest');
        return messages[state] || messages.latest;
      }
      if (command === 'get_app_version') return '2.0.52';
      if (command === 'get_settings') return {'dpsMeter.language':'zh-Hans','dpsMeter.windowOpacity':'95','dpsMeter.autoHideMeter':'false'};
      if (command === 'get_dps_snapshot') return sampleDps;
      if (command === 'get_fight_history') return [{id:'visual-demo',bossName:'界面示例 · 训练目标',targetId:990,startTimeMs:1791784800000,durationMs:120000,totalDamage:3840000,jobs:['검성','마도성'],memberJobs:['검성','마도성'],jobIds:[1,5],isTrain:false,isLive:false,appVersion:'2.0.52',mobCode:0,dungeonId:0}];
      if (command === 'discover_localization_roots') return ['D:/SteamLibrary/steamapps/common/AION2'];
      if (command === 'localization_execute') return {ok:true,message:`仅界面测试：${args.client}，156480 个键；编码回读及缺译检查通过。未修改游戏文件。`};
      if (command === 'get_available_devices' || command === 'list_monitors') return [];
      if (command === 'get_capture_status') return {running:false,status:'idle'};
      if (command === 'open_combat' || command === 'atreia_install_update') throw new Error('这是界面预览，不启动统计、不下载、不修改游戏文件。');
      return null;
    }},
    event: {listen: async (name, callback) => { if (name === 'dps-update') setTimeout(()=>callback({payload:sampleDps}),200); return () => {}; }},
    opener: {open: async () => {}, openUrl: async () => {}},
    window: {getCurrentWindow: () => ({label:window.__A2_VIEW__})},
  };
})();
