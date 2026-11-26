import assert from "node:assert/strict";
import { test } from "node:test";
import { createServer } from "vite";

const hour = 3_600_000;

test("anonymous four-hour public reads", async (t) => {
  const stored = new Map();
  const client = {
    get length() { return stored.size; },
    key: (index) => [...stored.keys()][index] ?? null,
    getItem: (key) => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: (key) => stored.delete(key),
  };
  const realNow = Date.now();
  let now = realNow, cookie = "", lastCookie = "", calls = 0, status = 200;
  let body = () => ({version: calls});
  const document = {
    get cookie() { return cookie; },
    set cookie(value) {
      lastCookie = value;
      cookie = value.split(";")[0];
    },
    querySelector: () => ({getAttribute: () => "public-readonly"}),
  };
  for (const [key, value] of Object.entries({ document, location: {protocol: "https:"}, localStorage: client, window: {localStorage: client} })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, key);
    Object.defineProperty(globalThis, key, {value, configurable: true});
    t.after(() => {
      if (previous) Object.defineProperty(globalThis, key, previous);
      else delete globalThis[key];
    });
  }
  t.mock.method(Date, "now", () => now);
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls++;
    assert.equal(init.credentials, "omit");
    assert.equal(init.cache, "no-store");
    assert.equal(new Headers(init.headers).has("Authorization"), false);
    return Response.json(await body(url), {status});
  });
  const server = () => createServer({
    configFile: false, server: { middlewareMode: true }, logLevel: "silent",
    define: {"import.meta.env.VITE_FORECAST_LAB": '"1"'},
  });
  const vite = await server();
  t.after(() => vite.close());
  const { publicJson: read } = await vite.ssrLoadModule("/src/lib/api/publicReads.ts");
  const { getJson, postJson } = await vite.ssrLoadModule("/src/lib/api/client.ts");
  const { researchGet } = await vite.ssrLoadModule("/src/lib/researchEvidence.ts");
  const signal = new AbortController().signal;

  await t.test("survives a new application instance and expires per URL, independently of later writes", async () => {
    const a = "/reports?ticker=NVDA&limit=20", b = "/reports?ticker=IBM&limit=20";
    assert.deepEqual(await getJson(a), {version: 1});
    const keys = [...stored.keys()];
    assert.equal(keys.length, 1);
    assert.match(keys[0], /:GET:\/workspace-api\/reports\?ticker=NVDA&limit=20$/);
    assert.match(lastCookie, /^gant_read_cache=v1\.[a-f0-9]{32}; Path=\/; Max-Age=14400; SameSite=Strict; Secure$/);
    const restarted = await server();
    try {
      const next = await restarted.ssrLoadModule("/src/lib/api/client.ts");
      now += 3 * hour;
      assert.deepEqual(await next.getJson(a), {version: 1});
      assert.deepEqual(await next.getJson(b), {version: 2});
      now += hour;
      assert.deepEqual(await next.getJson(a), {version: 3});
      assert.deepEqual(await next.getJson(b), {version: 2});
    } finally { await restarted.close(); }
  });

  await t.test("refresh reaches the server, transient errors are visible and revocations purge a prior hit", async () => {
    const url = "cases?ticker=GE&limit=200";
    const first = await researchGet(url, signal);
    assert.deepEqual(await researchGet(url, signal), first);
    const fresh = await researchGet(url, signal, {refresh: true});
    assert.notDeepEqual(fresh, first);
    assert.deepEqual(await researchGet(url, signal), fresh);
    status = 503;
    await assert.rejects(researchGet(url, signal, {refresh: true}), /연구 자료/);
    assert.deepEqual(await researchGet(url, signal), fresh);
    status = 404;
    await assert.rejects(researchGet(url, signal, {refresh: true}), /찾을 수 없/);
    await assert.rejects(researchGet(url, signal), /찾을 수 없/);
    status = 200;
    assert.notDeepEqual(await researchGet(url, signal), fresh);
  });

  await t.test("public history is reusable while open cases expire at their next trading boundary", async () => {
    const entry = now + hour, exit = now + 5 * hour;
    let source = "uncollected";
    body = () => ({
      version: calls, status: "awaiting", entry_open_at: new Date(entry).toISOString(),
      exit_close_at: new Date(exit).toISOString(), issues: {status: "empty"}, last30days: {status: source},
    });
    const beforeOpen = await read("/api/cases/20");
    const list = await read("/api/cases?ticker=IBM&limit=200&before_id=21");
    assert.deepEqual(await read("/api/cases/20"), beforeOpen);
    now = entry;
    const open = await read("/api/cases/20");
    assert.notDeepEqual(open, beforeOpen);
    assert.deepEqual(await read("/api/cases/20"), open);
    assert.deepEqual(await read("/api/cases?ticker=IBM&limit=200&before_id=21"), list);
    now = exit;
    assert.notDeepEqual(await read("/api/cases/20"), await read("/api/cases/20"));
    source = "failed";
    assert.notDeepEqual(await read("/api/report-sources/7"), await read("/api/report-sources/7"));
    source = "available";
    assert.deepEqual(await read("/api/report-sources/7"), await read("/api/report-sources/7"));
  });

  await t.test("live and account endpoints bypass browser storage and mutation is refused", async () => {
    body = () => ({version: calls});
    const entries = stored.size;
    for (const path of ["/api/status", "/api/stats?market=us", "/workspace-api/queue", "/workspace-api/portfolio/config"]) {
      assert.notDeepEqual(await read(path), await read(path));
    }
    const before = calls;
    await assert.rejects(postJson("/reports", {}), /조회만/);
    assert.equal(calls, before);
    assert.equal(stored.size, entries);
  });

  await t.test("simultaneous readers share work and an older response cannot overwrite manual refresh", async () => {
    const resolvers = [];
    body = () => new Promise(resolve => resolvers.push(resolve));
    const controller = new AbortController();
    const url = "/api/forecast-tickers";
    const abandoned = read(url, {signal: controller.signal});
    const original = read(url);
    controller.abort();
    await assert.rejects(abandoned, {name: "AbortError"});
    const refreshed = read(url, {refresh: true});
    assert.equal(resolvers.length, 2);
    resolvers[1]([{ticker: "GE", id: 8}]);
    const expected = await refreshed;
    resolvers[0]([{ticker: "GE", id: 6}]);
    await original;
    assert.deepEqual(await read(url), expected);
  });

  await t.test("origin cookie removal, capacity and blocked storage fall back safely", async () => {
    body = () => ({version: calls});
    const url = "/workspace-api/tickers/names";
    const first = await read(url);
    cookie = "";
    assert.notDeepEqual(await read(url), first);
    stored.set("unrelated", "unchanged");
    for (let i = 1; i <= 68; i++) await read("/public-api/reports/" + i);
    assert.equal(stored.size, 65);
    body = () => ({large: "x".repeat(800_000)});
    await read("/public-api/reports/70");
    await read("/public-api/reports/71");
    assert.ok([...stored].reduce((sum, [key, value]) => sum + key.length + value.length, 0) <= 1_500_100);
    assert.equal(stored.get("unrelated"), "unchanged");
    body = () => ({version: calls});
    const getter = t.mock.method(client, "getItem", () => { throw Error("blocked"); });
    const setter = t.mock.method(client, "setItem", () => { throw Error("blocked"); });
    assert.notDeepEqual(await read(url), await read(url));
    const {viewMode} = await vite.ssrLoadModule("/src/stores/mode.ts");
    const {currencyFilter} = await vite.ssrLoadModule("/src/stores/currency.ts");
    const observed = [];
    const stop = viewMode.subscribe(value => observed.push(value));
    viewMode.set("portfolio");
    stop();
    const stopCurrency = currencyFilter.subscribe(value => observed.push(value));
    stopCurrency();
    assert.deepEqual(observed, ["analysis", "portfolio", "ALL"]);
    getter.mock.restore();
    setter.mock.restore();
  });
});
