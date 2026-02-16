import { get } from "svelte/store";
import { clearToken, tokenStore } from "../../stores/auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
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

  return res.json() as Promise<T>;
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
