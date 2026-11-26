<script context="module" lang="ts">
  let nextId = 0;
</script>

<script lang="ts">
  import type { Issues } from "../lib/researchEvidence";
  import WorkspaceIcon from "./WorkspaceIcon.svelte";

  export let title: string;
  export let items: Issues["items"];
  export let known = true;

  const listId = "source-list-" + ++nextId;
  let expanded = false;
  $: count = known ? items.length + "건" : "확인 불가";
</script>

<h4 class="source-heading">
  {#if items.length > 1}
    <button class="source-row source-toggle" type="button" aria-expanded={expanded}
      aria-controls={listId} on:click={() => expanded = !expanded}>
      <span>{title}</span>
      <span class="count">{count}</span>
      <span class="chevron"><WorkspaceIcon name="chevron" size={20} /></span>
    </button>
  {:else}
    <span class="source-row"><span>{title}</span><span class="count">{count}</span></span>
  {/if}
</h4>
<slot name="notice" />
<div id={listId}>
  {#each expanded ? items : items.slice(0, 1) as item}
    <slot {item} />
  {/each}
</div>

<style>
  .source-heading {
    margin: 0;
    border-block-start: 1px solid var(--fl-line);
    color: var(--fl-ink);
    font-size: 0.94rem;
    font-weight: 650;
    line-height: 1.45;
  }
  .source-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto 20px;
    align-items: center;
    gap: 0.5rem;
    inline-size: 100%;
    min-block-size: 44px;
    padding: 0.35rem 0;
    box-sizing: border-box;
    text-align: start;
    overflow-wrap: anywhere;
  }
  .count {
    color: var(--fl-muted);
    font-size: 0.81rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .source-toggle {
    appearance: none;
    background: transparent;
    border: 0;
    border-radius: 0;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .chevron {
    display: inline-flex;
    color: var(--fl-accent);
    transform: rotate(90deg);
  }
  .source-toggle[aria-expanded="true"] .chevron { transform: rotate(-90deg); }
  .source-toggle:focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: 2px;
  }
  @media (hover: hover) {
    .source-toggle:hover { color: var(--fl-accent); }
  }
  @media (prefers-reduced-motion: no-preference) {
    .chevron { transition: transform 160ms ease-out; }
  }
</style>
