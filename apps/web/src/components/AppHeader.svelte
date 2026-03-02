<script lang="ts">
  import { onMount } from "svelte";
  import { link } from "svelte-spa-router";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";
  import { viewMode, type ViewMode } from "../stores/mode";
  import { fetchPortfolioConfig } from "../lib/api/endpoints";
  import PortfolioActivateModal from "./PortfolioActivateModal.svelte";

  const currencies: CurrencyFilter[] = ["ALL", "KRW", "USD"];
  const modes: { value: ViewMode; label: string }[] = [
    { value: "analysis", label: "분석" },
    { value: "portfolio", label: "포트폴리오" },
  ];

  const setCurrency = (c: CurrencyFilter) => { currencyFilter.set(c); };
  let showActivateModal = false;

  async function checkPortfolioConfig() {
    try {
      const r = await fetchPortfolioConfig() as { config?: unknown };
      if (!r.config) showActivateModal = true;
    } catch {
      showActivateModal = true;
    }
  }

  function onModeChange(m: ViewMode) {
    if (m === "portfolio") {
      viewMode.set("portfolio");
      checkPortfolioConfig();
    } else {
      viewMode.set("analysis");
    }
  }

  function handleModeSelect(e: Event) {
    const val = (e.currentTarget as HTMLSelectElement).value;
    onModeChange(val === "portfolio" ? "portfolio" : "analysis");
  }

  onMount(() => {
    if ($viewMode === "portfolio") checkPortfolioConfig();
  });
</script>

<header class="app-header">
  <div class="header-left">
    <select
      class="mode-select"
      value={$viewMode}
      on:change={handleModeSelect}
    >
      {#each modes as m}
        <option value={m.value}>{m.label}</option>
      {/each}
    </select>
  </div>
  <div class="header-right">
    <div class="currency-selector">
      {#each currencies as c}
        <button
          class="currency-btn"
          class:active={$currencyFilter === c}
          on:click={() => setCurrency(c)}
        >{c}</button>
      {/each}
    </div>
    <a href="#/about" class="header-link about-icon" use:link title="about">?</a>
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
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .header-left { flex: 0 0 auto; }
  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .mode-select {
    padding: 6px 10px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    color: var(--text);
    cursor: pointer;
  }
  .about-icon {
    font-size: 1rem;
    font-weight: 700;
    padding: 2px 8px;
    min-width: 28px;
    text-align: center;
  }
  .currency-selector {
    flex: 0 0 auto;
    display: flex;
    gap: 2px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
  }
  .currency-btn {
    padding: 4px 12px;
    font-size: 0.7rem;
    font-weight: 600;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    background: transparent;
    color: var(--text-dim);
    transition: all 0.15s ease;
  }
  .currency-btn:hover:not(.active) {
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.04);
  }
  .currency-btn.active {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text);
    border-color: var(--border);
  }
  .header-link {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--primary);
    transition: all 0.15s ease;
  }
  .header-link:hover {
    color: var(--primary-hover);
  }
</style>
