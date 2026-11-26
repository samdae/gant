// View preferences stay available in the Svelte stores when site storage is blocked.
export function readPreference(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writePreference(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch { /* Storage can be unavailable, full, or disabled. */ }
}
