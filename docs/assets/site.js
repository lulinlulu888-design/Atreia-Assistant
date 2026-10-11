const repo = "lulinlulu888-design/Atreia-Assistant";
const button = document.querySelector("#download-button");
const label = document.querySelector("#download-label");
const status = document.querySelector("#release-status");

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
    const installer = assets.find((asset) => /^Atreia-Assistant_\d+\.\d+\.\d+_x64\.msi$/i.test(asset.name));
    if (!installer || !installer.browser_download_url) {
      unavailable("最新 Release 没有符合命名规则的 Windows x64 MSI，请前往 GitHub 查看详情。");
      return;
    }
    const version = String(release.tag_name || "").replace(/^v/i, "");
    label.textContent = `下载 Windows ${version || "正式版"}`;
    status.textContent = `${installer.name} · ${(installer.size / 1024 / 1024).toFixed(1)} MB · 来自 GitHub Releases`;
    button.href = installer.browser_download_url;
    button.classList.remove("is-disabled");
    button.removeAttribute("aria-disabled");
  })
  .catch((error) => {
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

button.addEventListener("click", (event) => {
  if (button.getAttribute("aria-disabled") === "true") event.preventDefault();
});

window.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();
});
