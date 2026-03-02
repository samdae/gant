<script lang="ts">
  import { onMount } from "svelte";
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
        minimal
        on:change={(e) => onModeChange(e.detail)}
      />
    </div>
  </div>
  <div class="header-right">
    <div class="header-select-wrap currency-wrap">
      <SelectMenu
        value={$currencyFilter}
        options={currencyOptions}
        minimal
        on:change={(e) => onCurrencyChange(e.detail)}
      />
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
    justify-content: space-between;
    gap: 12px;
    padding: 0 16px;
  }
  .header-left {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
  }
  .header-right {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
  .header-select-wrap {
    flex: 0 1 auto;
    min-width: 0;
  }
  .header-select-wrap.mode-wrap,
  .header-select-wrap.currency-wrap {
    min-width: 72px;
  }
</style>
