<script lang="ts">
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import DecisionBadge from "../components/DecisionBadge.svelte";
  import ReportRounds from "../components/ReportRounds.svelte";
  import ForecastReportList from "../components/ForecastReportList.svelte";
  import { isForecastLab } from "../lib/workspace";
  import { onMount } from "svelte";
  import { fetchReportTickers } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { instrumentName, tickerNames } from "../stores/tickerNames";
  import { currencyFilter, matchesCurrency } from "../stores/currency";
  import AnalysisTabs from "../components/AnalysisTabs.svelte";

  type TickerSummary = {
    ticker: string;
    display_name?: string;
    report_count: number;
    latest_at: string;
    latest_cycle?: number;
    last_decision: string;
    stored_decision_position?: string | null; decision_position?: string;
    portfolio_action?: string;
    portfolio_shares?: number;
    trade_action?: string;
    trade_shares?: number;
  };

  let tickers: TickerSummary[] = [];
  let query = "";
  let kind: "all" | "forecast" | "trade" = "all";
  let roundsTicker = "";
  const kinds = [{value:"all",label:"전체"}, {value:"forecast",label:"확률 예측"}, {value:"trade",label:"매매 분석"}] as const;
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

  $: filteredTickers = tickers.filter((t) => matchesCurrency(t.ticker, $currencyFilter));
  $: normalizedQuery = query.trim().toLowerCase();
  $: published = filteredTickers.filter((t) => t.report_count > 0).sort((a,b) => Date.parse(b.latest_at) - Date.parse(a.latest_at));
  $: visibleTickers = published.filter((t) =>
    !normalizedQuery || t.ticker.toLowerCase().includes(normalizedQuery)
    || instrumentName(t.ticker, $tickerNames, t.display_name).toLowerCase().includes(normalizedQuery));
</script>

<section class="page" id="page-reports">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? "분석 리포트" : "AI분석"}</h2>
    </div>
    {#if !isForecastLab}<AnalysisTabs />{/if}

    {#if isForecastLab}
      <div class="report-filter">
        <div class="report-kind" aria-label="리포트 유형">
          {#each kinds as option}
            <button aria-pressed={kind === option.value} on:click={() => kind = option.value}>{option.label}</button>
          {/each}
        </div>
        <label class="desk-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg>
            <input type="search" bind:value={query} aria-label="티커 또는 종목명 검색" placeholder="티커 또는 종목명 검색" />
          </label></div>
      {#if kind !== "trade"}<ForecastReportList {query} />{/if}
      {#if kind !== "forecast"}
      <section class="desk-panel report-directory" aria-label="종목별 리포트">
        <header class="desk-toolbar">
          <div class="desk-heading"><h3>매매 분석 리포트</h3>{#if !loading && !error}<span>{published.length}종목</span>{/if}</div>

        </header>
        {#if loading || error || !visibleTickers.length}
          <div class="desk-state" role="status">{loading ? "리포트를 불러오는 중입니다." : error || (query ? "검색 결과가 없습니다." : "발행된 분석 리포트가 없습니다.")}</div>
        {:else}
          <div class="desk-report-row desk-report-head" aria-hidden="true"><span>종목</span><span>최근 판단</span><span>리포트 수</span><span>최근 발행</span><span></span></div>
          {#each visibleTickers as item}
            {@const action = (item.stored_decision_position === undefined ? item.decision_position : item.stored_decision_position) || ""}
            <a href={`#/reports/${encodeURIComponent(item.ticker.toLowerCase())}`} class="desk-report-row">
              <span class="desk-instrument"><InstrumentLabel ticker={item.ticker} name={item.display_name} /></span>
              <span class="desk-report-decision"><span class="mobile-report-label">최근 판단</span><DecisionBadge value={action} /></span>
              <span class="report-metadata">
                <span class="desk-report-count"><span class="mobile-report-label">리포트 </span>{item.report_count}건</span>
                <time datetime={item.latest_at}><span class="mobile-report-label">최근 발행 </span>{formatDateTime(item.latest_at)}</time>
              </span>
              <span aria-hidden="true" class="desk-arrow">›</span>
            </a>
            <div class="round-picker">
              <button aria-expanded={roundsTicker === item.ticker} on:click={() => roundsTicker = roundsTicker === item.ticker ? "" : item.ticker}>
                {roundsTicker === item.ticker ? "회차 목록 닫기" : "회차별 조회"}
              </button>
            </div>
            {#if roundsTicker === item.ticker}<ReportRounds ticker={item.ticker} />{/if}
          {/each}
        {/if}
      </section>
      {/if}
    {:else}
    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if filteredTickers.length === 0}
      <div class="card" style="padding:16px">AI분석이 없습니다.</div>
    {:else}
      <div class="report-legend">
        <span class="legend-item"><span class="legend-swatch legend-buy"></span>매수</span>
        <span class="legend-item"><span class="legend-swatch legend-sell"></span>매도</span>
        <span class="legend-item"><span class="legend-swatch legend-hold"></span>관망</span>
      </div>
        <div class="report-ticker-list list-grid">
          {#each filteredTickers as item}
          {@const actionRaw = item.decision_position || item.portfolio_action || item.trade_action || ""}
          {@const action = actionRaw ? normalizeDecision(actionRaw) : ""}
          <a href={`#/reports/${item.ticker.toLowerCase()}`} class="report-ticker-card list-row {action ? 'action-bar-' + action.toLowerCase() : ''}">
            <div class="report-ticker-left">
              <InstrumentLabel ticker={item.ticker} name={item.display_name} />
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
    {/if}
  </div>
</section>

<style>
  .report-filter {display:flex; justify-content:space-between; flex-wrap:wrap; align-items:end; gap:.75rem; margin:.8rem 0 1rem; border-bottom:1px solid var(--fl-line);}
  .report-kind {display:flex; align-items:stretch; gap:.2rem;}
  .report-kind button,.round-picker button {font:inherit; font-size:.86rem; color:var(--fl-muted); border:0; background:transparent; cursor:pointer; padding:.65rem .8rem;}
  .report-kind button {border-bottom:2px solid transparent;}
  .report-kind button[aria-pressed="true"] {border-color:var(--fl-accent); color:var(--fl-accent); font-weight:700;}
  .report-filter label {margin-bottom:.35rem;}
  .round-picker {display:flex; justify-content:flex-end; padding:0 .6rem .3rem;}
  .round-picker button {color:var(--fl-accent); text-decoration:underline; text-underline-offset:.2em;}
  @media(max-width:550px) { .report-filter {align-items:stretch;} .report-filter label {flex-basis:100%; margin-bottom:.6rem;} }
</style>
