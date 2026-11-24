<script lang="ts">
  import { onMount } from "svelte";
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
  import { tickerNames } from "../stores/tickerNames";
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
  let portfolioHoldings: Array<{ ticker: string; shares: number; current_value_base?: number; allocation_pct?: number }> = [];

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const goArchive = () => {
    window.location.hash = "#/archive";
  };

  const getTotalAmount = (pos: PositionMarket) =>
    pos.current_price !== null && pos.current_price !== undefined
      ? pos.current_price * pos.shares
      : null;

  type RecentReport = { ticker: string; report_count: number; latest_at: string };
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
        const ph = results[6] as { holdings?: Array<{ ticker: string; shares: number; current_value_base?: number; allocation_pct?: number }> };
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
          실행중 · {queue.running}
        </span>
      {:else}
        <span class="badge badge-info">
          <span class="status-dot status-info" style="width:6px;height:6px;margin-right:4px"></span>
          온라인 · 대기
        </span>
      {/if}
    </div>

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

    {#if isForecastLab}
      <section class="desk-panel desk-recent">
        <header class="desk-toolbar"><h3>최근 발행 리포트</h3><a href="#/reports">전체 보기 <span aria-hidden="true">→</span></a></header>
        {#if recentReports.length}
          {#each recentReports as report}
            <a class="desk-recent-row" href={`#/reports/${encodeURIComponent(report.ticker.toLowerCase())}`}>
              <span class="desk-document" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h5"/></svg></span>
              <span class="desk-instrument"><b>{report.ticker}</b>{#if $tickerNames[report.ticker]}<small>{$tickerNames[report.ticker]}</small>{/if}</span>
              <time datetime={report.latest_at}>{formatDateTime(report.latest_at)}</time>
            </a>
          {/each}
        {:else}
          <div class="desk-state">{reportStatus === "loading" ? "리포트를 불러오는 중입니다." : reportStatus === "error" ? "최근 리포트를 조회할 수 없습니다." : "발행된 리포트가 없습니다."}</div>
        {/if}
      </section>
    {/if}
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

    <div class="dashboard-grid">
      <div class="card">
        <div class="card-header">
            <h3>내 투자</h3>
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
                    <td colspan="2" class="empty-state">내 투자가 없습니다.</td>
                  </tr>
                {:else}
                  {#each filteredPortfolioHoldings as h}
                    <tr on:click={() => goTrade(h.ticker)}>
                      <td><span class="ticker-badge">{h.ticker}</span>{#if $tickerNames[h.ticker]} <span class="ticker-tag">{$tickerNames[h.ticker]}</span>{/if}</td>
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
                  <td colspan="2" class="empty-state">내 투자가 없습니다.</td>
                </tr>
              {:else}
                {#each filteredPositions as pos}
                  {@const totalAmount = getTotalAmount(pos)}
                  <tr on:click={() => goTrade(pos.ticker)}>
                    <td><span class="ticker-badge">{pos.ticker}</span>{#if $tickerNames[pos.ticker]} <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>{/if}</td>
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

      <div class="card">
        <div class="card-header">
          <h3>대기열</h3>
          <a href="#/live" class="card-link">실시간 보기</a>
        </div>
        <div class="card-body">
          {#if queue.running}
            <div class="queue-item queue-running">
              <span class="queue-indicator"></span>
              <span class="queue-ticker">{queue.running}</span>
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
                <span class="queue-ticker">{item}</span>
                <span class="badge badge-muted">대기중</span>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>
</section>

<style>
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
