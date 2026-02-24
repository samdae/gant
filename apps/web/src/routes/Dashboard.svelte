<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchHealth,
    fetchMetrics,
    fetchPositionsMarket,
    fetchQueue,
    fetchScheduleSummary,
  } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage, formatAmount, formatSignedAmount } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { currencyFilter, showAmount, matchesCurrency, tickerCurrency } from "../stores/currency";

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
      const [metricsRes, positionsRes, queueRes, healthRes, summaryRes] = await Promise.all([
        fetchMetrics(),
        fetchPositionsMarket(),
        fetchQueue(),
        fetchHealth(),
        fetchScheduleSummary(),
      ]);

      metrics = metricsRes as Metrics;
      positions = (positionsRes as PositionMarket[]) || [];
      queue = (queueRes as QueueStatus) || { running: null, pending: [], total: 0 };
      health = healthRes as Health;
      scheduleSummary = summaryRes as ScheduleSummary;
    } catch (err) {
      error = formatErrorMessage(err, "대시보드 데이터를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    loadData();
  });

  $: todayRunsTotal = scheduleSummary
    ? scheduleSummary.done + scheduleSummary.failed + scheduleSummary.skipped + scheduleSummary.running
    : null;

  $: filteredPositions = positions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));

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
    </div>

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
