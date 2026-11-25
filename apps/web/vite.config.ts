import { defineConfig, loadEnv } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig(({ mode }) => ({
  css: loadEnv(mode, ".", "VITE_").VITE_FORECAST_LAB === "1" ? {
    postcss: { plugins: [{
      postcssPlugin: "workspace-local-fonts",
      AtRule: { import(rule) {
        if (rule.params.includes("cdn.jsdelivr.net/gh/orioncactus/pretendard")) rule.remove();
      } }
    }] }
  } : undefined,
  plugins: [
    {
      name: "forecast-lab-document",
      enforce: "pre",
      apply: () => loadEnv(mode, ".", "VITE_").VITE_FORECAST_LAB === "1",
      transformIndexHtml(html) {
        return html
          .replace('<html lang="en">', '<html lang="ko" class="gant-workspace">')
          .replace(/(<meta name="viewport"\s+content=")[^"]*/, '$1width=device-width, initial-scale=1, viewport-fit=cover')
          .replace('<meta name="theme-color" content="#0d0f13" />', '<meta name="theme-color" content="#18191b" />\n  <meta name="color-scheme" content="dark" />')
          .replace("<title>GANT</title>", "<title>GANT &middot; Forecast Lab</title>")
          .replace(/<link\b[^>]*https:\/\/fonts\.(?:googleapis|gstatic)\.com[^>]*>\s*/g, "");
      },
    },
    svelte(),
    VitePWA({
      disable: loadEnv(mode, ".", "VITE_").VITE_FORECAST_LAB === "1",
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
  },
}));
