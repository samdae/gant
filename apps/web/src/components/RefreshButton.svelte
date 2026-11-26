<script lang="ts">
  export let label: string;
  export let busy = false;
</script>

<button class="refresh" type="button" aria-label={label} title={label}
  disabled={busy} aria-busy={busy} on:click>
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M20 10a8 8 0 0 0-13.4-4L4 8.5M4 4v4.5h4.5M4 14a8 8 0 0 0 13.4 4l2.6-2.5M20 20v-4.5h-4.5" />
  </svg>
</button>

<style>
  .refresh {
    --fl-control-padding-inline: 0;
    display: inline-flex;
    flex: none;
    align-items: center;
    justify-content: center;
    inline-size: var(--fl-control-height, 44px);
    block-size: var(--fl-control-height, 44px);
    margin: 0;
    padding: 0;
    border: 1px solid var(--fl-line);
    border-radius: 50%;
    background: var(--fl-surface);
    color: var(--fl-muted);
    cursor: pointer;
  }
  .refresh svg { flex: none; }
  .refresh:focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: -2px;
  }
  @media (hover: hover) {
    .refresh:hover:enabled { background: var(--fl-surface-subtle); color: var(--fl-ink); }
  }
  .refresh:active:enabled { color: var(--fl-accent); }
  .refresh:disabled { cursor: wait; }
  @media (prefers-reduced-motion: no-preference) {
    .refresh[aria-busy="true"] svg { animation: turn 1s linear infinite; }
    @keyframes turn { to { transform: rotate(360deg); } }
  }
</style>
