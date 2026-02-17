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

<div class="select-menu" bind:this={container} on:pointerdown|stopPropagation on:click|stopPropagation>
  <button
    type="button"
    class={`select-trigger ${open ? "open" : ""}`}
    on:pointerdown|stopPropagation
    on:click|stopPropagation={toggle}
    disabled={disabled}
    aria-expanded={open}
  >
    <span class="select-label">{selectedLabel}</span>
    <svg class="select-caret" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M5 7l5 6 5-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    </svg>
  </button>

  {#if open}
    <div class="select-panel" on:pointerdown|stopPropagation on:click|stopPropagation>
      {#each options as option}
        <button
          type="button"
          class={`select-option ${option.value === value ? "active" : ""}`}
          on:pointerdown|stopPropagation
          on:click|stopPropagation={(event) => selectOption(option.value, event)}
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
