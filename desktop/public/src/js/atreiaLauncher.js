// Atreia launcher: displaying the page does not invoke capture or localization.
(() => {
  const combat = document.getElementById("combat");
  const status = document.getElementById("status");
  const npcap = document.getElementById("npcap-download");
  const setStatus = (message, missingNpcap = false) => {
    status.textContent = message; status.title = message;
    npcap.hidden = !missingNpcap;
  };
  npcap.addEventListener("click", async () => {
    if (npcap.disabled || npcap.hidden) return;
    npcap.disabled = true;
    try {
      // Fixed official page only; never download a driver or start capture.
      await window.__TAURI__.core.invoke("open_url", {url: "https://npcap.com/#download"});
    } catch (error) {
      if (!npcap.hidden) setStatus(`无法打开 Npcap 官网，请手动访问 https://npcap.com/#download。${String(error)}`, true);
    } finally { npcap.disabled = false; }
  });
  combat.addEventListener("click", async () => {
    if (combat.disabled) return;
    combat.disabled = true;
    setStatus("正在准备战斗统计…");
    try {
      await window.__TAURI__.core.invoke("open_combat");
      setStatus("战斗统计已开启");
    } catch (error) {
      const message = String(error);
      setStatus(message, message.includes("未能加载 Npcap。"));
    }
    finally { combat.disabled = false; }
  });
  document.getElementById("localization").addEventListener("click", window.atreiaOpenLocalization);
  window.lucide?.createIcons();
})();
