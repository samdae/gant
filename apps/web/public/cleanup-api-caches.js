// Remove responses stored by earlier workers, including authenticated portfolio reads.
self.addEventListener("activate", (event) => {
  event.waitUntil(Promise.all(["api-cache", "api-reports-cache"].map((name) => caches.delete(name))));
});
