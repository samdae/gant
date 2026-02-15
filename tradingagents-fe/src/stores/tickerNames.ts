import { writable, get } from "svelte/store";
import { getJson } from "../lib/api/client";

/** Ticker display name map: { "005930.KS": "삼성전자", "NVDA": "NVIDIA" } */
export const tickerNames = writable<Record<string, string>>({});

let loaded = false;

/** Fetch ticker names from API. Call once on app init. */
export async function loadTickerNames(): Promise<void> {
    if (loaded) return;
    try {
        const names = (await getJson("/tickers/names")) as Record<string, string>;
        tickerNames.set(names);
        loaded = true;
    } catch {
        // Silently fail — fallback is ticker symbol itself
    }
}

/** Get display name for a ticker, falling back to ticker symbol. */
export function getTickerName(ticker: string): string {
    const names = get(tickerNames);
    return names[ticker] || ticker;
}

/** Add a name to the local store (for immediate UI without re-fetch). */
export function setTickerName(ticker: string, name: string): void {
    tickerNames.update((m) => ({ ...m, [ticker]: name }));
}
