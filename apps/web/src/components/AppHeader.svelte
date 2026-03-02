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

  onMount(() => {
    if ($viewMode === "portfolio") checkPortfolioConfig();
  });
</script>

<header class="app-header">
  <div class="header-left">
    <a href="#/" class="logo" use:link>Gant</a>
    <div class="mode-selector">
      {#each modes as m}
        <button
          class="mode-btn"
          class:active={$viewMode === m.value}
          on:click={() => onModeChange(m.value)}
        >{m.label}</button>
      {/each}
    </div>
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
    <a href="#/about" class="help-btn" use:link title="도움말" aria-label="도움말">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <path d="M12 17h.01"/>
      </svg>
    </a>
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
    gap: 16px;
    padding: 0 20px;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    flex: 1;
    min-width: 0;
  }
  .logo {
    font-family: var(--font-display);
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--primary);
    flex-shrink: 0;
    transition: color 0.15s ease;
  }
  .logo:hover {
    color: var(--primary-hover);
  }
  .mode-selector {
    display: flex;
    gap: 2px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
  }
  .mode-btn {
    padding: 5px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    background: transparent;
    color: var(--text-dim);
    transition: all 0.15s ease;
  }
  .mode-btn:hover:not(.active) {
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.04);
  }
  .mode-btn.active {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  }
  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }
  .currency-selector {
    display: flex;
    gap: 2px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
  }
  .currency-btn {
    padding: 5px 12px;
    font-size: 0.72rem;
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
    background: var(--primary-bg);
    color: var(--primary);
    border-color: var(--primary-border);
    box-shadow: 0 0 0 1px var(--primary-border);
  }
  .help-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    color: var(--text-dim);
    transition: all 0.15s ease;
  }
  .help-btn:hover {
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.06);
  }
</style>
