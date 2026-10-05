(() => {
  const CDN_MANIFEST = "https://a2tools.app/latest-v2.json";
  const START_DELAY = 800,
    RETRY = 500,
    LIMIT = 5;

  const parseVersion = (v) => {
    const cleaned = String(v || "").trim().replace(/^v/i, "");
    const [base, prerelease] = cleaned.split("-", 2);
    const [a = 0, b = 0, c = 0] = String(base || "")
      .split(".")
      .map(Number);
    return {
      base,
      prerelease: Boolean(prerelease),
      value: a * 1e6 + b * 1e3 + c,
    };
  };

  let once = false;

  const start = () =>
    setTimeout(async () => {
      try {
        if (once) return;
        once = true;

        // Wait for the bridge AND for the async version fetch to complete
        for (
          let i = 0;
          i < LIMIT && !(
            window.dpsData?.getVersion &&
            window.javaBridge?.openBrowser &&
            String(window.dpsData.getVersion() || "").trim()
          );
          i++
        ) {
          await new Promise((r) => setTimeout(r, RETRY));
        }
        if (!(window.dpsData?.getVersion && window.javaBridge?.openBrowser)) {
          return;
        }

        const rawCurrent = String(window.dpsData.getVersion() || "").trim();
        const current = rawCurrent.startsWith("v") ? rawCurrent : "v" + rawCurrent;
        console.log("[A2Tools] Update check: current =", current);

        let result;
        try {
          const raw = await window.__TAURI__.core.invoke("fetch_url", { url: CDN_MANIFEST });
          const m = JSON.parse(raw);
          console.log("[A2Tools] Update manifest:", JSON.stringify(m));
          const v = m.version?.startsWith("v") ? m.version : "v" + m.version;
          // One package per platform; the backend picks the one it can install.
          result = { latest: v, msi: m.msiUrl || "", arch: m.archUrl || "", deb: m.debUrl || "", rpm: m.rpmUrl || "" };
          // SHA-256 of each package: the backend installs a download only when it matches.
          result.hashes = { msi: m.msiSha256 || "", arch: m.archSha256 || "", deb: m.debSha256 || "", rpm: m.rpmSha256 || "" };
        } catch (e) {
          console.error("[A2Tools] Update check failed:", e);
          return;
        }

        const latest = result.latest;
        const latestInfo = parseVersion(latest);
        const currentInfo = parseVersion(current);
        const hasUpdate =
          latestInfo.value > currentInfo.value ||
          (latestInfo.value === currentInfo.value &&
            currentInfo.prerelease &&
            !latestInfo.prerelease);

        if (!hasUpdate) return;

        console.log("[A2Tools] Update available:", current, "->", latest);
        await window.__TAURI__.core.invoke("show_update_window", {
          current,
          latest,
          msiUrl: result.msi,
          archUrl: result.arch,
          debUrl: result.deb,
          rpmUrl: result.rpm,
          msiSha256: result.hashes.msi,
          archSha256: result.hashes.arch,
          debSha256: result.hashes.deb,
          rpmSha256: result.hashes.rpm,
        });
      } catch (e) {
        console.error("[A2Tools] Update check error:", e);
      }
    }, START_DELAY);

  window.ReleaseChecker = { start };
})();
