import { defineConfig } from "vite";
import { copyFileSync, cpSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({

  plugins: [{
    name: "ui-resources",
    // Dev-only visual fixtures exercise real markup without native capture,
    // game writes, downloads or installation. Never included in build inputs.
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const entry = req.url?.split("?")[0];
        if (entry !== "/__visual/launcher.html" && entry !== "/__visual/index.html") return next();
        const html = readFileSync(join(server.config.root, entry.endsWith("launcher.html") ? "launcher.html" : "index.html"), "utf8");
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.end(html.replace("<head>", '<head><script src="/visual-tests/native-fixture.js"></script>'));
      });
    },
    configResolved(config) {
      const dataDir = join(config.publicDir, "data");
      mkdirSync(dataDir, { recursive: true });
      copyFileSync(join(config.root, "src/data/skill_icons.json"), join(dataDir, "skill_icons.json"));
      cpSync(join(config.root, "src/data/i18n"), join(config.publicDir, "i18n"), { recursive: true });
    },
  }],
  build: { rollupOptions: { input: { meter: "index.html", launcher: "launcher.html", confirmation: "confirmation.html" } } },

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
  },
}));
