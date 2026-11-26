import { writable } from "svelte/store";
import { readPreference, writePreference } from "./preferences";

export type ViewMode = "analysis" | "portfolio";

const STORAGE_KEY = "gant_view_mode";

function getInitial(): ViewMode {
  const stored = readPreference(STORAGE_KEY);
  if (stored === "portfolio") return "portfolio";
  return "analysis";
}

export const viewMode = writable<ViewMode>(getInitial());

viewMode.subscribe((v) => writePreference(STORAGE_KEY, v));

/** 포트폴리오 활성화 후 새로고침 트리거 */
export const portfolioRefreshTrigger = writable<number>(0);
