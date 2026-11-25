import "./styles/base.css";
import "./styles/application-tokens.css";
import "./styles/console-workspace.css";
import "./styles/folio-workspace.css";
import "./styles/application-controls.css";
import App from "./App.svelte";

import { isForecastLab } from "./lib/workspace";

if (isForecastLab && !window.location.hash) {
  history.replaceState(history.state, "", "#/research");
}

const target = document.getElementById("app");

if (target) {
  new App({ target });
}

if (!isForecastLab && import.meta.env.PROD && "serviceWorker" in navigator) {
  // The bundle filename changes per build. Older CDN entries for /sw.js
  // must not precache the previous dashboard on a fresh visit.
  const worker = new URL("/sw.js", location.origin);
  worker.searchParams.set("build", new URL(import.meta.url).pathname);
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(worker, { updateViaCache: "none" }).catch((error) => {
      console.warn("Service worker registration failed", error);
    });
  });
}
