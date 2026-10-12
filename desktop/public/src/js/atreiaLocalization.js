// Discovery and folder selection are read-only; installation stays explicit.
(() => {
  let draft = {client:'steam',root:''};
  window.atreiaOpenLocalization = event => {
    if (document.querySelector('.atreiaDialog')) return;
    const opener = event?.currentTarget || document.activeElement;
    const dialog = document.createElement('dialog');
    dialog.className = 'atreiaDialog';
    dialog.setAttribute('aria-label', '游戏汉化');
    const title = document.createElement('h3'); title.textContent = '游戏汉化';
    const client = document.createElement('select');
    client.setAttribute('aria-label', '游戏客户端');
    for (const [value,label] of [['steam','Steam / Global'],['purple','PURPLE']]) {
      const option = document.createElement('option'); option.value = value; option.textContent = label; client.append(option);
    }
    client.value = draft.client;
    const pathRow = document.createElement('div'); pathRow.className = 'localization-path';
    const root = document.createElement('input'); root.placeholder = '点击检测自动查找，或选择游戏目录';
    root.setAttribute('aria-label', '游戏目录');
    root.value = draft.root; root.title = draft.root;
    const browse = document.createElement('button'); browse.className = 'browse-path';
    browse.setAttribute('aria-label', '选择游戏目录'); browse.title = '选择游戏目录';
    const folderIcon = document.createElement('i'); folderIcon.setAttribute('data-lucide', 'folder-open'); browse.append(folderIcon);
    pathRow.append(root, browse);
    const status = document.createElement('p'); status.className = 'localization-status';
    status.setAttribute('role', 'status');
    const candidates = document.createElement('select'); candidates.hidden = true;
    candidates.setAttribute('aria-label', '检测到的游戏目录'); candidates.className = 'localization-candidates';
    const actions = document.createElement('div'); actions.className = 'localization-actions';
    let busy = false, verifiedKey = null, activeOperation = null;
    const selectionKey = () => `${client.value}\n${root.value.trim()}`;
    const setBusy = value => {
      busy = value; client.disabled = value; root.disabled = value; browse.disabled = value;
      candidates.disabled = value; close.disabled = value;
      dialog.setAttribute('aria-busy', String(value));
      close.title = value ? '请等待操作完成；确认窗口可选择取消。' : '返回主页，保留客户端和目录';
      actions.querySelectorAll('button').forEach(button => { button.disabled = value || (button === installButton && verifiedKey !== selectionKey()); });
    };
    let installButton;
    const stageListener = window.__TAURI__.event?.listen('atreia-localization-stage', ({payload}) => {
      if (busy && payload?.stage === 'running' && payload.client === client.value && payload.operation === activeOperation) {
        status.textContent = payload.operation === 'restore' ? '正在还原，请等待事务完成…' : '正在安装汉化，请等待事务完成…';
      }
    }).catch(() => null);
    for (const [operation,label] of [['inspect','检测'],['install','安装 / 更新汉化'],['restore','还原']]) {
      const button = document.createElement('button'); button.textContent = label;
      if (operation === 'install') { button.className = 'primary'; installButton = button; button.disabled = true; button.title = '先检测当前目录，检查通过后才能安装'; }
      button.addEventListener('click', async () => {
        if (busy) return;
        if (!root.value.trim() && operation !== 'inspect') { status.textContent = '请先点击检测，或选择游戏目录。'; return; }
        if (operation === 'install' && verifiedKey !== selectionKey()) { status.textContent = '请先检测当前目录，检查通过后再安装汉化。'; return; }
        activeOperation = operation;
        setBusy(true);
        try {
          if (operation === 'inspect') verifiedKey = null;
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
          status.textContent = operation === 'inspect' ? '正在核对游戏语言资源，请稍候…' : '等待操作确认；取消不会修改游戏文件。';
          await stageListener;
          const command = "localization_execute";
          const result = await window.__TAURI__.core.invoke(command, {root:root.value.trim(),client:client.value,operation});
          if (!result || typeof result.ok !== 'boolean' || typeof result.message !== 'string') throw new Error('操作返回了无效结果，请重新检测。');
          if (operation === 'inspect' && result.ok) verifiedKey = selectionKey();
          if (operation !== 'inspect' && result.ok) verifiedKey = null;
          status.textContent = result.message;
          status.setAttribute('data-state', result.cancelled ? 'neutral' : result.ok ? 'success' : 'error');
        } catch (error) { verifiedKey = null; status.setAttribute('data-state','error'); status.textContent = String(error); }
        finally { activeOperation = null; setBusy(false); }
      }); actions.append(button);
    }
    const refreshClient = () => {
      status.textContent = client.value === 'purple'
        ? '请先退出游戏。可自动查找常见安装位置，也可手动选择；安装后文字语言设为 English。'
        : '点击检测自动查找 Steam 游戏目录。请先退出游戏；安装前备份，支持还原。';
    };
    client.addEventListener('change', () => { if (busy) return; verifiedKey = null; root.value = ''; root.title = ''; candidates.hidden = true; refreshClient(); setBusy(false); });
    root.addEventListener('input', () => { if (busy) return; verifiedKey = null; root.title = root.value; candidates.hidden = true; status.textContent = '目录已更改，请重新检测。'; setBusy(false); });
    candidates.addEventListener('change', () => {
      if (!busy && candidates.value) { verifiedKey = null; root.value = candidates.value; root.title = candidates.value; candidates.hidden = true; status.textContent = '已选择目录，点击检测核对当前游戏资源。'; setBusy(false); }
    });
    browse.addEventListener('click', async () => {
      if (busy) return;
      setBusy(true);
      try {
        const selected = await window.__TAURI__.core.invoke('browse_localization_root', {start:root.value.trim() || null});
        if (selected) { verifiedKey = null; root.value = selected; root.title = selected; candidates.hidden = true; status.textContent = '已选择目录，点击检测核对当前游戏资源。'; }
      } catch (error) { status.textContent = String(error); }
      finally { setBusy(false); }
    });
    const close = document.createElement('button'); close.textContent = '返回主页'; close.className = 'ghost';
    close.addEventListener('click', () => { if (!busy) dialog.close(); }); actions.append(close);
    refreshClient(); if (root.value) status.textContent = '已保留上次选择的目录，请重新检测当前游戏资源。';
    dialog.append(title,client,pathRow,status,candidates,actions); setBusy(false);
    dialog.addEventListener('cancel', event => { if (busy) { event.preventDefault(); status.textContent = '操作尚未完成，请等待；确认窗口可选择取消。'; } });
    dialog.addEventListener('close', () => {
      draft = {client:client.value,root:root.value.trim()};
      stageListener?.then(unlisten=>unlisten?.());
      dialog.remove(); opener?.focus?.();
    });
    document.body.append(dialog); dialog.showModal(); window.lucide?.createIcons();
  };
})();
