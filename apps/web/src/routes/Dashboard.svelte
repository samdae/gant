<script lang="ts">
  import {
    fetchHealth,
    fetchMetrics,
    fetchPositionsMarket,
    fetchQueue,
    fetchScheduleSummary,
    fetchPortfolioConfig,
    fetchPortfolioHoldings,
  } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage, formatAmount, formatSignedAmount } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { currencyFilter, showAmount, matchesCurrency, tickerCurrency } from "../stores/currency";
  import { viewMode, portfolioRefreshTrigger } from "../stores/mode";

  type Metrics = {
    active_positions: number;
    closed_positions: number;
    wins: number;
    losses: number;
    total_unrealized_pnl: number;
    total_unrealized_return_pct: number;
    total_realized_pnl: number;
    total_realized_return_pct: number;
    total_pnl: number;
    total_return_pct: number;
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
    pos.avg_cost !== null && pos.avg_cost !== undefined
      ? pos.avg_cost * pos.shares
      : null;

  const loadData = async () => {
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
      error = formatErrorMessage(err, "대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  $: $viewMode, $portfolioRefreshTrigger, loadData();

  $: todayRunsTotal = scheduleSummary
    ? scheduleSummary.done + scheduleSummary.failed + scheduleSummary.skipped + scheduleSummary.running
    : null;

  $: filteredPositions = positions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));
  $: filteredPortfolioHoldings = portfolioHoldings.filter((h) => matchesCurrency(h.ticker, $currencyFilter));

</script>

<section class="page" id="page-dashboard">
  <div class="page-container">
    <div class="page-header">
      <h2>홈</h2>
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
          <div class="summary-title">오늘 실행</div>
        </div>
        <div class="summary-total">
          {todayRunsTotal ?? "-"}
        </div>
      </div>
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
          <div class="metric-label">총손익</div>
          <div class="metric-value" class:text-gain={metrics && metrics.total_return_pct >= 0} class:text-loss={metrics && metrics.total_return_pct < 0}>
            {metrics ? formatPercent(metrics.total_return_pct) : "-"}
          </div>
          <div class="metric-sub metric-sub-grid">
            <span>실현</span><span>{metrics ? formatPercent(metrics.total_realized_return_pct) : "-"}</span>
            <span>미실현</span><span>{metrics ? formatPercent(metrics.total_unrealized_return_pct) : "-"}</span>
          </div>
        </div>
        <div class="metric-segment">
          <div class="metric-icon icon-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z" />
              <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </div>
          <div class="metric-label">투자</div>
          <div class="metric-value">{metrics ? metrics.active_positions : "-"}</div>
          <div class="metric-sub">
            <div>승 {metrics ? metrics.wins : "-"}</div>
            <div>패 {metrics ? metrics.losses : "-"}</div>
          </div>
        </div>
      {/if}
    </div>

    {#if $viewMode === "analysis" && metrics && (metrics.analysis_accuracy_count != null && metrics.analysis_accuracy_count > 0 || metrics.rag_contribution_count != null && metrics.rag_contribution_count > 0)}
      <div class="card metric-strip" style="margin-bottom:16px">
        <div class="metric-segment">
          <div class="metric-label">분석 정확도</div>
          <div class="metric-value metric-value-compact">
            {metrics.analysis_accuracy_avg != null ? `${Math.round(metrics.analysis_accuracy_avg)}점` : "-"}
            {metrics.analysis_accuracy_count != null && metrics.analysis_accuracy_count > 0
              ? ` (${metrics.analysis_accuracy_count}건 평균)`
              : ""}
          </div>
        </div>
        <div class="metric-segment">
          <div class="metric-label">RAG 기여도</div>
          <div class="metric-value metric-value-compact">
            {metrics.rag_contribution_avg != null ? `${Math.round(metrics.rag_contribution_avg)}점` : "-"}
            {metrics.rag_contribution_count != null && metrics.rag_contribution_count > 0
              ? ` (RAG 사용 ${metrics.rag_contribution_count}건 평균)`
              : ""}
          </div>
        </div>
      </div>
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
                      {#if $showAmount && totalAmount !== null}
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
  .metric-value-compact {
    font-size: 1.04rem;
    line-height: 1.35;
    letter-spacing: -0.01em;
    word-break: keep-all;
  }
</style>
