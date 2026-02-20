<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchActivity,
    fetchHealth,
    fetchMetrics,
    fetchPositionsMarket,
    fetchQueue,
    fetchScheduleSummary,
  } from "../lib/api/endpoints";
  import { formatMoney, formatMoneyPlain, formatPercent, formatAgo, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";

  type Metrics = {
    active_positions: number;
    closed_positions: number;
    wins: number;
    losses: number;
    total_unrealized_pnl: number;
    total_unrealized_return_pct: number;
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

  type ActivityEvent = {
    event_type: string;
    ticker: string;
    created_at: string;
    scheduled_cycle?: number;
    action?: string;
    decision?: string;
    shares?: number;
    price?: number;
  };

  let loading = true;
  let error = "";
  let metrics: Metrics | null = null;
  let health: Health | null = null;
  let positions: PositionMarket[] = [];
  let queue: QueueStatus = { running: null, pending: [], total: 0 };
  let activity: ActivityEvent[] = [];
  let scheduleSummary: ScheduleSummary | null = null;
  let todayRunsTotal: number | null = null;

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const goArchive = () => {
    window.location.hash = "#/archive";
  };

  const mapDecision = (value?: string) => {
    if (!value) return null;
    if (value === "BUY") return "매수";
    if (value === "SELL") return "매도";
    if (value === "HOLD") return "관망";
    return value;
  };

  const formatShares = (value?: number) => {
    if (value == null) return "";
    return value.toLocaleString(undefined, { maximumFractionDigits: 6 });
  };

  const formatActivity = (item: ActivityEvent) => {
    if (item.event_type === "trade") {
      const action = item.action === "BUY" ? "매수" : "매도";
      const shares = item.shares ?? 0;
      const price = item.price ? `$${item.price.toFixed(2)}` : "";
      return `${action} ${shares} @ ${price}`;
    }
    if (item.event_type === "analysis") {
      const decision = mapDecision(item.decision);
      if (!decision) return "분석 완료";
      if (item.shares != null) return `결정: ${decision} (${formatShares(item.shares)}주)`;
      return `결정: ${decision}`;
    }
    return "활동";
  };

  const getTotalAmount = (pos: PositionMarket) =>
    pos.avg_cost !== null && pos.avg_cost !== undefined
      ? pos.avg_cost * pos.shares
      : null;

  const loadData = async () => {
    loading = true;
    error = "";
    try {
      const [metricsRes, positionsRes, queueRes, activityRes, healthRes, summaryRes] = await Promise.all([
        fetchMetrics(),
        fetchPositionsMarket(),
        fetchQueue(),
        fetchActivity(),
        fetchHealth(),
        fetchScheduleSummary(),
      ]);

      metrics = metricsRes as Metrics;
      positions = (positionsRes as PositionMarket[]) || [];
      queue = (queueRes as QueueStatus) || { running: null, pending: [], total: 0 };
      activity = (activityRes as ActivityEvent[]) || [];
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
        <div class="metric-value text-gain">
          {metrics ? formatMoney(metrics.total_unrealized_pnl) : "-"}
        </div>
        <div class="metric-sub">
          수익률 {metrics ? formatPercent(metrics.total_unrealized_return_pct) : "-"}
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
          승 {metrics ? metrics.wins : "-"} · 패 {metrics ? metrics.losses : "-"}
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
              {:else if positions.length === 0}
                <tr>
                  <td colspan="2" class="empty-state">내 투자가 없습니다.</td>
                </tr>
              {:else}
                {#each positions as pos}
                  {@const totalAmount = getTotalAmount(pos)}
                  <tr on:click={() => goTrade(pos.ticker)}>
                    <td><span class="ticker-badge">{pos.ticker}</span>{#if $tickerNames[pos.ticker]} <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>{/if}</td>
                    <td>
                      {#if totalAmount !== null}
                        <span>{formatMoneyPlain(totalAmount)}</span>
                        <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                          ({formatMoney(pos.pnl)})
                        </span>
                      {:else}
                        -
                      {/if}
                    </td>
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      <div style="display:flex;flex-direction:column;gap:16px">
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

        <div class="card" style="flex:1">
          <div class="card-header">
            <h3>최근 활동</h3>
            <span style="font-size:0.75rem;color:var(--text-dim)">최근 24시간</span>
          </div>
          <div class="card-body">
            <div class="activity-list">
              {#if loading}
                <div class="activity-item">
                  <div class="activity-content">불러오는 중...</div>
                </div>
              {:else if activity.length === 0}
                <div class="activity-item">
                  <div class="activity-content empty-state">최근 활동이 없습니다.</div>
                </div>
              {:else}
                {#each activity as item}
                  <div class="activity-item">
                    <span
                      class={`activity-dot ${item.event_type === "trade" ? (item.action === "SELL" ? "dot-sell" : "dot-buy") : item.decision === "HOLD" ? "dot-hold" : "dot-analysis"}`}
                    ></span>
                    <div class="activity-content">
                      <div class="activity-title">
                        <span class="ticker-badge" style="font-size:0.6875rem;padding:1px 5px">
                          {item.ticker}
                        </span>
                        &nbsp;{formatActivity(item)}
                      </div>
                      <div class="activity-time">
                        {formatAgo(item.created_at)}{item.scheduled_cycle ? ` · ${item.scheduled_cycle} 회차` : ""}
                      </div>
                    </div>
                  </div>
                {/each}
              {/if}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
