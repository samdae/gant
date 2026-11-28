import { createHash, randomUUID } from "node:crypto";
import { link, mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { basename, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { pulsePath, pulseMiddleware } from "./v4-report-pulse.mjs";

const prefix = "/v4/";
const bookmarkRoot = new URL("../packages/tradingagents/forecast_lab/web/", import.meta.url);
const researchBookmarks = new Map([
  ["/research", "workspace-bookmark.html"], ["/research/", "workspace-bookmark.html"],
  ["/research/index.html", "workspace-bookmark.html"],
  ["/research/workspace-bookmark.js", "workspace-bookmark.js"],
]);
const assetName = /^[\w.-]+-[\w-]{8,}\.(?:js|css|svg|png|webp|avif|woff2)$/;
const releaseId = /^[a-f0-9]{64}$/;
const installFiles = new Set([
  "index.html", "favicon.svg", "gant.webmanifest", "gant-sw.js", "apple-touch-icon.png",
  "gant-192.png", "gant-512.png", "gant-maskable-192.png", "gant-maskable-512.png",
]);
const mimeTypes = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json",
  ".png": "image/png", ".webp": "image/webp", ".avif": "image/avif", ".woff2": "font/woff2",
};
const securityHeaders = {
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "SAMEORIGIN",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; frame-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'",
};

function shellAssets(html) {
  if (!html.includes('name="forecast-console-access" content="public-readonly"')
      || !html.includes('href="/v4/gant.webmanifest"') || !html.includes('href="/v4/favicon.svg"')) {
    throw Error("Expected the public /v4/ shell. Build with npm run build:v4.");
  }
  const links = [...html.matchAll(/(?:src|href)="\/v4\/assets\/([^"]+)"/g)].map(match => match[1]);
  if (!links.some(name => name.endsWith(".js")) || !links.some(name => name.endsWith(".css"))
      || !links.every(name => assetName.test(name))) throw Error("Invalid v4 shell assets");
  return links;
}

async function putImmutable(file, bytes) {
  const pending = file + "." + randomUUID();
  try {
    await writeFile(pending, bytes, { flag: "wx" });
    // Link only the completed file. Interrupted writes never occupy an immutable URL.
    try {
      await link(pending, file);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      if (!(await readFile(file)).equals(bytes)) throw Error("Release file collision at " + basename(file));
    }
  } finally {
    await rm(pending, { force: true });
  }
}

export async function activate(runtime, revision) {
  if (!releaseId.test(revision)) throw Error("Invalid release id");
  const shell = await readFile(join(runtime, "releases", revision, "index.html"), "utf8");
  for (const asset of shellAssets(shell)) await readFile(join(runtime, "assets", asset));
  const pointer = join(runtime, "current");
  const pending = pointer + "." + randomUUID();
  await writeFile(pending, revision, { flag: "wx" });
  await rename(pending, pointer);
}

export async function publish(runtime, dist) {
  const files = new Map();
  for (const name of installFiles) files.set(name, await readFile(join(dist, name)));
  const links = shellAssets(files.get("index.html").toString());
  const manifest = JSON.parse(files.get("gant.webmanifest"));
  if (manifest.id !== prefix || manifest.scope !== prefix || manifest.start_url !== "/v4/#/reports"
      || !manifest.icons.every(icon => icon.src.startsWith(prefix) && installFiles.has(icon.src.slice(prefix.length)))) {
    throw Error("Invalid v4 install scope");
  }
  await mkdir(join(runtime, "assets"), { recursive: true });
  const assets = await readdir(join(dist, "assets"));
  if (!links.every(name => assets.includes(name))) throw Error("Missing assets for the v4 shell");
  for (const name of assets) {
    if (!assetName.test(name)) throw Error("Unexpected build asset " + name);
    await putImmutable(join(runtime, "assets", name), await readFile(join(dist, "assets", name)));
  }
  const hash = createHash("sha256");
  for (const [name, bytes] of files) hash.update(name).update(createHash("sha256").update(bytes).digest());
  const revision = hash.digest("hex");
  const release = join(runtime, "releases", revision);
  await mkdir(release, { recursive: true });
  for (const [name, bytes] of files) await putImmutable(join(release, name), bytes);
  await activate(runtime, revision);
  return revision;
}

export function previewServer(runtime, readPulse) {
  const servePulse = pulseMiddleware(readPulse);
  return createServer(async (req, res) => {
    res.setHeaders(new Headers(securityHeaders));
    res.setHeader("Cache-Control", "no-store");
    const stop = (code) => { res.writeHead(code); res.end(); };
    if (req.method !== "GET" && req.method !== "HEAD") {
      res.setHeader("Allow", "GET, HEAD");
      return stop(405);
    }
    const path = req.url.split("?", 1)[0];
    const search = req.url.slice(path.length);
    if (path === "/" || path === "/index.html") {
      // Omitting the fragment lets the browser carry the original hash route to v4.
      res.setHeader("Location", prefix + search);
      return stop(307);
    }
    if (path === pulsePath) return servePulse(req, res);
    if (path === "/v4") { res.setHeader("Location", prefix + search); return stop(308); }
    const bookmark = researchBookmarks.get(path);
    if (bookmark === "workspace-bookmark.html") {
      const match = /^\?case=([1-9]\d{0,15})$/.exec(search);
      if (match) { res.setHeader("Location", prefix + "#/research/" + match[1]); return stop(307); }
    }
    if (!bookmark && !path.startsWith(prefix)) return stop(404);
    const relative = bookmark || path.slice(prefix.length) || "index.html";
    const asset = relative.startsWith("assets/") && assetName.test(relative.slice(7));
    if (!bookmark && !asset && !installFiles.has(relative)) return stop(404);
    try {
      let file;
      if (bookmark) {
        // This navigation shim translates legacy #results and #observe in the browser.
        file = new URL(bookmark, bookmarkRoot);
      } else if (asset) {
        file = join(runtime, relative);
      } else {
        const revision = await readFile(join(runtime, "current"), "utf8");
        if (!releaseId.test(revision)) return stop(503);
        file = join(runtime, "releases", revision, relative);
      }
      const bytes = await readFile(file);
      res.setHeader("Content-Type", mimeTypes[extname(relative)]);
      res.setHeader("Content-Length", bytes.length);
      res.setHeader("Cache-Control", asset ? "public, max-age=31536000, immutable" : "no-cache");
      if (relative === "gant-sw.js") res.setHeader("Service-Worker-Allowed", prefix);
      res.writeHead(200);
      res.end(req.method === "HEAD" ? undefined : bytes);
    } catch (error) {
      if (error.code !== "ENOENT") console.error(error);
      stop(asset && error.code === "ENOENT" ? 404 : 503);
    }
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const runtime = join(process.env.LOCALAPPDATA, "TradingAgentsV4", "web");
  const [command, argument] = process.argv.slice(2);
  if (command === "serve") {
    previewServer(runtime).listen(8035, "127.0.0.1", () => console.log("GANT v4 at http://127.0.0.1:8035/v4/"));
  } else if (command === "publish" && argument) {
    console.log("Published", await publish(runtime, resolve(argument)));
  } else if (command === "activate" && argument) {
    await activate(runtime, argument);
    console.log("Activated", argument);
  } else {
    throw Error("Usage: node scripts/v4-preview.mjs publish <dist> | activate <release-id> | serve");
  }
}
