const repo = "lulinlulu888-design/Atreia-Assistant";
const button = document.querySelector("#download-button");
const label = document.querySelector("#download-label");
const status = document.querySelector("#release-status");
const footerButton = document.querySelector("#footer-download");
const downloadCount = document.querySelector("#download-count");
const installerName = /^Atreia-Assistant_\d+\.\d+\.\d+_x64\.msi$/i;
const cachedVersion = button.dataset?.version;
const cachedInstaller = /^\d+\.\d+\.\d+$/.test(cachedVersion || "") ? {
  version: cachedVersion,
  size: Number(button.dataset.size),
  url: `https://github.com/${repo}/releases/download/v${cachedVersion}/Atreia-Assistant_${cachedVersion}_x64.msi`
} : null;

function showInstaller(installer) {
  label.textContent = `下载 Windows ${installer.version || "正式版"}`;
  status.textContent = `Windows x64 · ${(installer.size / 1024 / 1024).toFixed(1)} MB · 整合安装包`;
  button.href = installer.url;
  button.classList.remove("is-disabled");
  button.removeAttribute("aria-disabled");
  if (footerButton) {
    footerButton.href = installer.url;
    footerButton.querySelector("span").textContent = label.textContent;
  }
}

function unavailable(message) {
  label.textContent = "正式版尚未发布";
  status.textContent = message;
  button.classList.add("is-disabled");
  button.setAttribute("aria-disabled", "true");
  button.href = `https://github.com/${repo}/releases`;
}

fetch(`https://api.github.com/repos/${repo}/releases/latest`, {
  headers: { Accept: "application/vnd.github+json" }
})
  .then((response) => {
    if (!response.ok) throw new Error(String(response.status));
    return response.json();
  })
  .then((release) => {
    const assets = Array.isArray(release.assets) ? release.assets : [];
    const installer = assets.find((asset) => installerName.test(asset.name));
    if (!installer || !installer.browser_download_url) {
      if (cachedInstaller) { showInstaller(cachedInstaller); return; }
      unavailable("最新 Release 没有符合命名规则的 Windows x64 MSI，请前往 GitHub 查看详情。");
      return;
    }
    const version = String(release.tag_name || "").replace(/^v/i, "");
    showInstaller({version, size: installer.size, url: installer.browser_download_url});
  })
  .catch((error) => {
    if (cachedInstaller) { showInstaller(cachedInstaller); return; }
    if (error.message === "404") {
      unavailable("当前没有正式安装包。首个 Release 发布后，本页会自动显示下载按钮。");
      return;
    }
    label.textContent = "前往 GitHub 下载";
    status.textContent = "暂时无法读取版本信息，请前往 GitHub Releases 查看安装包。";
    button.href = `https://github.com/${repo}/releases`;
    button.classList.remove("is-disabled");
    button.removeAttribute("aria-disabled");
  });

async function loadDownloadCount() {
  if (!downloadCount) return;
  downloadCount.hidden = false;
  downloadCount.textContent = "下载统计加载中…";
  try {
    let total = 0;
    // Publish the total only after every page succeeds, never a partial count.
    const signal = AbortSignal.timeout(10000);
    for (let page = 1; page <= 100; page += 1) {
      const response = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=100&page=${page}`, {
        headers: { Accept: "application/vnd.github+json" }, signal
      });
      if (!response.ok) throw new Error(String(response.status));
      const releases = await response.json();
      if (!Array.isArray(releases)) throw new Error("Invalid releases");
      for (const release of releases) {
        if (release.draft || release.prerelease) continue;
        if (!Array.isArray(release.assets)) throw new Error("Invalid release assets");
        for (const asset of release.assets) {
          if (!installerName.test(asset.name)) continue;
          if (!Number.isSafeInteger(asset.download_count) || asset.download_count < 0) {
            throw new Error("Invalid download count");
          }
          total += asset.download_count;
          if (!Number.isSafeInteger(total)) throw new Error("Invalid total");
        }
      }
      if (releases.length < 100) {
        downloadCount.textContent = `累计下载 ${total.toLocaleString("zh-CN")} 次`;
        return;
      }
    }
    throw new Error("Too many release pages");
  } catch {
    downloadCount.textContent = "下载统计暂不可用";
  }
}

loadDownloadCount();

button.addEventListener("click", (event) => {
  if (button.getAttribute("aria-disabled") === "true") event.preventDefault();
});

window.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();
});
