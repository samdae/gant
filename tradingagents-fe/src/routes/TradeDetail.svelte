<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import {
    fetchPositionDetail,
    fetchPositions,
    fetchPositionsMarket,
    fetchReportsByTicker,
  } from "../lib/api/endpoints";
  import { formatMoney, formatPercent, formatDateTime, formatErrorMessage } from "../lib/utils/format";

  type PositionMarket = {
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  type PositionDetail = {
    position: { id: number; ticker: string; shares: number; avg_cost: number | null };
    trades: Array<{ id: number; action: string; shares: number; price: number; executed_at: string }>;
    reports: Array<{ id: number; created_at: string; final_trade_decision?: string; investment_plan?: string }>;
  };

  let ticker = "";
  let loading = true;
  let error = "";
  let summary: PositionMarket | null = null;
  let reports: PositionDetail["reports"] = [];
  let tab: "report" | "history" = "report";

  const mapDecision = (value?: string | null) => {
    if (!value) return "-";
    if (value.toUpperCase().includes("BUY")) return "Buy";
    if (value.toUpperCase().includes("SELL")) return "Sell";
    if (value.toUpperCase().includes("HOLD")) return "Hold";
    return value;
  };

  const loadDetail = async (t: string) => {
    loading = true;
    error = "";
    try {
      const positionsMarket = (await fetchPositionsMarket()) as PositionMarket[];
      summary = positionsMarket.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;

      const active = (await fetchPositions("active")) as Array<{ id: number; ticker: string }>;
      let target = active.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;
      if (!target) {
        const closed = (await fetchPositions("closed")) as Array<{ id: number; ticker: string }>;
        target = closed.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;
      }
      if (!target) {
        reports = (await fetchReportsByTicker(t)) as PositionDetail["reports"];
        return;
      }

      const detail = (await fetchPositionDetail(target.id)) as PositionDetail;
      reports = detail.reports || [];
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load data.");
    } finally {
      loading = false;
    }
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadDetail(ticker);
  }

  const latestReport = () => {
    if (!reports || reports.length === 0) return null;
    return [...reports].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  };

  onMount(() => {
    if (ticker) loadDetail(ticker);
  });
</script>

<section class="page" id="page-trade">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker} Report</h2>
      <span class={`pnl-banner ${summary && summary.return_pct >= 0 ? "pnl-pos" : "pnl-neg"}`}>
        {summary ? formatPercent(summary.return_pct) : "-"}
      </span>
    </div>

    <div class="card-grid" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header">
          <h3>Position</h3>
        </div>
        <div class="card-body">
          <div class="stat-row"><span class="stat-label">Shares</span><span class="stat-value">{summary?.shares ?? "-"}</span></div>
          <div class="stat-row"><span class="stat-label">Avg Cost</span><span class="stat-value">{summary?.avg_cost ? `$${summary.avg_cost.toFixed(2)}` : "-"}</span></div>
          <div class="stat-row"><span class="stat-label">Price</span><span class="stat-value">{summary?.current_price ? `$${summary.current_price.toFixed(2)}` : "-"}</span></div>
          <div class="stat-row"><span class="stat-label">PnL</span><span class={`stat-value ${summary && summary.pnl >= 0 ? "text-gain" : "text-loss"}`}>{summary ? formatMoney(summary.pnl) : "-"}</span></div>
        </div>
      </div>
    </div>

    <div class="trade-actions">
      <a href={`#/archive/${ticker.toLowerCase()}`} class="btn btn-ghost" id="viewArchiveBtn">View archive</a>
    </div>

    <div class="tab-bar">
      <button class={`tab-btn ${tab === "report" ? "active" : ""}`} on:click={() => (tab = "report")}>Latest Report</button>
      <button class={`tab-btn ${tab === "history" ? "active" : ""}`} on:click={() => (tab = "history")}>History</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">Loading...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if tab === "report"}
      {#if latestReport()}
        <div class="card" style="margin-bottom:12px">
          <div class="card-body">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
              <span class="cycle-badge">Report #{latestReport()?.id}</span>
              <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(latestReport()?.created_at)}</span>
            </div>
            <div class="strategy-text">
              <strong style="color:var(--text);font-size:0.875rem;display:block;margin-bottom:4px">Final decision:
                {mapDecision(latestReport()?.final_trade_decision)}</strong>
              {latestReport()?.investment_plan || latestReport()?.final_trade_decision || ""}
            </div>
          </div>
        </div>
      {:else}
        <div class="card" style="padding:16px">No reports yet.</div>
      {/if}
    {:else}
      <div class="history-list">
        {#if reports.length === 0}
          <div class="card history-entry">
            <div class="history-action">No history.</div>
          </div>
        {:else}
          {#each reports as report}
            <div class="card history-entry">
              <div class="history-top">
                <span class="history-no">#{report.id}</span>
                <span class="history-date">{formatDateTime(report.created_at)}</span>
                <span class="badge badge-gain">{mapDecision(report.final_trade_decision)}</span>
              </div>
              <div class="history-action">{report.investment_plan || report.final_trade_decision || ""}</div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</section>
