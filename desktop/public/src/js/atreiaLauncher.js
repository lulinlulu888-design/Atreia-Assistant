// Atreia launcher: displaying the page does not invoke capture or localization.
(() => {
  const combat = document.getElementById("combat");
  const status = document.getElementById("status");
  combat.addEventListener("click", async () => {
    combat.disabled = true;
    status.textContent = "正在准备战斗统计…";
    try {
      await window.__TAURI__.core.invoke("open_combat");
      status.textContent = "战斗统计已开启";
    } catch (error) { status.textContent = String(error); }
    finally { combat.disabled = false; }
  });
  document.getElementById("localization").addEventListener("click", window.atreiaOpenLocalization);
})();
