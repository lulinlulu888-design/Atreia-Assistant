// Added by Atreia. DOM text is never interpreted as HTML or shell commands.
(() => {
  window.atreiaOpenLocalization = () => {
    if (document.querySelector(".atreiaDialog")) return;
    const dialog = document.createElement("dialog");
    dialog.className = "atreiaDialog";
    Object.assign(dialog.style, {background:"#142230",color:"#eaf1f6",border:"1px solid #365163",borderRadius:"12px",width:"min(440px,90vw)",padding:"20px",fontFamily:"Microsoft YaHei UI, sans-serif"});
    const title = document.createElement("h3"); title.textContent = "游戏汉化";
    const client = document.createElement("select");
    for (const [value,label] of [["steam","Steam / Global"],["purple","PURPLE（安装暂未开放）"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label; client.append(option);
    }
    const root = document.createElement("input"); root.placeholder = "游戏根目录（包含 Aion2 文件夹）";
    root.setAttribute("aria-label", "游戏目录"); root.style.cssText = "display:block;width:100%;margin:12px 0;padding:8px;box-sizing:border-box";
    const status = document.createElement("p"); status.style.fontSize = "12px";
    status.textContent = "请先退出游戏。安装前备份，支持还原；本页不会启动战斗统计。";
    const actions = document.createElement("div"); actions.style.cssText = "display:flex;gap:8px;flex-wrap:wrap";
    let busy = false;
    for (const [operation,label] of [["inspect","检测"],["install","安装 / 更新汉化"],["restore","还原"]]) {
      const button = document.createElement("button"); button.textContent = label;
      if (operation === "install") button.className = "primary";
      button.addEventListener("click", async () => {
        if (!root.value.trim()) { status.textContent = "请填写游戏目录。"; return; }
        busy = true; actions.querySelectorAll("button").forEach(b => b.disabled = true); close.disabled = true;
        status.textContent = "正在处理，请等待完成…";
        try {
          const result = await window.__TAURI__.core.invoke("localization_execute", {root:root.value.trim(),client:client.value,operation});
          status.textContent = result.message;
        } catch (error) { status.textContent = String(error); }
        finally {busy = false; actions.querySelectorAll("button").forEach(b => b.disabled = false); close.disabled = false;}
      }); actions.append(button);
    }
    const close = document.createElement("button"); close.textContent = "返回"; close.addEventListener("click", () => {if(!busy) dialog.close();});
    close.className = "ghost";
    actions.append(close); dialog.append(title,client,root,status,actions);
    dialog.addEventListener("cancel", event => {if(busy) event.preventDefault();});
    dialog.addEventListener("close", () => dialog.remove()); document.body.append(dialog); dialog.showModal();
  };
})();
