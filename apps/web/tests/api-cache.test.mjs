import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer } from "vite";

// Exercise the browser client with mocked network/storage; never contact a backend.
test("offline report fallback respects expiry, authentication and HTTP status", async () => {
  const storage = new Map();
  const originals = { fetch: globalThis.fetch, window: globalThis.window, localStorage: globalThis.localStorage };
  const vite = await createServer({ configFile: false, server: { middlewareMode: true }, logLevel: "silent" });
  try {
    globalThis.window = { location: { hash: "#/reports" } };
    globalThis.localStorage = {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    };
    const { getJson } = await vite.ssrLoadModule("/src/lib/api/client.ts");
    const { setToken, clearToken } = await vite.ssrLoadModule("/src/stores/auth.ts");
    const success = () => Promise.resolve(Response.json({ id: 1 }));
    const offline = () => Promise.reject(new TypeError("offline"));

    globalThis.fetch = success;
    await getJson("/reports");
    globalThis.fetch = offline;
    assert.deepEqual(await getJson("/reports"), { id: 1 });

    setToken("test-token");
    await assert.rejects(getJson("/reports"), /offline/);
    globalThis.fetch = success;
    await getJson("/portfolio/config");
    clearToken();
    globalThis.fetch = offline;
    await assert.rejects(getJson("/portfolio/config"), /offline/);

    globalThis.fetch = () => Promise.resolve(new Response(null, { status: 403 }));
    await assert.rejects(getJson("/reports"), /Unauthorized/);
    assert.match(window.location.hash, /^#\/auth\?/);
    const key = [...storage.keys()].find((k) => k.endsWith("/reports"));
    storage.set(key, JSON.stringify({ timestamp: Date.now() - 360000, value: { id: 1 } }));
    globalThis.fetch = offline;
    await assert.rejects(getJson("/reports"), /offline/);
  } finally {
    await vite.close();
    Object.assign(globalThis, originals);
  }
});
