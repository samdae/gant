import { writable } from "svelte/store";

export const pendingReads = writable<HTMLElement[]>([]);

export function trackPending(node: HTMLElement) {
  pendingReads.update(nodes => [...nodes, node]);
  return { destroy: () => pendingReads.update(nodes => nodes.filter(item => item !== node)) };
}
