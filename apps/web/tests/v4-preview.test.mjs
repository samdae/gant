import assert from "node:assert/strict";
import { mkdtemp, mkdir, copyFile, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { once } from "node:events";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { activate, previewServer, publish } from "../../../scripts/v4-preview.mjs";

test("v4 browser and installed app share a black launch surface", async t => {
  const root = new URL("../", import.meta.url);
  const vite = await createServer({
    root: fileURLToPath(root), mode: "v4", logLevel: "silent",
    server: { middlewareMode: true, hmr: false, preTransformRequests: false, watch: null },
  });
  t.after(() => vite.close());
  const shell = await readFile(new URL("index.html", root), "utf8");
  const html = await vite.transformIndexHtml("/v4/", shell);
  const manifest = JSON.parse(await readFile(new URL("v4-pwa/gant.webmanifest", root), "utf8"));

  assert.equal(manifest.background_color, "#000000");
  assert.equal(manifest.theme_color, manifest.background_color);
  assert.equal(html.match(/<meta name="theme-color" content="([^"]+)"/)?.[1], manifest.theme_color);
  assert.match(html, /<meta name="color-scheme" content="dark"/);
  assert.match(html, /href="\/v4\/gant\.webmanifest"/);
  assert.match(html, /href="\/v4\/apple-touch-icon\.png"/);
});

test("public entry URLs carry hash routes and translate research bookmarks", async t => {
  const server = previewServer();
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());
  const base = "http://127.0.0.1:" + server.address().port;
  const request = (path, method = "GET") => fetch(base + path, { method, redirect: "manual" });
  for (const path of ["/", "/index.html"]) {
    const res = await request(path + "?view=public#/reports/btc-usd", "HEAD");
    assert.equal(res.status, 307);
    assert.equal(res.headers.get("Location"), "/v4/?view=public");
    assert.equal(res.headers.get("Cache-Control"), "no-store");
  }
  assert.equal((await request("/research/?case=35")).headers.get("Location"), "/v4/#/research/35");
  const shim = "/research/workspace-bookmark.js";
  for (const path of ["/research", "/research/", "/research/index.html", "/research/?embedded=1"]) {
    const res = await request(path);
    assert.equal(res.status, 200);
    assert.ok((await res.text()).includes(shim));
  }
  const script = await (await request(shim)).text();
  for (const [hash, search, expected] of [
    ["#observe", "?market=kr", "/#/observe?market=kr"],
    ["#results", "?from_date=2026-11-20", "/#/results?from_date=2026-11-20"],
    ["", "?case=35&market=us", "/#/research/35?market=us"],
    ["", "?case=other", "/#/research"],
  ]) {
    let destination;
    runInNewContext(script, { URLSearchParams, location: { hash, search, replace: url => destination = url } });
    assert.equal(destination, expected);
  }
  assert.equal((await request("/", "POST")).status, 405);
  assert.equal((await request("/research/lab.js")).status, 404);
});

test("v4 serves independent install assets and switches complete releases", async t => {
  const dir = await mkdtemp(join(tmpdir(), "gant-v4-release-"));
  t.after(async () => {
    assert.equal(dirname(resolve(dir)), resolve(tmpdir()));
    assert.match(basename(dir), /^gant-v4-release-[a-z0-9]+$/i);
    await rm(dir, { recursive: true, force: true });
  });
  const dist = join(dir, "dist");
  const runtime = join(dir, "live");
  await mkdir(join(dist, "assets"), { recursive: true });
  const pwa = new URL("../v4-pwa/", import.meta.url);
  for (const name of ["favicon.svg", "gant.webmanifest", "apple-touch-icon.png", "gant-192.png", "gant-512.png",
    "gant-maskable-192.png", "gant-maskable-512.png"]) {
    await copyFile(fileURLToPath(new URL(name, pwa)), join(dist, name));
  }
  await copyFile(fileURLToPath(new URL("../lab-pwa/gant-sw.js", import.meta.url)), join(dist, "gant-sw.js"));
  const css = "style-aaaaaaaa.css";
  const older = "index-11111111.js";
  const newer = "index-22222222.js";
  const shell = name => '<html><head><meta name="forecast-console-access" content="public-readonly">' +
    '<link rel="icon" href="/v4/favicon.svg"><link rel="manifest" href="/v4/gant.webmanifest">' +
    '<link rel="stylesheet" href="/v4/assets/' + css + '"><script src="/v4/assets/' + name + '"></script></head></html>';
  await writeFile(join(dist, "assets", css), "body {}");
  await writeFile(join(dist, "assets", older), "const n = 1;");
  await writeFile(join(dist, "index.html"), shell(older));
  const first = await publish(runtime, dist);
  const server = previewServer(runtime);
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  t.after(() => server.close());
  const base = "http://127.0.0.1:" + server.address().port;
  const request = (path, options) => fetch(base + path, options);
  assert.match(await (await request("/v4/")).text(), /index-11111111/);
  assert.equal((await request("/v4", {redirect:"manual"})).headers.get("Location"), "/v4/");
  assert.equal((await request("/api/status")).status, 404);
  assert.equal((await request("/v4/", {method:"POST"})).status, 405);
  assert.equal((await request("/gant-sw.js")).status, 404);
  assert.equal((await request("/v4/gant-sw.js")).headers.get("Service-Worker-Allowed"), "/v4/");
  const manifest = await (await request("/v4/gant.webmanifest")).json();
  assert.equal(manifest.id, "/v4/");
  assert.equal(manifest.scope, "/v4/");
  for (const icon of manifest.icons) {
    const response = await request(icon.src);
    const bytes = Buffer.from(await response.arrayBuffer());
    const size = Number(icon.sizes.split("x")[0]);
    assert.equal(bytes.readUInt32BE(16), size);
    assert.equal(bytes.readUInt32BE(20), size);
  }
  await writeFile(join(dist, "index.html"), shell(newer));
  await assert.rejects(publish(runtime, dist), /Missing assets/);
  assert.match(await (await request("/v4/")).text(), /index-11111111/);
  await writeFile(join(dist, "assets", newer), "const n = 2;");
  const second = await publish(runtime, dist);
  assert.notEqual(first, second);
  assert.match(await (await request("/v4/")).text(), /index-22222222/);
  assert.equal((await request("/v4/assets/" + older)).status, 200);
  const head = await request("/v4/assets/" + newer, {method:"HEAD"});
  assert.match(head.headers.get("Cache-Control"), /immutable/);
  assert.equal(await head.text(), "");
  await activate(runtime, first);
  assert.match(await (await request("/v4/")).text(), /index-11111111/);
});
