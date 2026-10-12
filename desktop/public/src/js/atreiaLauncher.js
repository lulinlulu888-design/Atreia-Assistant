// Atreia launcher: displaying the page does not invoke capture or localization.
(() => {
  const combat = document.getElementById("combat");
  const status = document.getElementById("status");
  const setStatus = message => { status.textContent = message; status.title = message; };
  combat.addEventListener("click", async () => {
    combat.disabled = true;
    setStatus("正在准备战斗统计…");
    try {
      await window.__TAURI__.core.invoke("open_combat");
      setStatus("战斗统计已开启");
    } catch (error) { setStatus(String(error)); }
    finally { combat.disabled = false; }
  });
  document.getElementById("localization").addEventListener("click", window.atreiaOpenLocalization);
  window.lucide?.createIcons();
})();
