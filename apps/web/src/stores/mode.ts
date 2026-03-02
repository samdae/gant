import { writable } from "svelte/store";

export type ViewMode = "analysis" | "portfolio";

const STORAGE_KEY = "gant_view_mode";

function getInitial(): ViewMode {
  if (typeof window === "undefined") return "analysis";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "portfolio") return "portfolio";
  return "analysis";
}

export const viewMode = writable<ViewMode>(getInitial());

viewMode.subscribe((v) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, v);
  }
});

/** 포트폴리오 활성화 후 새로고침 트리거 */
export const portfolioRefreshTrigger = writable<number>(0);
