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
    decision_position?: string;
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

  const normalizeDecision = (value: string): string => {
    const upper = value.trim().toUpperCase();
    if (upper === "BUY" || upper === "SELL" || upper === "HOLD") return upper;
    if (value.includes("매수")) return "BUY";
    if (value.includes("매도")) return "SELL";
    if (value.includes("보유")) return "HOLD";
    return "";
  };

  const extractAction = (text: string): string => {
    if (!text) return "";

    const cleaned = text.replace(/\*\*/g, "");
    const lines = cleaned.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const decisionLine = lines.find((line) => /결정|decision/i.test(line));

    if (decisionLine) {
      const match = decisionLine.match(/(?:결정|decision)[:：]\s*(BUY|SELL|HOLD|매수|매도|보유)/i);
      if (match?.[1]) {
        const normalized = normalizeDecision(match[1]);
        if (normalized) return normalized;
      }

      const parts = decisionLine.split(/[:：]/);
      if (parts.length > 1) {
        const after = parts.slice(1).join(":").trim();
        const token = after.split(/\s+/)[0] || "";
        const normalized = normalizeDecision(token);
        if (normalized) return normalized;
      }
    }

    if (cleaned.includes("보유")) return "HOLD";
    if (cleaned.includes("매도")) return "SELL";
    if (cleaned.includes("매수")) return "BUY";

    const lower = cleaned.toLowerCase();
    if (/(^|\b)hold(\b|$)/.test(lower)) return "HOLD";
    if (/(^|\b)sell(\b|$)/.test(lower) || /(^|\b)short(\b|$)/.test(lower)) return "SELL";
    if (/(^|\b)buy(\b|$)/.test(lower) || /(^|\b)long(\b|$)/.test(lower)) return "BUY";

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
          {@const action = item.decision_position ? normalizeDecision(item.decision_position) : extractAction(item.last_decision)}
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
