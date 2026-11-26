/** Anonymous, versioned public projections only. All other reads go straight to the network. */
const TTL = 4 * 60 * 60 * 1000;
const COOKIE = "gant_read_cache";
const PREFIX = "gant:public-reads:v1:";
const MAX_ENTRIES = 64;
const MAX_CHARS = 1_500_000; // Roughly 3 MB in UTF-16, leaving room for other origin storage.
const publishedRoute = /^\/(?:api\/(?:forecast-tickers|cases(?:\/[1-9]\d*)?|report-sources\/[1-9]\d*)|workspace-api\/(?:reports(?:\/tickers)?|tickers\/names)|public-api\/reports\/[1-9]\d*)$/;
const pending = new Map<string, Promise<unknown>>();

type Options = {
  signal?: AbortSignal | null;
  refresh?: boolean;
  errorMessage?: string;
  notFoundMessage?: string;
};

function cookieToken(): string | undefined {
  return document.cookie.match(/(?:^|;\s*)gant_read_cache=(v1\.[\da-f]{32})(?:;|$)/)?.[1];
}

function setCookie(token: string) {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE}=${token}; Path=/; Max-Age=${TTL / 1000}; SameSite=Strict${secure}`;
}

function cacheToken(): string | undefined {
  try {
    const existing = cookieToken();
    if (existing) return existing;
    const random = crypto.getRandomValues(new Uint8Array(16));
    const token = "v1." + Array.from(random, b => b.toString(16).padStart(2, "0")).join("");
    setCookie(token);
    return cookieToken();
  } catch {
    // Restricted cookies, browser storage, or embedded contexts can still fetch normally.
    return undefined;
  }
}

function readStored<T>(key: string): { value: T } | undefined {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return;
    const split = raw.indexOf("\n");
    const until = Number(raw.slice(0, split));
    if (split > 0 && until > Date.now() && until <= Date.now() + TTL) {
      return { value: JSON.parse(raw.slice(split + 1)) as T };
    }
    localStorage.removeItem(key);
  } catch { /* Cache misses include corrupt or inaccessible storage. */ }
}

function expiry(path: string, value: unknown, now: number): number {
  if (value === null || typeof value !== "object") return 0;
  const until = now + TTL;
  if (!/^\/api\/(cases|report-sources)\//.test(path)) return until;
  const record = value as {
    status?: string; entry_open_at?: string; exit_close_at?: string;
    issues?: { status?: string }; last30days?: { status?: string };
  };
  // "uncollected" is a frozen as-of result. A missing or failed source is retryable.
  const completedSource = (source?: {status?: string}) =>
    source?.status === "available" || source?.status === "empty" || source?.status === "uncollected";
  if (!completedSource(record.issues) || !completedSource(record.last30days)) return 0;
  if (!path.startsWith("/api/cases/")) return until;
  if (record.status === "matured" || record.status === "excluded") return until;
  if (record.status !== "awaiting") return 0;
  const entry = Date.parse(record.entry_open_at || "");
  const exit = Date.parse(record.exit_close_at || "");
  // Fetch again when the trading horizon opens or matures; an overdue unscored case is live.
  if (!Number.isFinite(exit) || exit <= now) return 0;
  return Math.min(until, entry > now ? entry : exit, exit);
}

function storeResult(key: string, token: string, path: string, value: unknown) {
  try {
    if (cookieToken() !== token) return; // Cookies may have been cleared during the fetch.
    const now = Date.now();
    const until = expiry(path, value, now);
    localStorage.removeItem(key);
    if (!until) return;
    const raw = until + "\n" + JSON.stringify(value);
    let chars = key.length + raw.length;
    if (chars > MAX_CHARS) return;
    const entries: { name: string; until: number; chars: number }[] = [];
    for (let i = localStorage.length - 1; i >= 0; i--) {
      const name = localStorage.key(i);
      if (!name?.startsWith(PREFIX)) continue;
      const stored = localStorage.getItem(name);
      if (!stored) continue;
      const expires = Number(stored.slice(0, stored.indexOf("\n")));
      if (!name.startsWith(PREFIX + token + ":") || !(expires > now)) {
        localStorage.removeItem(name);
        continue;
      }
      const size = stored.length + name.length;
      chars += size;
      entries.push({ name, until: expires, chars: size });
    }
    entries.sort((a, b) => b.until - a.until);
    while (entries.length && (entries.length >= MAX_ENTRIES || chars > MAX_CHARS)) {
      const oldest = entries.pop()!;
      localStorage.removeItem(oldest.name);
      chars -= oldest.chars;
    }
    localStorage.setItem(key, raw);
    setCookie(token); // Renew the namespace on writes; individual entries retain their own deadline.
  } catch { /* Storage quota or privacy settings must never prevent a successful read. */ }
}

function observe<T>(request: Promise<T>, signal?: AbortSignal | null): Promise<T> {
  if (!signal) return request;
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException("Request aborted", "AbortError"));
    signal.addEventListener("abort", abort, { once: true });
    request.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

export async function publicJson<T>(url: string, options: Options = {}): Promise<T> {
  const { signal, refresh } = options;
  if (signal?.aborted) throw new DOMException("Request aborted", "AbortError");
  const path = url.split("?")[0];
  const token = publishedRoute.test(path) ? cacheToken() : undefined;
  const key = token ? PREFIX + token + ":GET:" + url : "";

  let request: Promise<T>;
  async function download(shared: boolean): Promise<T> {
    const response = await fetch(url, { credentials: "omit", cache: "no-store", signal: shared ? undefined : signal });
    if (!response.ok) {
      if ([401, 403, 404, 410].includes(response.status) && shared && pending.get(key) === request) {
        try { localStorage.removeItem(key); } catch { /* Storage may be disabled. */ }
      }
      if (response.status === 401 || response.status === 403) throw new Error("공개 조회가 제공되지 않는 자료입니다.");
      throw new Error((response.status === 404 && options.notFoundMessage) || options.errorMessage || "공개 자료를 조회하지 못했습니다.");
    }
    return response.status === 204 ? {} as T : response.json();
  }
  if (!token) return download(false);
  if (!refresh) {
    const loading = pending.get(key) as Promise<T> | undefined;
    if (loading) return observe(loading, signal);
    const hit = readStored<T>(key);
    if (hit) return hit.value;
  }
  // Multiple consumers can leave independently. Only the newest request may replace this entry.
  request = download(true).then(value => {
    if (pending.get(key) === request) storeResult(key, token, path, value);
    return value;
  }).finally(() => { if (pending.get(key) === request) pending.delete(key); });
  pending.set(key, request);
  return observe(request, signal);
}
