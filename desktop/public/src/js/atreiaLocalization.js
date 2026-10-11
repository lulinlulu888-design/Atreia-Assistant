// Discovery and folder selection are read-only; installation stays explicit.
(() => {
  window.atreiaOpenLocalization = () => {
    if (document.querySelector('.atreiaDialog')) return;
    const dialog = document.createElement('dialog');
    dialog.className = 'atreiaDialog';
    Object.assign(dialog.style, {background:'#142230',color:'#eaf1f6',border:'1px solid #365163',borderRadius:'8px',width:'min(440px,90vw)',padding:'20px',fontFamily:'Microsoft YaHei UI, sans-serif'});
    const title = document.createElement('h3'); title.textContent = '游戏汉化';
    const client = document.createElement('select');
    client.setAttribute('aria-label', '游戏客户端');
    for (const [value,label] of [['steam','Steam / Global'],['purple','PURPLE']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = label; client.append(option);
    }
    const pathRow = document.createElement('div'); pathRow.className = 'localization-path';
    const root = document.createElement('input'); root.placeholder = '点击检测自动查找，或选择游戏目录';
    root.setAttribute('aria-label', '游戏目录');
    const browse = document.createElement('button'); browse.className = 'browse-path';
    browse.setAttribute('aria-label', '选择游戏目录'); browse.title = '选择游戏目录';
    const folderIcon = document.createElement('i'); folderIcon.setAttribute('data-lucide', 'folder-open'); browse.append(folderIcon);
    pathRow.append(root, browse);
    const status = document.createElement('p'); status.style.fontSize = '12px';
    status.setAttribute('role', 'status');
    const candidates = document.createElement('select'); candidates.hidden = true;
    candidates.setAttribute('aria-label', '检测到的游戏目录'); candidates.className = 'localization-candidates';
    const actions = document.createElement('div'); actions.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap';
    let busy = false;
    const setBusy = value => {
      busy = value; client.disabled = value; root.disabled = value; browse.disabled = value;
      candidates.disabled = value; close.disabled = value;
      actions.querySelectorAll('button').forEach(button => { button.disabled = value; });
    };
    for (const [operation,label] of [['inspect','检测'],['install','安装 / 更新汉化'],['restore','还原']]) {
      const button = document.createElement('button'); button.textContent = label;
      if (operation === 'install') button.className = 'primary';
      button.addEventListener('click', async () => {
        if (busy) return;
        if (!root.value.trim() && operation !== 'inspect') { status.textContent = '请先点击检测，或选择游戏目录。'; return; }
        setBusy(true);
        try {
          if (!root.value.trim()) {
            status.textContent = '正在自动查找游戏目录…';
            const found = await window.__TAURI__.core.invoke('discover_localization_roots', {client:client.value});
            if (!Array.isArray(found) || found.some(path => typeof path !== 'string')) throw new Error('目录检测返回无效结果');
            if (!found.length) { status.textContent = '未找到游戏目录，请点击文件夹按钮手动选择。'; return; }
            if (found.length > 1) {
              candidates.replaceChildren();
              const placeholder = document.createElement('option'); placeholder.value = ''; placeholder.textContent = '请选择要检测的游戏目录'; candidates.append(placeholder);
              for (const path of found) { const option = document.createElement('option'); option.value = path; option.textContent = path; candidates.append(option); }
              candidates.hidden = false;
              status.textContent = `找到 ${found.length} 个目录，请选择后再点击检测。`;
              return;
            }
            root.value = found[0]; root.title = found[0]; candidates.hidden = true;
          }
          status.textContent = operation === 'inspect' ? '正在核对游戏语言资源，请稍候…' : '正在处理，请等待完成…';
          const command = "localization_execute";
          const result = await window.__TAURI__.core.invoke(command, {root:root.value.trim(),client:client.value,operation});
          status.textContent = result.message;
        } catch (error) { status.textContent = String(error); }
        finally { setBusy(false); }
      }); actions.append(button);
    }
    const refreshClient = () => {
      status.textContent = client.value === 'purple'
        ? '请先退出游戏。可自动查找常见安装位置，也可手动选择；安装后文字语言设为 English。'
        : '点击检测自动查找 Steam 游戏目录。请先退出游戏；安装前备份，支持还原。';
    };
    client.addEventListener('change', () => { root.value = ''; root.title = ''; candidates.hidden = true; refreshClient(); });
    root.addEventListener('input', () => { root.title = root.value; candidates.hidden = true; status.textContent = '目录已更改，请重新检测。'; });
    candidates.addEventListener('change', () => {
      if (candidates.value) { root.value = candidates.value; root.title = candidates.value; candidates.hidden = true; status.textContent = '已选择目录，点击检测核对当前游戏资源。'; }
    });
    browse.addEventListener('click', async () => {
      if (busy) return;
      setBusy(true);
      try {
        const selected = await window.__TAURI__.core.invoke('browse_localization_root', {start:root.value.trim() || null});
        if (selected) { root.value = selected; root.title = selected; candidates.hidden = true; status.textContent = '已选择目录，点击检测核对当前游戏资源。'; }
      } catch (error) { status.textContent = String(error); }
      finally { setBusy(false); }
    });
    const close = document.createElement('button'); close.textContent = '返回'; close.className = 'ghost';
    close.addEventListener('click', () => { if (!busy) dialog.close(); }); actions.append(close);
    refreshClient(); dialog.append(title,client,pathRow,status,candidates,actions);
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    dialog.addEventListener('close', () => dialog.remove());
    document.body.append(dialog); dialog.showModal(); window.lucide?.createIcons();
  };
})();
