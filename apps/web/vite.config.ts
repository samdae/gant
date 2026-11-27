import { readFileSync } from "node:fs";
import { defineConfig, loadEnv } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";
import { pulseMiddleware } from "../../scripts/v4-report-pulse.mjs";

export default defineConfig(({ mode }) => {
  const v4 = mode === "v4";
  const lab = v4 || loadEnv(mode, ".", "VITE_").VITE_FORECAST_LAB === "1";
  const folder = new URL(v4 ? "./v4-pwa/" : "./lab-pwa/", import.meta.url);
  const installFiles = [
    "favicon.svg", "gant.webmanifest", "gant-sw.js", "apple-touch-icon.png",
    "gant-192.png", "gant-512.png", "gant-maskable-192.png", "gant-maskable-512.png",
  ];
  const installAsset = (name: string) => readFileSync(name === "gant-sw.js" ?
    new URL("./lab-pwa/gant-sw.js", import.meta.url) : new URL(name, folder));
  const previewApi = {
    "/api/": "http://127.0.0.1:8025",
    "/workspace-api/": "http://127.0.0.1:8025",
    "/public-api/": "http://127.0.0.1:8025",
  };
  return {
    base: v4 ? "/v4/" : "/",
    define: v4 ? { "import.meta.env.VITE_FORECAST_LAB": JSON.stringify("1") } : undefined,
    css: lab ? {
      postcss: { plugins: [{
        postcssPlugin: "workspace-local-fonts",
        AtRule: { import(rule) {
          if (rule.params.includes("cdn.jsdelivr.net/gh/orioncactus/pretendard")) rule.remove();
        } }
      }] }
    } : undefined,
    plugins: [
      {
        name: "v4-report-pulse",
        apply: () => v4,
        configureServer(server) { server.middlewares.use(pulseMiddleware()); },
        configurePreviewServer(server) { server.middlewares.use(pulseMiddleware()); },
      },
      {
        name: "forecast-lab-document",
        enforce: "pre",
        apply: () => lab,
        configureServer(server) {
          if (!v4) return;
          server.middlewares.use((req, res, next) => {
            const path = req.url?.split("?", 1)[0] ?? "";
            const file = path.slice("/v4/".length);
            if (!path.startsWith("/v4/") || !installFiles.includes(file) || req.method !== "GET") return next();
            const type = file.endsWith(".png") ? "image/png" : file.endsWith(".svg") ? "image/svg+xml" :
              file.endsWith(".js") ? "text/javascript" : "application/manifest+json";
            res.setHeader("Content-Type", type);
            res.end(installAsset(file));
          });
        },
        generateBundle() {
          for (const fileName of installFiles) {
            this.emitFile({ type: "asset", fileName, source: installAsset(fileName) });
          }
        },
        transformIndexHtml(html) {
          const iconBase = v4 ? "/v4/" : "/";
          const tint = v4 ? "#000000" : "#18191b";
          const workspaceClass = v4 ? "gant-workspace gant-v4" : "gant-workspace";
          const access = v4 ? '<meta name="forecast-console-access" content="public-readonly">' : "";
          return html
            .replace('<html lang="en">', `<html lang="ko" class="${workspaceClass}">`)
            .replace(/(<meta name="viewport"\s+content=")[^"]*/, '$1width=device-width, initial-scale=1, viewport-fit=cover')
            .replace('<meta name="theme-color" content="#0d0f13" />', `<meta name="theme-color" content="${tint}" />\n  <meta name="color-scheme" content="dark" />`)
            .replace("</head>", `${access}<link rel="manifest" href="${iconBase}gant.webmanifest" crossorigin="use-credentials" />\n<link rel="apple-touch-icon" sizes="180x180" href="${iconBase}apple-touch-icon.png" />\n</head>`)
            .replace("<title>GANT</title>", v4 ? "<title>GANT v4 · 예측 연구실</title>" : "<title>GANT &middot; Forecast Lab</title>")
            .replace(/<link\b[^>]*https:\/\/fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*/g, "");
        },
      },
      svelte(),
      VitePWA({
        disable: lab,
        registerType: "autoUpdate",
        injectRegister: false,
        includeAssets: ["favicon.svg", "icon.svg"],
        manifest: {
          name: "GANT Trading Console",
          short_name: "GANT",
          description: "AI-driven trading analysis dashboard",
          theme_color: "#0d0f13",
          background_color: "#0d0f13",
          display: "standalone",
          start_url: "/",
          icons: [
            {
              src: "/icon.svg",
              sizes: "any",
              type: "image/svg+xml",
              purpose: "any maskable",
            },
          ],
        },
        workbox: {
          skipWaiting: true,
          clientsClaim: true,
          importScripts: ["cleanup-api-caches.js"],
        },
      }),
    ],
    server: {
      port: 5173,
      proxy: v4 ? previewApi : undefined,
    },
    preview: v4 ? { proxy: previewApi } : undefined,
  };
});
