<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount } from "svelte";

  type Option = {
    value: string;
    label: string;
  };

  export let value = "";
  export let options: Option[] = [];
  export let placeholder = "선택";
  export let disabled = false;
  export let compact = false;
  export let minimal = false;

  const dispatch = createEventDispatcher<{ change: string }>();
  let open = false;
  let container: HTMLDivElement;

  const toggle = () => {
    if (disabled) return;
    open = !open;
  };

  const selectOption = (nextValue: string, event?: MouseEvent) => {
    event?.stopPropagation();
    if (disabled) return;
    value = nextValue;
    open = false;
    dispatch("change", nextValue);
  };

  const handleClickOutside = (event: PointerEvent) => {
    if (!container?.contains(event.target as Node)) {
      open = false;
    }
  };

  onMount(() => {
    window.addEventListener("pointerdown", handleClickOutside);
  });

  onDestroy(() => {
    window.removeEventListener("pointerdown", handleClickOutside);
  });

  $: selectedLabel = options.find((item) => item.value === value)?.label ?? placeholder;
</script>

<div class="select-menu" class:compact class:minimal bind:this={container}>
  <button
    type="button"
    class={`select-trigger ${open ? "open" : ""}`}
    on:click={toggle}
    disabled={disabled}
    aria-expanded={open}
  >
    <span class="select-label">{selectedLabel}</span>
    <svg class="select-caret" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5 7l5 6 5-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>

  {#if open}
    <div class="select-panel">
      {#each options as option}
        <button
          type="button"
          class={`select-option ${option.value === value ? "active" : ""}`}
          on:pointerdown|preventDefault|stopPropagation={(event) => selectOption(option.value, event)}
        >
          <span>{option.label}</span>
          {#if option.value === value}
            <svg class="select-check" viewBox="0 0 20 20" aria-hidden="true">
              <path d="M4 10l4 4 8-8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .select-menu.compact {
    width: auto;
    min-width: 0;
  }
  .select-menu.compact :global(.select-trigger) {
    padding: 6px 10px 6px 12px;
    font-size: 0.8125rem;
    font-weight: 600;
  }
  .select-menu.compact :global(.select-caret) {
    width: 14px;
    height: 14px;
    margin-left: 4px;
  }
  .select-menu.compact :global(.select-panel) {
    padding: 4px;
  }
  .select-menu.compact :global(.select-option) {
    padding: 6px 10px;
    font-size: 0.8125rem;
  }

  /* minimal: 셀렉트박스처럼 보이지 않음, 터치 타겟 44px, 포커스 앱 테마 */
  .select-menu.minimal {
    min-width: 72px;
  }
  .select-menu.minimal :global(.select-trigger) {
    min-height: 44px;
    padding: 0 12px;
    background: transparent;
    border: none;
    border-radius: 8px;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text);
    outline: none;
    -webkit-tap-highlight-color: transparent;
  }
  .select-menu.minimal :global(.select-trigger:hover) {
    background: rgba(255, 255, 255, 0.06);
  }
  .select-menu.minimal :global(.select-trigger:focus) {
    outline: none;
  }
  .select-menu.minimal :global(.select-trigger.open) {
    background: rgba(255, 255, 255, 0.08);
    border: none;
    box-shadow: 0 0 0 2px var(--primary-border);
  }
  .select-menu.minimal :global(.select-caret) {
    width: 12px;
    height: 12px;
    margin-left: 6px;
    opacity: 0.6;
  }
  .select-menu.minimal :global(.select-panel) {
    top: calc(100% + 4px);
    left: 0;
    background: var(--bg-header);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow-md);
    padding: 6px;
  }
  .select-menu.minimal :global(.select-option) {
    min-height: 40px;
    padding: 8px 12px;
    font-size: 0.875rem;
  }
</style>
