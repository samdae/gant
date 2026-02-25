import { writable, derived } from "svelte/store";

export type CurrencyFilter = "ALL" | "KRW" | "USD";

const STORAGE_KEY = "gant_currency";

function getInitial(): CurrencyFilter {
  if (typeof window === "undefined") return "ALL";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "KRW" || stored === "USD") return stored;
  return "ALL";
}

export const currencyFilter = writable<CurrencyFilter>(getInitial());

currencyFilter.subscribe((v) => {
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEY, v);
  }
});

export const currencySymbol = derived(currencyFilter, ($f) => {
  if ($f === "KRW") return "₩";
  if ($f === "USD") return "$";
  return "";
});

export const showAmount = derived(currencyFilter, ($f) => $f !== "ALL");

export function tickerCurrency(ticker: string): "KRW" | "USD" {
  const upper = ticker.toUpperCase();
  if (upper.endsWith(".KS") || upper.endsWith(".KQ")) return "KRW";
  return "USD";
}

export function matchesCurrency(ticker: string, filter: CurrencyFilter): boolean {
  if (filter === "ALL") return true;
  return tickerCurrency(ticker) === filter;
}
