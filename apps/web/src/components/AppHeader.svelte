<script lang="ts">
  import { onMount } from "svelte";
  import { link } from "svelte-spa-router";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";
  import { viewMode, type ViewMode } from "../stores/mode";
  import { fetchPortfolioConfig } from "../lib/api/endpoints";
  import SelectMenu from "./SelectMenu.svelte";
  import PortfolioActivateModal from "./PortfolioActivateModal.svelte";

  const modeOptions = [
    { value: "analysis", label: "분석" },
    { value: "portfolio", label: "포트폴리오" },
  ];
  const currencyOptions = [
    { value: "ALL", label: "ALL" },
    { value: "KRW", label: "KRW" },
    { value: "USD", label: "USD" },
  ];

  let showActivateModal = false;

  async function checkPortfolioConfig() {
    try {
      const r = await fetchPortfolioConfig() as { config?: unknown };
      if (!r.config) showActivateModal = true;
    } catch {
      showActivateModal = true;
    }
  }

  function onModeChange(val: string) {
    const m = val as ViewMode;
    if (m === "portfolio") {
      viewMode.set("portfolio");
      checkPortfolioConfig();
    } else {
      viewMode.set("analysis");
    }
  }

  function onCurrencyChange(val: string) {
    currencyFilter.set(val as CurrencyFilter);
  }

  onMount(() => {
    if ($viewMode === "portfolio") checkPortfolioConfig();
  });
</script>

<header class="app-header">
  <div class="header-left">
    <div class="header-select-wrap mode-wrap">
      <SelectMenu
        value={$viewMode}
        options={modeOptions}
        compact
        on:change={(e) => onModeChange(e.detail)}
      />
    </div>
    <div class="header-select-wrap currency-wrap">
      <SelectMenu
        value={$currencyFilter}
        options={currencyOptions}
        compact
        on:change={(e) => onCurrencyChange(e.detail)}
      />
    </div>
  </div>
  <a href="#/about" class="help-link" use:link>도움말</a>
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
    padding: 0 16px;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }
  .header-select-wrap {
    flex: 0 1 auto;
    min-width: 0;
  }
  .header-select-wrap.mode-wrap {
    max-width: 100px;
  }
  .header-select-wrap.currency-wrap {
    max-width: 68px;
  }
  .help-link {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-secondary);
    flex-shrink: 0;
    transition: color 0.15s ease;
  }
  .help-link:hover {
    color: var(--text);
  }
</style>
