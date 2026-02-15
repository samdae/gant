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
  import { formatMoney, formatPercent, formatAgo, formatErrorMessage } from "../lib/utils/format";

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

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const goArchive = () => {
    window.location.hash = "#/archive";
  };

  const mapDecision = (value?: string) => {
    if (!value) return null;
    if (value === "BUY") return "BUY";
    if (value === "SELL") return "SELL";
    if (value === "HOLD") return "HOLD";
    return value;
  };

  const formatActivity = (item: ActivityEvent) => {
    if (item.event_type === "trade") {
      const action = item.action === "BUY" ? "BUY" : "SELL";
      const shares = item.shares ?? 0;
      const price = item.price ? `$${item.price.toFixed(2)}` : "";
      return `${action} ${shares} @ ${price}`;
    }
    if (item.event_type === "analysis") {
      const decision = mapDecision(item.decision);
      return decision ? `Decision: ${decision}` : "Analysis complete";
    }
    return "Activity";
  };

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
      error = formatErrorMessage(err, "Failed to load dashboard data.");
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
      <h2>Dashboard</h2>
      <span class="badge badge-gain">
        <span
          class="status-dot status-ok"
          style="width:6px;height:6px;margin-right:4px"
        ></span>
        {error ? "System issue" : "System ok"}
      </span>
    </div>

    <button class="card summary-banner" type="button" on:click={goArchive}>
      <div class="summary-header">
        <div>
          <div class="summary-title">Today Runs</div>
        </div>
        <div class="summary-total">
          {scheduleSummary ? scheduleSummary.total : "-"}
        </div>
      </div>
      <div class="summary-metrics">
        <div class="summary-item">
          <span class="summary-label">Done</span>
          <span class="summary-value text-gain">
            {scheduleSummary ? scheduleSummary.done : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Skipped</span>
          <span class="summary-value">
            {scheduleSummary ? scheduleSummary.skipped : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Failed</span>
          <span class="summary-value text-loss">
            {scheduleSummary ? scheduleSummary.failed : "-"}
          </span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Running</span>
          <span class="summary-value">
            {scheduleSummary ? scheduleSummary.running : "-"}
          </span>
        </div>
      </div>
    </button>

    <div class="card-grid card-grid-3" style="margin-bottom:16px">
      <div class="metric-card">
        <div class="metric-icon icon-gain">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M12 2v20M17 7l-5-5-5 5" />
          </svg>
        </div>
        <div class="metric-label">Total PnL</div>
        <div class="metric-value text-gain">
          {metrics ? formatMoney(metrics.total_unrealized_pnl) : "-"}
        </div>
        <div class="metric-sub">
          Total return {metrics ? formatPercent(metrics.total_unrealized_return_pct) : "-"}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon icon-primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <rect x="2" y="7" width="20" height="14" rx="2" />
            <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2" />
          </svg>
        </div>
        <div class="metric-label">Positions</div>
        <div class="metric-value">{metrics ? metrics.active_positions : "-"}</div>
        <div class="metric-sub">
          Wins {metrics ? metrics.wins : "-"} · Losses {metrics ? metrics.losses : "-"}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon icon-info">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        </div>
        <div class="metric-label">Queue</div>
        <div class="metric-value">{queue.total}</div>
        <div class="metric-sub">Uptime: {health ? Math.floor(health.uptime_seconds / 3600) : 0}h</div>
      </div>
    </div>

    <div class="dashboard-grid">
      <div class="card">
        <div class="card-header">
            <h3>Active Positions</h3>
            <a href="#/positions" class="card-link">View all</a>
        </div>
        <div class="card-body" style="padding:0">
          <table class="data-table" style="border:none;box-shadow:none;border-radius:0">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Shares</th>
                <th>Price</th>
                <th>PnL</th>
                <th>Return</th>
              </tr>
            </thead>
            <tbody>
              {#if loading}
                <tr>
                  <td colspan="5">Loading...</td>
                </tr>
              {:else if positions.length === 0}
                <tr>
                  <td colspan="5" class="empty-state">No active positions.</td>
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
            <h3>Queue</h3>
            <a href="#/live" class="card-link">View live</a>
          </div>
          <div class="card-body">
            {#if queue.running}
              <div class="queue-item queue-running">
                <span class="queue-indicator"></span>
                <span class="queue-ticker">{queue.running}</span>
                <span class="badge badge-info">Running</span>
              </div>
            {/if}
            {#if queue.pending.length === 0}
              <div class="queue-item queue-pending">
                <span class="queue-indicator"></span>
                <span class="queue-ticker">No pending</span>
                <span class="badge badge-muted">Idle</span>
              </div>
            {:else}
              {#each queue.pending as item}
                <div class="queue-item queue-pending">
                  <span class="queue-indicator"></span>
                  <span class="queue-ticker">{item}</span>
                  <span class="badge badge-muted">Queued</span>
                </div>
              {/each}
            {/if}
          </div>
        </div>

        <div class="card" style="flex:1">
          <div class="card-header">
            <h3>Recent Activity</h3>
            <span style="font-size:0.75rem;color:var(--text-dim)">Last 24h</span>
          </div>
          <div class="card-body">
            <div class="activity-list">
              {#if loading}
                <div class="activity-item">
                  <div class="activity-content">Loading...</div>
                </div>
              {:else if activity.length === 0}
                <div class="activity-item">
                  <div class="activity-content empty-state">No recent activity.</div>
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
                        {formatAgo(item.created_at)}{item.scheduled_cycle ? ` · Cycle #${item.scheduled_cycle}` : ""}
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
