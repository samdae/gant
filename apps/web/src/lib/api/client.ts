import { get } from "svelte/store";
import { clearToken, tokenStore } from "../../stores/auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const CACHE_PREFIX = "gant_api_cache:";
const CACHE_TTL_MS = 60 * 5 * 1000;

type CacheEntry<T> = {
  timestamp: number;
  value: T;
};

const getCacheKey = (url: string) => `${CACHE_PREFIX}${url}`;

const readCache = <T>(key: string) => {
  if (typeof localStorage === "undefined") return null;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CacheEntry<T>;
    if (!parsed || typeof parsed.timestamp !== "number") return null;
    return parsed;
  } catch {
    return null;
  }
};

const writeCache = <T>(key: string, value: T) => {
  if (typeof localStorage === "undefined") return;
  try {
    const payload: CacheEntry<T> = { timestamp: Date.now(), value };
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    return;
  }
};

const redirectToAuth = () => {
  if (typeof window === "undefined") return;
  const returnTo = window.location.hash || "#/";
  const encoded = encodeURIComponent(returnTo);
  window.location.hash = `#/auth?return=${encoded}`;
};

const request = async <T>(
  path: string,
  options: RequestInit = {}
): Promise<T> => {
  const headers = new Headers(options.headers || {});
  const token = get(tokenStore);
  const method = (options.method || "GET").toUpperCase();

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const requestUrl = `${BASE_URL}${path}`;
  const shouldCache = method === "GET" && !headers.has("Authorization");
  const cacheKey = getCacheKey(requestUrl);

  try {
    const res = await fetch(requestUrl, {
      ...options,
      headers,
    });

    if (res.status === 401 || res.status === 403) {
      clearToken();
      redirectToAuth();
      throw new Error("Unauthorized");
    }

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Request failed: ${res.status}`);
    }

    if (res.status === 204) {
      return {} as T;
    }

    const data = (await res.json()) as T;
    if (shouldCache) {
      writeCache(cacheKey, data);
    }
    return data;
  } catch (err) {
    if (shouldCache) {
      const cached = readCache<T>(cacheKey);
      if (cached) {
        const isStale = Date.now() - cached.timestamp > CACHE_TTL_MS;
        const isOnline = typeof navigator === "undefined" ? true : navigator.onLine;
        if (!isOnline || !isStale) {
          return cached.value;
        }
        return cached.value;
      }
    }
    throw err;
  }
};

const getJson = <T>(path: string) => request<T>(path);

const postJson = <T, U>(path: string, body: U) =>
  request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });

const deleteJson = <T>(path: string) =>
  request<T>(path, {
    method: "DELETE",
  });

export { BASE_URL, getJson, postJson, deleteJson };
