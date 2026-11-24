import { isPublicViewer } from "../lib/workspace";
import { writable } from "svelte/store";

const STORAGE_KEY = "gant_admin_token";

const getInitialToken = () => {
  if (isPublicViewer || typeof localStorage === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
};

const tokenStore = writable<string | null>(getInitialToken());

tokenStore.subscribe((value) => {
  if (isPublicViewer || typeof localStorage === "undefined") return;
  if (value) {
    localStorage.setItem(STORAGE_KEY, value);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
});

const setToken = (value: string) => tokenStore.set(value);
const clearToken = () => tokenStore.set(null);

export { tokenStore, setToken, clearToken };
