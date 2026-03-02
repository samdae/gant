<script lang="ts">
  import { onMount } from "svelte";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";
  import { viewMode, type ViewMode } from "../stores/mode";
  import { fetchPortfolioConfig } from "../lib/api/endpoints";
  import PortfolioActivateModal from "./PortfolioActivateModal.svelte";

  const modes: { value: ViewMode; label: string }[] = [
    { value: "analysis", label: "분석" },
    { value: "portfolio", label: "포트폴리오" },
  ];
  const currencies: CurrencyFilter[] = ["ALL", "KRW", "USD"];

  let showActivateModal = false;

  async function checkPortfolioConfig() {
    try {
      const r = await fetchPortfolioConfig() as { config?: unknown };
      if (!r.config) showActivateModal = true;
    } catch {
      showActivateModal = true;
    }
  }

  function onModeChange(val: ViewMode) {
    if (val === "portfolio") {
      viewMode.set("portfolio");
      checkPortfolioConfig();
    } else {
      viewMode.set("analysis");
    }
  }

  function onCurrencyChange(val: CurrencyFilter) {
    currencyFilter.set(val);
  }

  onMount(() => {
    if ($viewMode === "portfolio") checkPortfolioConfig();
  });
</script>

<header class="app-header">
  <div class="header-half header-left-half">
    <div class="segment-group">
      {#each modes as m}
        <button
          type="button"
          class="segment-btn"
          class:active={$viewMode === m.value}
          on:click={() => onModeChange(m.value)}
        >{m.label}</button>
      {/each}
    </div>
  </div>
  <div class="header-separator"></div>
  <div class="header-half header-right-half">
    <div class="segment-group">
      {#each currencies as c}
        <button
          type="button"
          class="segment-btn"
          class:active={$currencyFilter === c}
          on:click={() => onCurrencyChange(c)}
        >{c}</button>
      {/each}
    </div>
  </div>
</header>

{#if showActivateModal}
  <PortfolioActivateModal
    onClose={() => (showActivateModal = false)}
    onActivated={() => (showActivateModal = false)}
  />
{/if}

<style>
  .app-header {
    display: flex;
    align-items: center;
    padding: 0 16px;
  }
  .header-half {
    flex: 1;
    display: flex;
    align-items: center;
    min-width: 0;
  }
  .header-left-half {
    justify-content: flex-start;
  }
  .header-right-half {
    justify-content: flex-end;
  }
  .header-separator {
    flex-shrink: 0;
    width: 1px;
    height: 20px;
    margin: 0 12px;
    background: var(--border);
  }
  .segment-group {
    display: flex;
    gap: 4px;
  }
  .segment-btn {
    min-height: 44px;
    padding: 0 14px;
    font-size: 0.875rem;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    outline: none;
    -webkit-tap-highlight-color: transparent;
    transition: background 0.15s, color 0.15s;
  }
  .segment-btn:hover {
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.06);
  }
  .segment-btn.active {
    color: var(--text);
    background: rgba(255, 255, 255, 0.1);
  }
</style>
