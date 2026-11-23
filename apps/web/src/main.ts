import "./styles/base.css";
import App from "./App.svelte";

const target = document.getElementById("app");

if (target) {
  new App({ target });
}

if (import.meta.env.PROD && "serviceWorker" in navigator) {
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
