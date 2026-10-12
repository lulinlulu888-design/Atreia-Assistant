// Startup only checks metadata; downloads/installations require an explicit action.
(() => {
  const check = document.getElementById('update-check');
  const install = document.getElementById('update-install');
  const status = document.getElementById('update-status');
  const setStatus = message => { status.textContent = message; status.title = message; };
  let busy = false;
  const invoke = (name) => window.__TAURI__.core.invoke(name);
  const checkUpdate = async () => {
    if (busy) return;
    busy = true; check.disabled = true; install.hidden = true;
    setStatus('正在检查助手更新…');
    try {
      const result = await invoke('atreia_check_update');
      setStatus(result.message);
      install.hidden = result.status !== 'available';
    } catch (error) {
      const detail = String(error).replace(/^Error:\s*/, '').replace(/^(?:更新检查失败：\s*)+/, '');
      setStatus(`更新检查失败：${detail}`);
    }
    finally { busy = false; check.disabled = false; }
  };
  check.addEventListener('click', checkUpdate);
  install.addEventListener('click', async () => {
    if (busy || install.hidden) return;
    busy = true; check.disabled = true; install.disabled = true;
    setStatus('等待更新确认…');
    try { await invoke('atreia_install_update'); setStatus('正在启动安装程序…'); }
    catch (error) { setStatus(String(error)); }
    finally { busy = false; check.disabled = false; install.disabled = false; }
  });
  window.__TAURI__.event?.listen('atreia-update-progress', ({payload}) => {
    if (busy && Number.isFinite(payload)) setStatus(`正在下载助手更新：${Math.max(0,Math.min(100,Math.floor(payload)))}%`);
  }).catch(() => {});
  setTimeout(checkUpdate, 1000);
})();
