<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReportTickers } from "../lib/api/endpoints";
  import { formatDateTime, formatAgo, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";

  type TickerSummary = {
    ticker: string;
    report_count: number;
    latest_at: string;
    last_decision: string;
  };

  let tickers: TickerSummary[] = [];
  let loading = true;
  let error = "";

  const loadTickers = async () => {
    loading = true;
    error = "";
    try {
      tickers = (await fetchReportTickers()) as TickerSummary[];
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load report tickers.");
    } finally {
      loading = false;
    }
  };

  const extractAction = (text: string): string => {
    if (!text) return "";
    const lower = text.toLowerCase();
    if (lower.includes("buy") || lower.includes("long") || text.includes("매수")) return "BUY";
    if (lower.includes("sell") || lower.includes("short") || text.includes("매도")) return "SELL";
    if (lower.includes("hold") || text.includes("보유")) return "HOLD";
    return "";
  };

  onMount(() => {
    loadTickers();
  });
</script>

<section class="page" id="page-reports">
  <div class="page-container">
    <div class="page-header">
      <h2>Reports</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">Loading...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if tickers.length === 0}
      <div class="card" style="padding:16px">No reports yet.</div>
    {:else}
      <div class="report-legend">
        <span class="legend-item"><span class="legend-swatch legend-buy"></span>BUY</span>
        <span class="legend-item"><span class="legend-swatch legend-sell"></span>SELL</span>
        <span class="legend-item"><span class="legend-swatch legend-hold"></span>HOLD</span>
      </div>
      <div class="report-ticker-list">
        {#each tickers as item}
          {@const action = extractAction(item.last_decision)}
          <a href={`#/reports/${item.ticker.toLowerCase()}`} class="card report-ticker-card {action ? 'action-bar-' + action.toLowerCase() : ''}">
            <div class="report-ticker-left">
              <span class="ticker-badge">{item.ticker}</span>
              {#if $tickerNames[item.ticker]}
                <span class="ticker-tag">{$tickerNames[item.ticker]}</span>
              {/if}
            </div>
            <div class="report-ticker-meta">
              <span class="meta-count">{item.report_count} report{item.report_count > 1 ? 's' : ''}</span>
              <span class="meta-dot">·</span>
              <span class="meta-date">{formatAgo(item.latest_at)}</span>
              <svg class="report-ticker-chevron" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path d="M9 18l6-6-6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</section>
