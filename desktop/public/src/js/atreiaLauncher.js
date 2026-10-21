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
  document.getElementById("localization").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    if (button.disabled) return;
    button.disabled = true;
    try { await window.__TAURI__.core.invoke("open_localization"); setStatus("游戏汉化窗口已打开。"); }
    catch (error) { setStatus(String(error)); }
    finally { button.disabled = false; }
  });
  document.getElementById("radar-open")?.addEventListener("click", async (event) => {
    const button=event.currentTarget;
    if(button.disabled)return;
    button.disabled=true;
    try { await window.__TAURI__.core.invoke("open_radar");setStatus("宝箱雷达已打开，尚未开启采集。"); }
    catch(error) { setStatus(String(error)); }
    finally { button.disabled=false; }
  });
  window.lucide?.createIcons();
})();
