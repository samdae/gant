import { get } from "svelte/store";
import { clearToken, tokenStore } from "../../stores/auth";

import { isForecastLab, isPublicViewer } from "../workspace";

const BASE_URL = isPublicViewer ? "/workspace-api" : import.meta.env.VITE_API_BASE_URL || (isForecastLab ? "/workspace-api" : "http://localhost:8000");
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
  const token = isPublicViewer ? null : get(tokenStore);
  const method = (options.method || "GET").toUpperCase();

  if (isPublicViewer && method !== "GET") throw new Error("공개 화면에서는 조회만 가능합니다.");
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const requestUrl = `${BASE_URL}${path}`;
  const shouldCache = !isPublicViewer && method === "GET" && !headers.has("Authorization") && /^\/reports(?:[/?]|$)/.test(path);
  const cacheKey = getCacheKey(requestUrl);

  let res: Response;
  try {
    res = await fetch(requestUrl, { ...options, ...(isPublicViewer ? {credentials: "omit" as const} : {}), headers, cache: "no-store" });
  } catch (err) {
    const cached = shouldCache ? readCache<T>(cacheKey) : null;
    if (cached && Date.now() - cached.timestamp <= CACHE_TTL_MS) return cached.value;
    throw err;
  }

  if (res.status === 401 || res.status === 403) {
    if (isPublicViewer) throw new Error("공개 조회가 제공되지 않는 자료입니다.");
    if (get(tokenStore) === token) {
      clearToken();
      if (!window.location.hash.startsWith("#/auth")) redirectToAuth();
    }
    throw new Error("Unauthorized");
  }
  if (isPublicViewer && !res.ok) throw new Error("공개 자료를 조회하지 못했습니다.");
  if (!res.ok) throw new Error((await res.text()) || `Request failed: ${res.status}`);
  if (res.status === 204) return {} as T;
  const data = (await res.json()) as T;
  if (shouldCache) writeCache(cacheKey, data);
  return data;
};

const getJson = <T>(path: string) => request<T>(path);

const postJson = <T, U>(path: string, body?: U) =>
  request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });

const deleteJson = <T>(path: string) =>
  request<T>(path, {
    method: "DELETE",
  });

export { BASE_URL, getJson, postJson, deleteJson, redirectToAuth };
