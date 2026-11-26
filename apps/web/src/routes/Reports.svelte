<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import DecisionBadge from "../components/DecisionBadge.svelte";
  import ReportRounds from "../components/ReportRounds.svelte";
  import ForecastReportList from "../components/ForecastReportList.svelte";
  import { isForecastLab } from "../lib/workspace";
  import { onMount } from "svelte";
  import { querystring } from "svelte-spa-router";
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
  $: kind = isForecastLab && new URLSearchParams($querystring).get("tab") === "forecast" ? "forecast" : "trade";
  let roundsTicker = "";
  const kinds = [
    { value: "trade", label: "분석 리포트", hash: "#/reports" },
    { value: "forecast", label: "확률 예측", hash: "#/reports?tab=forecast" },
  ] as const;
  let mounted = false;
  let requestedTickers = false;
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
    mounted = true;
  });
  $: if (mounted && kind === "trade" && !requestedTickers) {
    requestedTickers = true;
    loadTickers();
  }

  $: filteredTickers = tickers.filter((t) => matchesCurrency(t.ticker, $currencyFilter));
  $: normalizedQuery = query.trim().toLowerCase();
  $: published = filteredTickers.filter((t) => t.report_count > 0).sort((a,b) => Date.parse(b.latest_at) - Date.parse(a.latest_at));
  $: visibleTickers = published.filter((t) =>
    !normalizedQuery || t.ticker.toLowerCase().includes(normalizedQuery)
    || instrumentName(t.ticker, $tickerNames, t.display_name).toLowerCase().includes(normalizedQuery));
  function latestDecision(item: TickerSummary) {
    return normalizeDecision((item.stored_decision_position === undefined
      ? item.decision_position : item.stored_decision_position) || "");
  }
  const signals = [
    {key: "BUY", label: "매수"}, {key: "HOLD", label: "관망"},
    {key: "SELL", label: "매도"}, {key: "", label: "미기록"},
  ];
  $: counts = signals.map(signal => ({
    ...signal, count: visibleTickers.filter(item => latestDecision(item) === signal.key).length,
  })).filter(signal => signal.key || signal.count);
  const dayFormat = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric" });
  const timeFormat = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hour12: false });
  function issuedTime(value: string) {
    const dt = new Date(value);
    return Number.isNaN(dt.valueOf()) ? {day: "발행일 미기록", time: "미기록"} : {day: dayFormat.format(dt), time: timeFormat.format(dt)};
  }
  $: totalReports = visibleTickers.reduce((sum, row) => sum + row.report_count, 0);
</script>

<section class="page" id="page-reports">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? "리포트" : "AI분석"}</h2>
    </div>
    {#if !isForecastLab}<AnalysisTabs />{/if}

    {#if isForecastLab}
      <div class="report-filter">
        <div class="report-kind" role="group" aria-label="리포트 유형">
          {#each kinds as option}
            <button type="button" aria-pressed={kind === option.value} on:click={() => window.location.hash = option.hash}>{option.label}</button>
          {/each}
        </div>
        <label class="desk-search">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg>
            <input type="search" bind:value={query} aria-label="티커 또는 종목명 검색" placeholder="회사명 또는 티커 검색" />
          </label></div>
      {#if kind === "forecast"}
      <ForecastReportList {query} />
      {:else}
      <section class="desk-panel report-directory" aria-label="종목별 리포트">
        <header class="publication-header">
          <div>
            <h3>매매 분석 리포트</h3>
            {#if !loading && !error}<p>{visibleTickers.length}개 종목 <span aria-hidden="true">·</span> 발행 {totalReports.toLocaleString("ko-KR")}건</p>{/if}
          </div>
          {#if !loading && !error && visibleTickers.length}
            <figure class="signal-distribution" aria-label="종목별 최근 판단 분포">
              <figcaption>최근 판단 분포</figcaption>
              <div class="distribution-track" aria-hidden="true">
                {#each counts as signal}
                  {#if signal.count}<i class={'distribution-' + signal.key.toLowerCase()} style:flex-grow={signal.count}></i>{/if}
                {/each}
              </div>
              <div class="distribution-legend">
                {#each counts as signal}<span><i class={'distribution-' + signal.key.toLowerCase()}></i>{signal.label} <b>{signal.count}</b></span>{/each}
              </div>
            </figure>
          {/if}
        </header>
        {#if loading || error || !visibleTickers.length}
          <div class="desk-state" role="status">
            {#if loading}<PendingState label="분석 리포트 조회 중"/>
            {:else if error}{error} <button on:click={loadTickers}>다시 조회</button>
            {:else}{query ? "검색 결과가 없습니다." : "발행된 분석 리포트가 없습니다."}{/if}
          </div>
        {:else}
          {#each visibleTickers as item, index (item.ticker)}
            {@const issued = issuedTime(item.latest_at)}
            {#if index === 0 || issued.day !== issuedTime(visibleTickers[index - 1].latest_at).day}
              <h4 class="edition"><span>{issued.day}</span><span>발행 · 한국시간</span></h4>
            {/if}
            <div class="publication">
              <a href={`#/reports/${encodeURIComponent(item.ticker.toLowerCase())}`} class="publication-link">
                <span class="publication-company"><InstrumentLabel ticker={item.ticker} name={item.display_name} /></span>
                <span class="publication-decision"><DecisionBadge value={latestDecision(item)} /></span>
                <time datetime={item.latest_at} title={formatDateTime(item.latest_at)}>{issued.time}</time>
              </a>
              <div class="round-picker">
                <button type="button" aria-expanded={roundsTicker === item.ticker} aria-label={item.ticker + " 회차별 조회"}
                  on:click={() => roundsTicker = roundsTicker === item.ticker ? "" : item.ticker}>
                  <span>회차 {item.report_count}건</span>
                  <svg class:opened={roundsTicker === item.ticker} viewBox="0 0 12 12" fill="none" aria-hidden="true"><path d="m3 4.8 3 3 3-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
                </button>
              </div>
            </div>
            {#if roundsTicker === item.ticker}<ReportRounds ticker={item.ticker} />{/if}
          {/each}
        {/if}
      </section>
      {/if}
    {:else}
    {#if loading}
      <div class="card" style="padding:16px"><PendingState label="분석 리포트 조회 중"/></div>
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
  .report-filter { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px 22px; margin:8px 0 22px; }
  .report-kind { display:inline-flex; align-items:center; gap:2px; padding:3px; border-radius:999px; background:var(--fl-glass, #f1f6f2); border:1px solid var(--fl-glass-edge, #b7cdc5); }
  .report-kind button { cursor:pointer; color:var(--fl-muted); background:transparent; border:0; font:650 .89rem var(--fl-font); padding:0 18px; }
  .report-kind button[aria-pressed="true"] { background:var(--fl-accent); color:var(--fl-on-accent); }
  .publication-header { display:grid; grid-template-columns:1fr minmax(210px,.55fr); align-items:center; gap:24px; padding:clamp(19px,3.2vw,38px); }
  .publication-header h3 { color:var(--fl-ink); font:720 clamp(1.35rem,2.3vw,2rem)/1.22 var(--fl-display); letter-spacing:-.035em; margin:0; }
  .publication-header p { margin:9px 0 0; color:var(--fl-muted); font-size:.86rem; }
  .publication-header p span { padding:0 4px; }
  .signal-distribution { margin:0; min-width:0; }
  .signal-distribution figcaption { color:var(--fl-ink); font-weight:680; font-size:.8rem; margin-bottom:8px; }
  .distribution-track { display:flex; gap:2px; height:7px; overflow:hidden; border-radius:6px; }
  .distribution-track i { flex-basis:0; }
  .distribution-legend { display:flex; flex-wrap:wrap; gap:4px 12px; margin-top:7px; }
  .distribution-legend span { display:inline-flex; align-items:center; gap:4px; color:var(--fl-muted); font-size:.76rem; white-space:nowrap; }
  .distribution-legend i { width:6px; height:6px; border-radius:50%; margin-right:1px; }
  .distribution-legend b { color:var(--fl-ink); font-weight:650; }
  .distribution-buy { background:var(--fl-accent); } .distribution-sell { background:var(--fl-down); }
  .distribution-hold { background:#71837d; } .distribution- { background:#acbbb4; }
  .edition { margin:0; padding:10px clamp(14px,2.5vw,28px); display:flex; justify-content:space-between; align-items:baseline; color:var(--fl-muted); background:var(--fl-surface-subtle); font-size:.78rem; font-weight:600; }
  .edition span + span { font-size:.74rem; font-weight:450; }
  .publication { display:flex; align-items:center; gap:clamp(10px,2vw,26px); margin:0 clamp(14px,2.5vw,28px); border-bottom:1px solid var(--fl-line); }
  .publication:last-child { border-bottom:0; }
  .publication-link { flex:1; min-width:0; display:grid; grid-template-columns:minmax(0,1fr) 76px 56px; align-items:center; gap:clamp(8px,2vw,24px); padding-block:15px; color:var(--fl-ink); text-decoration:none; }
  .publication-company { min-width:0; font-size:1.03rem; }
  .publication-link:hover .publication-company { color:var(--fl-accent); }
  .publication-link time { text-align:right; color:var(--fl-muted); font-size:.83rem; }
  .round-picker button { display:inline-flex; align-items:center; justify-content:center; gap:5px; padding:0 10px; font:630 .79rem var(--fl-font); border:0; cursor:pointer; background:var(--fl-surface-subtle); color:var(--fl-accent); white-space:nowrap; }
  .round-picker svg { width:12px; height:12px; transition:transform .18s ease; }
  .round-picker .opened { transform:rotate(180deg); }
  .desk-state button { font:inherit; color:var(--fl-accent); }
  @media(max-width:620px) {
    .report-filter { gap:10px; margin-bottom:16px; }
    .report-filter label { flex:1 1 180px; }
    .publication-header { grid-template-columns:minmax(0,1fr); gap:18px; }
    .publication-link { grid-template-columns:minmax(0,1fr) auto; column-gap:8px; row-gap:4px; padding-block:11px; }
    .publication-company { grid-row:1 / span 2; }
    .publication-link time { grid-column:2; font-size:.73rem; }
    .publication-decision { justify-self:end; }
    .round-picker button { padding-inline:6px; font-size:.75rem; }
  }
  @media(prefers-reduced-motion:reduce) { .round-picker svg { transition:none; } }
</style>
