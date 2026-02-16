import { writable } from "svelte/store";

const liveTickerStore = writable<string | null>(null);

export { liveTickerStore };
