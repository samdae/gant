<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import DecisionBadge from "../components/DecisionBadge.svelte";
  import ReportRounds from "../components/ReportRounds.svelte";
  import ForecastReportList from "../components/ForecastReportList.svelte";
  import { isForecastLab } from "../lib/workspace";
  import { onMount, onDestroy } from "svelte";
  import ReportPulse from "../components/ReportPulse.svelte";
  import type { PulseRow } from "../lib/reportPulse";
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
    stored_decision_position?: string | null; decision_position?: string;
    portfolio_action?: string;
    portfolio_shares?: number;
    trade_action?: string;
    trade_shares?: number;
    comparison?: PulseRow["status"];
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

  const usePulse = isForecastLab && import.meta.env.BASE_URL === "/v4/";
  let pulse: PulseRow[] = [];
  let pulseError = false;
  let request: AbortController;
  let comparisonFilter = "";

  async function loadTickers() {
    request?.abort();
    const req = new AbortController();
    request = req;
    loading = true;
    pulseError = false;
    error = "";
    try {
      if (usePulse) {
        try {
          const res = await fetch("/v4/data/report-pulse", {signal: req.signal});
          if (!res.ok) throw new Error(String(res.status));
          const data = await res.json();
          if (!Array.isArray(data.rows)) throw new Error("Invalid report comparison");
          if (req.signal.aborted) return;
          pulse = data.rows;
          tickers = pulse.map(row => ({
            ticker: row.ticker, report_count: row.report_count, latest_at: row.latest_at,
            latest_cycle: row.current?.cycle ?? undefined, stored_decision_position: row.current?.decision ?? null,
            comparison: row.status,
          }));
          return;
        } catch {
          if (req.signal.aborted) return;
          pulseError = true;
          pulse = [];
          comparisonFilter = "";
        }
      }
      const directory = await fetchReportTickers();
      if (!req.signal.aborted) tickers = directory as TickerSummary[];
    } catch (err) {
      if (!req.signal.aborted) error = formatErrorMessage(err, "리포트를 불러오지 못했습니다.");
    } finally {
      if (!req.signal.aborted) loading = false;
    }
  }
  onDestroy(() => request?.abort());

  const normalizeDecision = (value: string): string => {
    const upper = value.trim().toUpperCase();
    if (upper === "BUY" || upper === "SELL" || upper === "HOLD") return upper;
    if (value.includes("매수")) return "BUY";
    if (value.includes("매도")) return "SELL";
    if (value.includes("관망") || value.includes("보유")) return "HOLD";
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
  $: pulseMap = new Map(pulse.map(row => [row.ticker, row]));
  $: visiblePulse = visibleTickers.map(row => pulseMap.get(row.ticker)).filter((row): row is PulseRow => !!row);
  $: directoryRows = visibleTickers.filter(row => !comparisonFilter || pulseMap.get(row.ticker)?.status === comparisonFilter);
  function latestDecision(item: TickerSummary) {
    if (item.comparison === "unavailable") return "UNAVAILABLE";
    return normalizeDecision((item.stored_decision_position === undefined
      ? item.decision_position : item.stored_decision_position) || "");
  }
  const signals = [
    {key: "BUY", label: "매수"}, {key: "HOLD", label: "관망"},
    {key: "SELL", label: "매도"}, {key: "", label: "미기록"}, {key:"UNAVAILABLE", label:"조회 실패"},
  ];
  $: counts = signals.map(signal => ({
    ...signal, count: visibleTickers.filter(item => latestDecision(item) === signal.key).length,
  })).filter(signal => signal.count || ["BUY", "HOLD", "SELL"].includes(signal.key));
  const issuedFormat = new Intl.DateTimeFormat("ko-KR", {timeZone: "Asia/Seoul", month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit", hour12:false});
  function issuedTime(value: string) {
    const time = Date.parse(value);
    return Number.isFinite(time) ? issuedFormat.format(time) : "발행일 미기록";
  }
  $: totalReports = visibleTickers.reduce((sum, row) => sum + row.report_count, 0);
</script>

<section class="page" id="page-reports">
  <div class="page-container">
    {#if !isForecastLab}<div class="page-header"><h2>AI분석</h2></div><AnalysisTabs />{/if}

    {#if isForecastLab}
      <div class="report-filter">
        <h2>리포트</h2>
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
      {#if !loading && !error}
        {#if pulseError}
          <div class="comparison-error" role="status">회차별 판단 비교를 불러오지 못했습니다. <button type="button" on:click={loadTickers}>다시 조회</button></div>
        {:else if usePulse}
          <ReportPulse rows={visiblePulse} />
        {/if}
      {/if}
      <section class="desk-panel report-directory" aria-label="종목별 리포트">
        <header class="publication-header">
          <div class="directory-title"><h3>종목별 리포트</h3>
            {#if !loading && !error}<span>{visibleTickers.length}개 종목 · 발행 {totalReports.toLocaleString("ko-KR")}건</span>{/if}
          </div>
          {#if !loading && !error && visibleTickers.length}
            <div class="distribution-legend" aria-label="최근 판단 분포">
              {#each counts as signal}<span><i class={'distribution-' + signal.key.toLowerCase()}></i>{signal.label} <b>{signal.count}</b></span>{/each}
            </div>
          {/if}
        </header>
        {#if visiblePulse.length}
          <div class="comparison-filter" role="group" aria-label="회차 비교로 종목 목록 필터">
            {#each [["", "전체"], ["changed", "판단 변경"], ["unchanged", "판단 유지"]] as option}
              <button type="button" aria-pressed={comparisonFilter === option[0]} on:click={() => comparisonFilter = option[0]}>{option[1]}</button>
            {/each}
          </div>
        {/if}
        {#if loading || error || !directoryRows.length}
          <div class="desk-state" role="status">
            {#if loading}<PendingState label="분석 리포트 조회 중"/>
            {:else if error}{error} <button on:click={loadTickers}>다시 조회</button>
            {:else}{comparisonFilter ? "선택한 조건에 맞는 종목이 없습니다." : query ? "검색 결과가 없습니다." : "발행된 분석 리포트가 없습니다."}{/if}
          </div>
        {:else}
          {#each directoryRows as item (item.ticker)}
            <div class="publication">
              <a href={`#/reports/${encodeURIComponent(item.ticker.toLowerCase())}`} class="publication-link">
                <span class="publication-company"><InstrumentLabel ticker={item.ticker} name={item.display_name} /></span>
                <span class="publication-decision">
                  {#if item.comparison === "unavailable"}<small>조회 실패</small>
                  {:else}<DecisionBadge value={latestDecision(item)} />{/if}
                  {#if item.comparison === "first"}<small>첫 발행</small>{/if}
                </span>
                <time datetime={item.latest_at} title={formatDateTime(item.latest_at)}>{issuedTime(item.latest_at)}</time>
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
  .report-filter {display:flex;align-items:center;gap:12px 20px;flex-wrap:wrap;margin:0 0 clamp(15px,2vw,26px);}
  .report-filter h2 {font:720 clamp(1.65rem,2.6vw,2.5rem)/1.15 var(--fl-display);letter-spacing:-.04em;color:var(--fl-ink);margin:0 auto 0 0;}
  .report-kind {display:inline-flex;align-items:center;gap:2px;padding:2px;border-radius:999px;background:var(--fl-surface-subtle);border:1px solid var(--fl-line);}
  .report-kind button {cursor:pointer;color:var(--fl-muted);background:transparent;border:0;font:650 .89rem var(--fl-font);white-space:nowrap;}
  .report-kind button[aria-pressed="true"] {background:var(--fl-ink);color:var(--fl-on-accent);}
  :global(.gant-v4) .report-kind button[aria-pressed="true"] {background:var(--fl-selected-bg);color:var(--fl-selected-ink);box-shadow:inset 0 0 0 1px var(--fl-line);}
  .report-filter .desk-search {max-width:240px;}
  .publication-header {display:flex;align-items:center;justify-content:space-between;gap:8px 18px;flex-wrap:wrap;padding:clamp(16px,2vw,26px) clamp(14px,2.5vw,28px) 10px;}
  .directory-title {display:flex;align-items:baseline;flex-wrap:wrap;gap:5px 12px;}
  .publication-header h3 {font:700 clamp(1.1rem,1.6vw,1.4rem)/1.3 var(--fl-display);color:var(--fl-ink);letter-spacing:-.025em;margin:0;}
  .directory-title span,.distribution-legend span {color:var(--fl-muted);font-size:.79rem;white-space:nowrap;}
  .distribution-legend {display:flex;flex-wrap:wrap;gap:4px 12px;}
  .distribution-legend span {display:inline-flex;align-items:center;gap:4px;}
  .distribution-legend i {width:7px;height:7px;border-radius:50%;}
  .distribution-legend b {color:var(--fl-ink);font-weight:650;}
  .distribution-buy {background:#33836c;} .distribution-sell {background:#bd5f63;}
  .distribution-hold {background:#967335;} .distribution-,.distribution-unavailable {background:#918b90;}
  :global(.gant-v4) .distribution-buy {background:var(--fl-positive);}
  :global(.gant-v4) .distribution-sell {background:var(--fl-negative);}
  :global(.gant-v4) .distribution-hold {background:var(--fl-hold);}
  :global(.gant-v4) :is(.distribution-,.distribution-unavailable) {background:var(--fl-muted);}
  .publication-decision small {display:block;color:var(--fl-muted);font-size:.74rem;}
  .comparison-filter {display:flex;align-items:center;gap:12px;border-bottom:1px solid var(--fl-line);padding:0 clamp(14px,2.5vw,28px);}
  .comparison-filter button {font:600 .82rem var(--fl-font);border:0;border-bottom:2px solid transparent;color:var(--fl-muted);background:transparent;border-radius:0;cursor:pointer;min-height:44px;padding:0 3px;}
  .comparison-filter button[aria-pressed=true] {color:var(--fl-accent);border-color:currentColor;}
  .comparison-error {display:flex;align-items:center;gap:12px;margin:0 0 18px;color:var(--fl-muted);}
  .comparison-error button {cursor:pointer;border:0;background:transparent;color:var(--fl-accent);min-height:44px;text-decoration:underline;}
  .publication { display:flex; align-items:center; gap:clamp(10px,2vw,26px); margin:0 clamp(14px,2.5vw,28px); border-bottom:1px solid var(--fl-line); }
  .publication:last-child { border-bottom:0; }
  .publication-link { flex:1; min-width:0; display:grid; grid-template-columns:minmax(0,1fr) 76px 108px; align-items:center; gap:clamp(8px,2vw,24px); padding-block:15px; color:var(--fl-ink); text-decoration:none; }
  .publication-company { min-width:0; font-size:1.03rem; }
  .publication-link:hover .publication-company { color:var(--fl-accent); }
  .publication-link time { text-align:right; color:var(--fl-muted); font-size:.83rem; }
  .round-picker button { display:inline-flex; align-items:center; justify-content:center; gap:5px; padding:0 10px; font:630 .79rem var(--fl-font); border:0; cursor:pointer; background:var(--fl-surface-subtle); color:var(--fl-accent); white-space:nowrap; }
  .round-picker svg { width:12px; height:12px; transition:transform .18s ease; }
  .round-picker .opened { transform:rotate(180deg); }
  .desk-state button { font:inherit; color:var(--fl-accent); }
  @media(max-width:620px) {
    .report-filter {gap:9px; margin-bottom:12px;}
    .report-filter .desk-search {flex:1 1 100%;max-width:none;}
    .publication-header {gap:6px 14px;}
    .publication-link { grid-template-columns:minmax(0,1fr) auto; column-gap:8px; row-gap:4px; padding-block:11px; }
    .publication-company { grid-row:1 / span 2; }
    .publication-link time { grid-column:2; font-size:.73rem; }
    .publication-decision { justify-self:end; }
    .round-picker button { padding-inline:6px; font-size:.75rem; }
  }
  @media(prefers-reduced-motion:reduce) { .round-picker svg { transition:none; } }
</style>
