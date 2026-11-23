import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
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
});
