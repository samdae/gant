<script lang="ts">
  import { isForecastLab } from "../lib/workspace";
  import { onMount } from "svelte";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";
  import { viewMode, type ViewMode } from "../stores/mode";
  import { fetchPortfolioConfig } from "../lib/api/endpoints";
  import PortfolioActivateModal from "./PortfolioActivateModal.svelte";
  import SelectMenu from "./SelectMenu.svelte";

  const modeOptions: { value: ViewMode; label: string }[] = [
    { value: "analysis", label: "분석" },
    { value: "portfolio", label: "포트폴리오" },
  ];

  const currencyOptions: { value: CurrencyFilter; label: string }[] = [
    { value: "ALL", label: "ALL" },
    { value: "KRW", label: "KRW" },
    { value: "USD", label: "USD" },
  ];

  let showActivateModal = false;

  async function checkPortfolioConfig() {
    if (isForecastLab) return;
    try {
      const r = (await fetchPortfolioConfig()) as { config?: unknown };
      showActivateModal = $viewMode === "portfolio" && !r.config;
    } catch {
      showActivateModal = false;
    }
  }

  function onModeChange(next: string) {
    const val = next as ViewMode;
    if (val === "portfolio") {
      viewMode.set("portfolio");
      if (isForecastLab && window.location.hash === "#/") window.location.hash = "#/portfolio";
      checkPortfolioConfig();
      return;
    }
    showActivateModal = false;
    viewMode.set("analysis");
    if (isForecastLab && window.location.hash === "#/portfolio") window.location.hash = "#/";
  }

  function onCurrencyChange(next: string) {
    currencyFilter.set(next as CurrencyFilter);
  }

  onMount(() => {
    if ($viewMode === "portfolio") checkPortfolioConfig();
  });
</script>

{#if isForecastLab}
  <div class="work-controls" aria-label="콘솔 보기 설정">
    <label><span>모드</span><select aria-label="콘솔 모드" value={$viewMode} on:change={(e) => onModeChange(e.currentTarget.value)}>
      {#each modeOptions as option}<option value={option.value}>{option.label}</option>{/each}
    </select></label>
    <label><span>통화</span><select aria-label="표시 통화" value={$currencyFilter} on:change={(e) => onCurrencyChange(e.currentTarget.value)}>
      {#each currencyOptions as option}<option value={option.value}>{option.label}</option>{/each}
    </select></label>
  </div>
{:else}
<header class="app-header control-header">
  <div class="control-shell">
    <section class="control-block">
      <span class="control-label">모드</span>
      <SelectMenu
        minimal={true}
        compact={true}
        value={$viewMode}
        options={modeOptions}
        on:change={(e) => onModeChange(e.detail)}
      />
    </section>

    <div class="control-divider" aria-hidden="true"></div>

    <section class="control-block align-right">
      <span class="control-label">통화</span>
      <SelectMenu
        minimal={true}
        compact={true}
        panelAlign="end"
        value={$currencyFilter}
        options={currencyOptions}
        on:change={(e) => onCurrencyChange(e.detail)}
      />
    </section>
  </div>
</header>
{/if}


{#if showActivateModal}
  <PortfolioActivateModal
    onClose={() => (showActivateModal = false)}
    onActivated={() => (showActivateModal = false)}
  />
{/if}

<style>
  .work-controls { display:flex; align-items:center; gap:12px; }
  .work-controls label { display:flex; gap:6px; align-items:center; color:var(--fl-muted); font-size:12px; }
  .work-controls select { max-width:110px; color:var(--fl-ink); background:var(--fl-surface); border:1px solid var(--fl-line); border-radius:8px; padding:6px; min-height:32px; font:600 12px var(--fl-font); }
  .work-controls select:focus-visible { outline:2px solid var(--fl-accent); outline-offset:2px; }
  @media(max-width:630px) { .work-controls { gap:4px; } .work-controls label span { display:none; } }

  .control-header {
    padding: 8px 16px;
    height: 60px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-header);
  }

  .control-shell {
    width: 100%;
    max-width: 480px;
    margin: 0 auto;
    height: 42px;
    padding: 4px 6px;
    display: flex;
    align-items: center;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: rgba(19, 22, 29, 0.92);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    overflow: visible;
  }

  .control-block {
    min-width: 0;
    flex: 1;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .align-right {
    justify-content: flex-end;
  }

  .control-label {
    flex-shrink: 0;
    padding-left: 6px;
    font-size: 0.66rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    font-weight: 700;
  }

  .control-divider {
    width: 1px;
    height: 20px;
    flex-shrink: 0;
    background: var(--border);
    opacity: 0.8;
  }

  .control-block :global(.select-menu.compact) {
    width: auto;
  }

  .control-block :global(.select-trigger) {
    min-height: 36px;
    border-radius: 10px;
    color: var(--text);
  }

  .control-block :global(.select-trigger:hover) {
    background: rgba(255, 255, 255, 0.08);
  }

  .control-block :global(.select-trigger.open) {
    background: rgba(91, 139, 255, 0.12);
    box-shadow: 0 0 0 1px rgba(91, 139, 255, 0.24);
  }

  .control-block :global(.select-label) {
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .control-block :global(.select-caret) {
    opacity: 0.75;
  }

  .control-block :global(.select-panel) {
    background: #141923;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-md);
  }

  .align-right :global(.select-panel) {
    left: auto;
    right: 0;
  }
</style>
