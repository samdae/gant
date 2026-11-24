import { get, writable } from "svelte/store";
import catalog from "../../../../packages/tradingagents/forecast_lab/web/instrument-names.json";
import { getJson } from "../lib/api/client";

type Names = Record<string, string>;
const defaults: Names = catalog;
const registered: Names = Object.create(null);
export const tickerNames = writable<Names>({ ...defaults });
let loaded = false;

function distinct(name: unknown, symbol: string): string {
  if (typeof name !== "string") return "";
  const value = name.trim();
  return value.toUpperCase() === symbol ? "" : value;
}

export function instrumentName(ticker: string, names: Names, supplied?: string | null): string {
  const symbol = ticker.trim().toUpperCase();
  return distinct(registered[symbol], symbol) || distinct(supplied, symbol) || distinct(names[symbol], symbol);
}

export function instrumentText(ticker: string, names: Names, supplied?: string | null): string {
  const symbol = ticker.trim().toUpperCase();
  const name = instrumentName(symbol, names, supplied);
  return name ? `${name} (${symbol})` : symbol;
}

export async function loadTickerNames(): Promise<void> {
  if (loaded) return;
  try {
    const response = await getJson("/tickers/names") as Names;
    for (const [ticker, value] of Object.entries(response)) {
      const symbol = ticker.trim().toUpperCase();
      const name = distinct(value, symbol);
      if (name && !registered[symbol]) registered[symbol] = name;
    }
    tickerNames.set({ ...defaults, ...registered });
    loaded = true;
  } catch {
    // The packaged catalog remains available offline.
  }
}

export function getTickerName(ticker: string): string {
  return instrumentName(ticker, get(tickerNames)) || ticker.trim().toUpperCase();
}

export function setTickerName(ticker: string, name: string): void {
  const symbol = ticker.trim().toUpperCase();
  const value = distinct(name, symbol);
  if (!symbol || !value) return;
  registered[symbol] = value;
  tickerNames.update((names) => ({ ...names, [symbol]: value }));
}
