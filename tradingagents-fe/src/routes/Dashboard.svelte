<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchActivity,
    fetchHealth,
    fetchMetrics,
    fetchPositionsMarket,
    fetchQueue,
  } from "../lib/api/endpoints";
  import { formatMoney, formatPercent, formatAgo } from "../lib/utils/format";

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

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const mapDecision = (value?: string) => {
    if (!value) return null;
    if (value === "BUY") return "매수";
    if (value === "SELL") return "매도";
    if (value === "HOLD") return "관망";
    return value;
  };

  const formatActivity = (item: ActivityEvent) => {
    if (item.event_type === "trade") {
      const action = item.action === "BUY" ? "매수" : "매도";
      const shares = item.shares ?? 0;
      const price = item.price ? `$${item.price.toFixed(2)}` : "";
      return `${action} ${shares}주 @ ${price}`;
    }
    if (item.event_type === "analysis") {
      const decision = mapDecision(item.decision);
      return decision ? `결정: ${decision}` : "분석 완료";
    }
    return "활동";
  };

  const loadData = async () => {
    loading = true;
    error = "";
    try {
      const [metricsRes, positionsRes, queueRes, activityRes, healthRes] = await Promise.all([
        fetchMetrics(),
        fetchPositionsMarket(),
        fetchQueue(),
        fetchActivity(),
        fetchHealth(),
      ]);

      metrics = metricsRes as Metrics;
      positions = (positionsRes as PositionMarket[]) || [];
      queue = (queueRes as QueueStatus) || { running: null, pending: [], total: 0 };
      activity = (activityRes as ActivityEvent[]) || [];
      health = healthRes as Health;
    } catch (err) {
      error = err instanceof Error ? err.message : "데이터를 불러오지 못했습니다.";
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    loadData();
  });
</script>

<section class="page" id="page-dashboard">
  <div class="page-container">
    <div class="page-header">
      <h2>대시보드</h2>
      <span class="badge badge-gain">
        <span
          class="status-dot status-ok"
          style="width:6px;height:6px;margin-right:4px"
        ></span>
        {error ? "시스템 이슈" : "시스템 정상"}
      </span>
    </div>

    <div class="card-grid card-grid-3" style="margin-bottom:20px">
      <div class="metric-card">
        <div class="metric-icon icon-gain">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M12 2v20M17 7l-5-5-5 5" />
          </svg>
        </div>
        <div class="metric-label">총 손익</div>
        <div class="metric-value text-gain">
          {metrics ? formatMoney(metrics.total_unrealized_pnl) : "-"}
        </div>
        <div class="metric-sub">
          전체 수익률 {metrics ? formatPercent(metrics.total_unrealized_return_pct) : "-"}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon icon-primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="2" y="7" width="20" height="14" rx="2" />
            <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2" />
          </svg>
        </div>
        <div class="metric-label">포지션</div>
        <div class="metric-value">{metrics ? metrics.active_positions : "-"}</div>
        <div class="metric-sub">
          승 {metrics ? metrics.wins : "-"} · 패 {metrics ? metrics.losses : "-"}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon icon-info">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        </div>
        <div class="metric-label">스케줄</div>
        <div class="metric-value">{queue.total}</div>
        <div class="metric-sub">가동 시간: {health ? Math.floor(health.uptime_seconds / 3600) : 0}시간</div>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="card">
        <div class="card-header">
          <h3>활성 포지션</h3>
          <a href="#/positions" class="card-link">전체 보기</a>
        </div>
        <div class="card-body" style="padding:0">
          <table class="data-table" style="border:none;box-shadow:none;border-radius:0">
            <thead>
              <tr>
                <th>티커</th>
                <th>수량</th>
                <th>현재가</th>
                <th>손익</th>
                <th>수익률</th>
              </tr>
            </thead>
            <tbody>
              {#if loading}
                <tr>
                  <td colspan="5">불러오는 중...</td>
                </tr>
              {:else if positions.length === 0}
                <tr>
                  <td colspan="5">활성 포지션이 없습니다.</td>
                </tr>
              {:else}
                {#each positions as pos}
                  <tr on:click={() => goTrade(pos.ticker)}>
                    <td><span class="ticker-badge">{pos.ticker}</span></td>
                    <td>{pos.shares}</td>
                    <td>{pos.current_price ? `$${pos.current_price.toFixed(2)}` : "-"}</td>
                    <td class={pos.pnl >= 0 ? "text-gain" : "text-loss"}>{formatMoney(pos.pnl)}</td>
                    <td class={pos.return_pct >= 0 ? "text-gain" : "text-loss"}>{formatPercent(pos.return_pct)}</td>
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
            <h3>큐</h3>
            <a href="#/live" class="card-link">라이브 보기</a>
          </div>
          <div class="card-body">
            {#if queue.running}
              <div class="queue-item queue-running">
                <span class="queue-indicator"></span>
                <span class="queue-ticker">{queue.running}</span>
                <span class="badge badge-info">실행 중</span>
              </div>
            {/if}
            {#if queue.pending.length === 0}
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
                  <span class="badge badge-muted">대기</span>
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
                  <div class="activity-content">최근 활동이 없습니다.</div>
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
                        {formatAgo(item.created_at)}{item.scheduled_cycle ? ` · 사이클 #${item.scheduled_cycle}` : ""}
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
