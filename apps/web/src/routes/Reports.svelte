<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReportTickers } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";

  type TickerSummary = {
    ticker: string;
    report_count: number;
    latest_at: string;
    latest_cycle?: number;
    last_decision: string;
    decision_position?: string;
    portfolio_action?: string;
    portfolio_shares?: number;
    trade_action?: string;
    trade_shares?: number;
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
      error = formatErrorMessage(err, "AI분석을 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const normalizeDecision = (value: string): string => {
    const upper = value.trim().toUpperCase();
    if (upper === "BUY" || upper === "SELL" || upper === "HOLD") return upper;
    if (value.includes("매수")) return "BUY";
    if (value.includes("매도")) return "SELL";
    if (value.includes("관망") || value.includes("보유")) return "HOLD";
    return "";
  };

  const extractAction = (text: string): string => {
    if (!text) return "";

    const cleaned = text.replace(/\*\*/g, "");
    const lines = cleaned.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const decisionLine = lines.find((line) => /결정|decision/i.test(line));

    if (decisionLine) {
      const match = decisionLine.match(/(?:결정|decision)[:：]\s*(BUY|SELL|HOLD|매수|매도|관망|보유)/i);
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

    if (cleaned.includes("관망") || cleaned.includes("보유")) return "HOLD";
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
      <h2>AI분석</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if tickers.length === 0}
      <div class="card" style="padding:16px">AI분석이 없습니다.</div>
    {:else}
      <div class="report-legend">
        <span class="legend-item"><span class="legend-swatch legend-buy"></span>매수</span>
        <span class="legend-item"><span class="legend-swatch legend-sell"></span>매도</span>
        <span class="legend-item"><span class="legend-swatch legend-hold"></span>관망</span>
      </div>
        <div class="report-ticker-list list-grid">
          {#each tickers as item}
          {@const portfolioOk = item.portfolio_action ? (item.portfolio_action === "HOLD" || (item.portfolio_shares != null && item.portfolio_shares > 0)) : false}
          {@const actionRaw = item.trade_action || (portfolioOk ? item.portfolio_action : "") || (!item.portfolio_action ? item.decision_position : "") || ""}
          {@const action = actionRaw ? normalizeDecision(actionRaw) : ""}
          <a href={`#/reports/${item.ticker.toLowerCase()}`} class="report-ticker-card list-row {action ? 'action-bar-' + action.toLowerCase() : ''}">
            <div class="report-ticker-left">
              <span class="ticker-badge">{item.ticker}</span>
              {#if $tickerNames[item.ticker]}
                <span class="ticker-tag">{$tickerNames[item.ticker]}</span>
              {/if}
            </div>
            <div class="report-ticker-meta">
              <span class="meta-date">{item.latest_cycle ? `${item.latest_cycle}회` : "-"}</span>
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
