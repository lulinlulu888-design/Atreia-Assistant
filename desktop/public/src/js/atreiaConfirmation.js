// The backend owns the pending request and rejects answers from other windows.
(() => {
  const title = document.getElementById('confirmation-title');
  const message = document.getElementById('confirmation-message');
  const details = document.getElementById('confirmation-details');
  const status = document.getElementById('confirmation-status');
  const cancel = document.getElementById('confirmation-cancel');
  const accept = document.getElementById('confirmation-accept');
  let request = null, busy = false;
  const respond = async accepted => {
    if (busy || (accepted && !request)) return;
    busy = true; cancel.disabled = true; accept.disabled = true;
    try { await window.__TAURI__.core.invoke(request ? 'confirmation_respond' : 'confirmation_cancel', request ? {id:request.id,accepted} : undefined); }
    catch (error) { status.textContent = `确认未提交：${String(error)}`; busy = false; cancel.disabled = false; accept.disabled = !request; }
  };
  cancel.addEventListener('click', () => respond(false));
  accept.addEventListener('click', () => respond(true));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); respond(false); } });
  window.__TAURI__.core.invoke('confirmation_request').then(result => {
    if (!result || !Number.isSafeInteger(result.id) || result.id <= 0 || typeof result.title !== 'string' || typeof result.message !== 'string' || typeof result.confirm_label !== 'string' || !Array.isArray(result.details) || result.details.some(row=>!Array.isArray(row)||row.length!==2||row.some(value=>typeof value!=='string'))) throw new Error('无效的操作确认');
    request = result; title.textContent = result.title; message.textContent = result.message;
    accept.textContent = result.confirm_label;
    for (const [label, value] of result.details) { const dt=document.createElement('dt'), dd=document.createElement('dd'); dt.textContent=label; dd.textContent=value; details.append(dt,dd); }
    accept.disabled = busy; if (!busy) cancel.focus();
  }).catch(error => { status.textContent = `无法读取确认信息，未执行操作：${String(error)}`; accept.disabled = true; });
})();
