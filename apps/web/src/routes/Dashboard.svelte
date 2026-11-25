<script lang="ts">
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import PortfolioSummary from "../components/PortfolioSummary.svelte";
  import DecisionBadge from "../components/DecisionBadge.svelte";
  import { onMount } from "svelte";
  import { location } from "svelte-spa-router";
  import { isForecastLab } from "../lib/workspace";
  import {
    fetchReportTickers,
    fetchHealth,
    fetchMetrics,
    fetchPositionsMarket,
    fetchQueue,
    fetchScheduleSummary,
    fetchPortfolioConfig,
    fetchPortfolioHoldings,
  } from "../lib/api/endpoints";
  import { formatDateTime, formatPercent, formatErrorMessage, formatAmount, formatSignedAmount } from "../lib/utils/format";
  import { currencyFilter, showAmount, matchesCurrency, tickerCurrency } from "../stores/currency";
  import { viewMode, portfolioRefreshTrigger } from "../stores/mode";

  type CurrencyPerformance = {
    incomplete_positions: number;
    unpriced_positions: number;
    total_return_pct: number | null;
    total_realized_return_pct: number;
    total_unrealized_return_pct: number | null;
    active_positions: number;
    wins: number;
    losses: number;
  };

  type Metrics = {
    by_currency: Record<string, CurrencyPerformance>;
    active_positions: number;
    closed_positions: number;
    wins: number;
    losses: number;
    analysis_accuracy_avg?: number | null;
    analysis_accuracy_count?: number;
    rag_contribution_avg?: number | null;
    rag_contribution_count?: number;
  };

  type Health = {
    uptime_seconds: number;
  };

  type PositionMarket = {
    position_id: number;
    ticker: string;
    display_name?: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  type QueueStatus = {
    running: string | null;
    pending: string[];
    total: number;
  };

  type ScheduleSummary = {
    total: number;
    done: number;
    failed: number;
    skipped: number;
    running: number;
    pending: number;
    as_of: string;
  };

  let loading = true;
  let error = "";
  let metrics: Metrics | null = null;
  let accuracyHelp: HTMLDialogElement;
  let health: Health | null = null;
  let positions: PositionMarket[] = [];
  let queue: QueueStatus = { running: null, pending: [], total: 0 };
  let scheduleSummary: ScheduleSummary | null = null;
  let todayRunsTotal: number | null = null;
  let portfolioConfig: { total_fund?: number; available_cash?: number; initial_capital?: number; base_currency?: string } | null = null;
  let portfolioHoldings: Array<{ ticker: string; display_name?: string; shares: number; current_value_base?: number; allocation_pct?: number }> = [];

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const goArchive = () => {
    window.location.hash = isForecastLab ? "#/schedules" : "#/archive";
  };

  const getTotalAmount = (pos: PositionMarket) =>
    pos.current_price !== null && pos.current_price !== undefined
      ? pos.current_price * pos.shares
      : null;

  type RecentReport = { stored_decision_position?: string | null; decision_position?: string; ticker: string; display_name?: string; report_count: number; latest_at: string };
  let reports: RecentReport[] = [];
  let reportStatus: "loading" | "ready" | "error" = "loading";
  onMount(async () => {
    if (!isForecastLab) return;
    try {
      reports = (await fetchReportTickers() as RecentReport[]).slice().sort(
        (a,b) => Date.parse(b.latest_at) - Date.parse(a.latest_at));
      reportStatus = "ready";
    } catch {
      reportStatus = "error";
    }
  });
  $: recentReports = reports.filter((r) => r.report_count > 0 && matchesCurrency(r.ticker, $currencyFilter)).slice(0, 3);

  $: if (isForecastLab && $location === "/dashboard") viewMode.set("analysis");

  let generation = 0;
  const loadData = async () => {
    const request = ++generation;
    loading = true;
    error = "";
    try {
      const base: Promise<unknown>[] = [
        fetchMetrics(),
        fetchPositionsMarket(),
        fetchQueue(),
        fetchHealth(),
        fetchScheduleSummary(),
      ];
      if ($viewMode === "portfolio") {
        base.push(fetchPortfolioConfig());
        base.push(fetchPortfolioHoldings());
      }
      const results = await Promise.all(base);
      if (request !== generation) return;
      metrics = results[0] as Metrics;
      positions = (results[1] as PositionMarket[]) || [];
      queue = (results[2] as QueueStatus) || { running: null, pending: [], total: 0 };
      health = results[3] as Health;
      scheduleSummary = results[4] as ScheduleSummary;
      if ($viewMode === "portfolio" && results[5]) {
        const pc = results[5] as { config?: { total_fund?: number; available_cash?: number; initial_capital?: number; base_currency?: string } };
        portfolioConfig = pc?.config ?? null;
        const ph = results[6] as { holdings?: Array<{ ticker: string; display_name?: string; shares: number; current_value_base?: number; allocation_pct?: number }> };
        portfolioHoldings = ph?.holdings ?? [];
      } else {
        portfolioConfig = null;
        portfolioHoldings = [];
      }
    } catch (err) {
      if (request !== generation) return;
      error = formatErrorMessage(err, "대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      if (request === generation) loading = false;
    }
  };

  $: $viewMode, $portfolioRefreshTrigger, loadData();

  $: todayRunsTotal = scheduleSummary
    ? scheduleSummary.done + scheduleSummary.failed + scheduleSummary.skipped + scheduleSummary.running
    : null;

  $: performanceRows = Object.entries(metrics?.by_currency ?? {})
    .filter(([currency]) => $currencyFilter === "ALL" || currency === $currencyFilter);
  $: counts = $currencyFilter === "ALL" ? metrics : metrics?.by_currency?.[$currencyFilter];
  $: filteredPositions = positions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));
  $: filteredPortfolioHoldings = portfolioHoldings.filter((h) => matchesCurrency(h.ticker, $currencyFilter));

  type ExposureItem = { ticker: string; value: number | null; currency: string };
  function byCurrency(items: ExposureItem[]) {
    return [...new Set(items.map(item => item.currency))].map(currency => {
      const rows = items.filter(item => item.currency === currency);
      const total = rows.every(item => item.value !== null && Number.isFinite(item.value) && item.value >= 0)
        ? rows.reduce((sum, item) => sum + (item.value ?? 0), 0) : null;
      return { currency, items: rows.sort((a,b) => (b.value ?? 0) - (a.value ?? 0)), total };
    });
  }
  $: exposure = byCurrency($viewMode === "portfolio"
    ? filteredPortfolioHoldings.map(item => ({ ticker: item.ticker, value: item.current_value_base ?? null, currency: portfolioConfig?.base_currency || "기준 통화" }))
    : filteredPositions.map(item => ({ ticker: item.ticker, value: getTotalAmount(item), currency: tickerCurrency(item.ticker) })));
  $: quietAccount = isForecastLab && $viewMode === "analysis" && !loading && !error
    && metrics && metrics.by_currency && !performanceRows.length && !filteredPositions.length
    && !metrics.analysis_accuracy_count && !metrics.rag_contribution_count
    && todayRunsTotal === 0 && !queue.running && !queue.pending.length
    && reportStatus === "ready" && !recentReports.length;
</script>

<section class="page" id="page-dashboard">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? ($viewMode === "portfolio" ? "포트폴리오 현황" : "운영 대시보드") : "홈"}</h2>
      {#if error}
        <span class="badge badge-loss">
          <span class="status-dot status-error" style="width:6px;height:6px;margin-right:4px"></span>
          오프라인
        </span>
      {:else if queue.running}
        <span class="badge badge-info">
          <span class="status-dot status-info" style="width:6px;height:6px;margin-right:4px"></span>
          실행중 · <InstrumentLabel ticker={queue.running} inline />
        </span>
      {:else}
        <span class="badge badge-info">
          <span class="status-dot status-info" style="width:6px;height:6px;margin-right:4px"></span>
          온라인 · 대기
        </span>
      {/if}
    </div>

    {#if isForecastLab && $viewMode === "portfolio"}
      <PortfolioSummary config={portfolioConfig} />
    {/if}

    {#if quietAccount}
      <section class="quiet-account">
        <header><h3>보유·거래 현황</h3><a href="#/positions">포지션 명세</a></header>
        <h4>보유 중인 모의 자산이 없습니다</h4>
        <p>선택한 통화에 체결 기록이 없어 손익률을 집계할 수 없습니다.</p>
        <div class="quiet-actions"><a href="#/research">발행된 예측 확인</a><a href="#/reports">분석 리포트</a></div>
        <dl><div><dt>오늘 분석 실행</dt><dd><a href="#/schedules">실행 없음 · 일정 보기</a></dd></div>
            <div><dt>분석 대기열</dt><dd><a href="#/live">대기 없음 · 실시간 보기</a></dd></div>
            <div><dt>AI 회고 평가</dt><dd><button on:click={() => accuracyHelp.showModal()}>표본 없음 · 채점 기준</button></dd></div></dl>
      </section>
    {:else}
    <div class:folio-overview={isForecastLab}>
    {#if isForecastLab}
      <section class="folio-trading-brief">
        <header><h3>보유 자산 구성</h3><a href="#/positions">보유 명세 →</a></header>
        {#if loading}<p>보유 내역을 조회하고 있습니다.</p>
        {:else if error}<p role="alert">{error}</p>
        {:else if exposure.length}
          {#each exposure as group}
            <div class="folio-allocation"><strong>{group.currency} · {group.items.length}종목</strong>
              {#if group.total !== null && group.total > 0}
                {#each group.items as item}
                  <a href={"#/trade/" + item.ticker.toLowerCase()}><InstrumentLabel ticker={item.ticker} inline />
                    <span class="folio-track"><i style:width={((item.value ?? 0) / group.total * 100) + "%"}></i></span>
                    <span>{((item.value ?? 0) / group.total * 100).toFixed(1)}%</span>
                  </a>
                {/each}
              {:else}<p>시세가 완비되면 평가액 비중을 표시합니다.</p>{/if}
            </div>
          {/each}
        {:else}<p class="folio-empty-head">보유 자산 없음</p><p>선택한 계좌·통화에 남아 있는 모의 포지션이 없습니다.</p>{/if}
      </section>
    {/if}
    {#if isForecastLab && !loading && !error && todayRunsTotal === 0}
      <section class="operation-line"><div><h3>오늘의 분석 실행</h3><p>기록된 실행이 없습니다.</p></div><a href="#/schedules">분석 예약 보기</a></section>
    {:else}
    <button class="card summary-banner" type="button" on:click={goArchive}>
      <div class="summary-header">
        <div>
          <div class="summary-title">{isForecastLab ? "오늘의 분석 실행" : "오늘 실행"}</div>
        </div>
        <div class="summary-total">
          {todayRunsTotal ?? "-"}
        </div>
      </div>
      {#if isForecastLab && scheduleSummary}
        <div class="desk-progress" aria-hidden="true">
          {#each [scheduleSummary.done,scheduleSummary.skipped,scheduleSummary.failed,scheduleSummary.running] as n,index}
            {#if n > 0}<span class={`run-${index}`} style={`flex:${n}`}></span>{/if}
          {/each}
        </div>
      {/if}
      <div class="summary-metrics">
        <div class="summary-item">
          <span class="summary-label">완료</span>
          <span class="summary-value text-gain">
            {scheduleSummary ? scheduleSummary.done : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">건너뜀</span>
          <span class="summary-value">
            {scheduleSummary ? scheduleSummary.skipped : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">실패</span>
          <span class="summary-value text-loss">
            {scheduleSummary ? scheduleSummary.failed : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">실행중</span>
          <span class="summary-value">
            {scheduleSummary ? scheduleSummary.running : "-"}
          </span>
        </div>
      </div>
    </button>
    {/if}

    </div>
    {#if isForecastLab && $viewMode !== "portfolio" && !loading && !error && metrics && !performanceRows.length}
      <section class="performance-note"><h3>체결 기준 손익</h3><p>선택한 통화의 체결 기록이 없습니다.</p>
        <a href="#/research">예측 연구 보기</a> · <a href="#/positions">거래 명세 보기</a></section>
    {:else if !isForecastLab || $viewMode !== "portfolio"}
    <div class="card metric-strip" style="margin-bottom:16px">
      {#if $viewMode === "portfolio"}
        <div class="metric-segment">
          <div class="metric-icon icon-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z" />
              <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </div>
          <div class="metric-label">자산</div>
          <div class="metric-value">
            {portfolioConfig?.total_fund != null
              ? (portfolioConfig.base_currency === "USD"
                ? `$${portfolioConfig.total_fund.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
                : `₩${portfolioConfig.total_fund.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`)
              : "-"}
          </div>
        </div>
        <div class="metric-segment">
          <div class="metric-icon icon-gain">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          </div>
          <div class="metric-label">가용 현금</div>
          <div class="metric-value">
            {portfolioConfig?.available_cash != null
              ? (portfolioConfig.base_currency === "USD"
                ? `$${portfolioConfig.available_cash.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
                : `₩${portfolioConfig.available_cash.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`)
              : "-"}
          </div>
        </div>
        <div class="metric-segment">
          <div class="metric-icon icon-gain">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 16l4-4 4 4 6-6" />
            </svg>
          </div>
          <div class="metric-label">총 수익률</div>
          <div class="metric-value" class:text-gain={portfolioConfig && (portfolioConfig.total_fund ?? 0) >= (portfolioConfig.initial_capital ?? 0)} class:text-loss={portfolioConfig && (portfolioConfig.total_fund ?? 0) < (portfolioConfig.initial_capital ?? 0)}>
            {portfolioConfig?.total_fund != null && portfolioConfig?.initial_capital != null && portfolioConfig.initial_capital > 0
              ? formatPercent(((portfolioConfig.total_fund - portfolioConfig.initial_capital) / portfolioConfig.initial_capital) * 100)
              : "-"}
          </div>
        </div>
      {:else}
        <div class="metric-segment">
          <div class="metric-icon icon-gain">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 16l4-4 4 4 6-6" />
            </svg>
          </div>
          <div class="metric-label">체결 기준 손익률</div>
          {#each performanceRows as [currency, perf]}
            <div class="metric-value" class:text-gain={perf.total_return_pct != null && perf.total_return_pct >= 0} class:text-loss={perf.total_return_pct != null && perf.total_return_pct < 0}>
              {currency} {perf.total_return_pct != null ? formatPercent(perf.total_return_pct) : "—"}
            </div>
            <div class="metric-sub metric-sub-grid">
              <span>실현</span><span>{formatPercent(perf.total_realized_return_pct)}</span>
              <span>미실현</span><span>{perf.total_unrealized_return_pct != null ? formatPercent(perf.total_unrealized_return_pct) : "시세 미확인"}</span>
            </div>
            {#if perf.incomplete_positions}
              <div class="metric-sub">체결 기록 불완전 {perf.incomplete_positions}건 · 확인된 수량만 반영</div>
            {/if}
          {:else}
            <div class="metric-value">—</div>
          {/each}
        </div>
        <div class="metric-segment">
          <div class="metric-icon icon-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z" />
              <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </div>
          <div class="metric-label">투자</div>
          <div class="metric-value">{metrics ? counts?.active_positions ?? 0 : "-"}</div>
          <div class="metric-sub">
            <div>승 {metrics ? counts?.wins ?? 0 : "-"}</div>
            <div>패 {metrics ? counts?.losses ?? 0 : "-"}</div>
          </div>
        </div>
      {/if}
    </div>

    {/if}

    {#if $viewMode === "analysis" && metrics}
      <div class="card metric-strip" style="margin-bottom:16px">
        <div class="metric-segment">
          <div class="metric-label accuracy-label">
            AI 회고 평가 · 분석
            <button type="button" class="help-button" aria-label="분석 점수 채점 기준 보기"
              aria-haspopup="dialog" on:click={() => accuracyHelp.showModal()}><span aria-hidden="true">?</span></button>
          </div>
          <div class="metric-value metric-value-compact">
            {metrics.analysis_accuracy_avg != null ? `${Math.round(metrics.analysis_accuracy_avg)}점` : "-"}
            {metrics.analysis_accuracy_count != null && metrics.analysis_accuracy_count > 0
              ? ` (${metrics.analysis_accuracy_count}건 평균)`
              : ""}
          </div>
        </div>
        <div class="metric-segment">
          <div class="metric-label">AI 회고 평가 · 경험 활용</div>
          <div class="metric-value metric-value-compact">
            {metrics.rag_contribution_avg != null ? `${Math.round(metrics.rag_contribution_avg)}점` : "-"}
            {metrics.rag_contribution_count != null && metrics.rag_contribution_count > 0
              ? ` (RAG 사용 ${metrics.rag_contribution_count}건 평균)`
              : ""}
          </div>
        </div>
      </div>

    {/if}

    {#if isForecastLab && (reportStatus !== "ready" || recentReports.length)}
      <section class="desk-panel desk-recent">
        <header class="desk-toolbar"><h3>최근 발행 리포트</h3><a href="#/reports">전체 보기 <span aria-hidden="true">→</span></a></header>
        {#if recentReports.length}
          {#each recentReports as report}
            <a class="desk-recent-row" href={`#/reports/${encodeURIComponent(report.ticker.toLowerCase())}`}>
              <span class="desk-document" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h5"/></svg></span>
              <span class="desk-instrument"><InstrumentLabel ticker={report.ticker} name={report.display_name} /></span>
              <DecisionBadge value={(report.stored_decision_position === undefined ? report.decision_position : report.stored_decision_position) || ""} />
              <time datetime={report.latest_at}>{formatDateTime(report.latest_at)}</time>
            </a>
          {/each}
        {:else}
          <div class="desk-state">{reportStatus === "loading" ? "리포트를 불러오는 중입니다." : reportStatus === "error" ? "최근 리포트를 조회할 수 없습니다." : "발행된 리포트가 없습니다."}</div>
        {/if}
      </section>
    {/if}
    <div class="dashboard-grid">
      {#if !isForecastLab || loading || error || ($viewMode === "portfolio" ? filteredPortfolioHoldings.length : filteredPositions.length)}
      <div class="card">
        <div class="card-header">
            <h3>{isForecastLab ? "보유 종목 명세" : "내 투자"}</h3>
            <a href="#/positions" class="card-link">전체 보기</a>
        </div>
        <div class="card-body" style="padding:0">
          <table class="data-table" style="border:none;box-shadow:none;border-radius:0">
            <tbody>
              {#if loading}
                <tr>
                  <td colspan="2">불러오는 중...</td>
                </tr>
              {:else if $viewMode === "portfolio"}
                {#if filteredPortfolioHoldings.length === 0}
                  <tr>
                    <td colspan="2" class="empty-state">보유 중인 종목이 없습니다.</td>
                  </tr>
                {:else}
                  {#each filteredPortfolioHoldings as h}
                    <tr on:click={() => goTrade(h.ticker)}>
                      <td><InstrumentLabel ticker={h.ticker} name={h.display_name} /></td>
                      <td>
                        {#if $showAmount && h.current_value_base != null}
                          {portfolioConfig?.base_currency === "USD"
                            ? `$${h.current_value_base.toLocaleString("en-US", { maximumFractionDigits: 2 })}`
                            : `₩${h.current_value_base.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`}
                        {/if}
                        {#if h.allocation_pct != null}
                          <span class="text-dim" style="margin-left:4px">({h.allocation_pct.toFixed(1)}%)</span>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                {/if}
              {:else if filteredPositions.length === 0}
                <tr>
                  <td colspan="2" class="empty-state">보유 중인 종목이 없습니다.</td>
                </tr>
              {:else}
                {#each filteredPositions as pos}
                  {@const totalAmount = getTotalAmount(pos)}
                  <tr on:click={() => goTrade(pos.ticker)}>
                    <td><InstrumentLabel ticker={pos.ticker} name={pos.display_name} /></td>
                    <td>
                      {#if totalAmount === null || pos.avg_cost == null}
                        <span class="text-dim">평가 미확인</span>
                      {:else if $showAmount}
                        <span>{formatAmount(totalAmount, pos.ticker)}</span>
                        <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                          ({formatSignedAmount(pos.pnl, pos.ticker)})
                        </span>
                      {:else}
                        <span class={pos.return_pct >= 0 ? "text-gain" : "text-loss"}>
                          {formatPercent(pos.return_pct)}
                        </span>
                      {/if}
                    </td>
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      {/if}
      <div class="card">
        <div class="card-header">
          <h3>대기열</h3>
          <a href="#/live" class="card-link">실시간 보기</a>
        </div>
        <div class="card-body">
          {#if queue.running}
            <div class="queue-item queue-running">
              <span class="queue-indicator"></span>
              <span class="queue-ticker"><InstrumentLabel ticker={queue.running} /></span>
              <span class="badge badge-info">실행중</span>
            </div>
          {/if}
          {#if queue.pending.length === 0 && !queue.running}
            <div class="queue-item queue-pending">
              <span class="queue-indicator"></span>
              <span class="queue-ticker">대기 없음</span>
              <span class="badge badge-muted">대기</span>
            </div>
          {:else}
            {#each queue.pending as item}
              <div class="queue-item queue-pending">
                <span class="queue-indicator"></span>
                <span class="queue-ticker"><InstrumentLabel ticker={item} /></span>
                <span class="badge badge-muted">대기중</span>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
    {/if}
    {#if $viewMode === "analysis" && metrics}
      <dialog bind:this={accuracyHelp} class="accuracy-help" aria-labelledby="accuracy-help-title">
        <h2 id="accuracy-help-title">분석 점수 채점 기준</h2>
        <p>AI가 당시 전망의 방향·시점·근거를 이후 시장 관측과 대조해 매긴 점수입니다.</p>
        <dl>
          <dt>90~100점</dt><dd>방향, 시점, 근거가 모두 일치</dd>
          <dt>70~89점</dt><dd>방향은 맞고 시점이나 근거에 일부 오류</dd>
          <dt>50~69점</dt><dd>방향은 맞지만 당시 근거가 부실</dd>
          <dt>30~49점</dt><dd>방향은 틀렸지만 분석 일부가 유효</dd>
          <dt>0~29점</dt><dd>전망과 근거가 전반적으로 불일치</dd>
        </dl>
        <p>전망 기간이 지나지 않았거나 대조할 자료가 부족한 사이클은 제외합니다.
          평가 가능한 사이클이 없는 회고는 평균에서 빠집니다.</p>
        <form method="dialog"><button class="btn-secondary">닫기</button></form>
      </dialog>
    {/if}
  </div>
</section>

<style>
  .quiet-account {grid-column:1/-1; background:var(--fl-surface, #202124); color:var(--fl-ink, #f4f2e9); border:1px solid var(--fl-line, #3b3d41); border-radius:.7rem; padding:1.1rem 1.25rem;}
  .quiet-account header,.quiet-account dl div,.quiet-actions {display:flex; justify-content:space-between; align-items:center; gap:.75rem;}
  .quiet-account header {border-bottom:1px solid var(--fl-line, #3b3d41); padding-bottom:.75rem;}
  .quiet-account h3 {font-size:1.1rem; margin:0;}
  .quiet-account h4 {font-size:1.15rem; margin:1rem 0 .25rem;}
  .quiet-account p,.quiet-account dt {color:var(--fl-muted, #b5b4ad); font-size:.89rem;}
  .quiet-account p {margin:.2rem 0 .8rem;}
  .quiet-account a,.quiet-account button {font:inherit; color:var(--fl-accent, #d5f65e); font-weight:600; font-size:.85rem;}
  .quiet-account button {padding:0; border:0; background:none; cursor:pointer;}
  .quiet-actions {justify-content:flex-start;}
  .quiet-account dl {margin:1rem 0 0;} .quiet-account dl div {border-top:1px solid var(--fl-line, #3b3d41); padding:.55rem 0;}
  .quiet-account dd {margin:0;text-align:right;}
  .operation-line,.performance-note { padding:1rem 1.15rem; border:1px solid var(--fl-line, #3b3d41); border-radius:.65rem; background:var(--fl-surface, #202124); color:var(--fl-ink, #f4f2e9);}
  .operation-line {display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:.75rem;}
  .operation-line h3,.performance-note h3 {margin:0; font-size:1rem;}
  .operation-line p,.performance-note p {margin:.35rem 0; color:var(--fl-muted, #b5b4ad);}
  .operation-line a,.performance-note a {color:var(--fl-accent, #d5f65e); font-weight:600; font-size:.87rem;}
  .performance-note {margin-block:1rem;}

  .accuracy-label { display: flex; align-items: center; gap: 4px; }
  .help-button {
    display: inline-grid;
    place-items: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 0;
    color: inherit;
    cursor: pointer;
    font: inherit;
  }
  .help-button span {
    border: 1px solid currentColor;
    border-radius: 50%;
    width: 16px;
    height: 16px;
    line-height: 15px;
    text-align: center;
    font-weight: 700;
  }
  .accuracy-help {
    margin: auto;
    width: min(26rem, calc(100% - 2rem));
    max-height: 85vh;
    overflow: auto;
    box-sizing: border-box;
    padding: 1.25rem;
    background: var(--bg-card);
    color: inherit;
    border: 1px solid var(--border);
    border-radius: 12px;
  }
  .accuracy-help::backdrop { background: rgba(0, 0, 0, 0.6); }
  .accuracy-help h2 { margin: 0; font-size: 1.1rem; }
  .accuracy-help p, .accuracy-help dl { font-size: .9rem; line-height: 1.55; }
  .accuracy-help dl { display: grid; grid-template-columns: auto 1fr; gap: .4rem 1rem; }
  .accuracy-help dt { font-weight: 600; }
  .accuracy-help dd { margin: 0; }
  .accuracy-help form { text-align: right; }

  .metric-value-compact {
    font-size: 1.04rem;
    line-height: 1.35;
    letter-spacing: -0.01em;
    word-break: keep-all;
  }
</style>
