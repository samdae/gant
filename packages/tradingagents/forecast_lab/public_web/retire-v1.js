/* Retire the GANT v1 root Workbox registration after the v2 console cutover. */
self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const scope = self.registration.scope;
    const windows = await self.clients.matchAll({ type: "window" });
    try {
      await caches.delete("workbox-precache-v2-" + scope);
    } finally {
      await self.registration.unregister();
      await Promise.allSettled(windows.map((client) => {
        const url = new URL(client.url);
        if (url.origin === self.location.origin &&
            (url.pathname === "/" || url.pathname === "/index.html")) {
          return client.navigate(client.url);
        }
      }));
    }
  })());
});
