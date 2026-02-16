<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPositionsMarket, fetchMetrics } from "../lib/api/endpoints";
  import { formatMoney, formatPercent, formatErrorMessage } from "../lib/utils/format";

  type PositionMarket = {
    position_id: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  let loading = true;
  let error = "";
  let positions: PositionMarket[] = [];
  let totalPnl = 0;

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const loadData = async () => {
    loading = true;
    error = "";
    try {
      const [positionsRes, metricsRes] = await Promise.all([
        fetchPositionsMarket(),
        fetchMetrics(),
      ]);
      positions = (positionsRes as PositionMarket[]) || [];
      totalPnl = (metricsRes as { total_unrealized_pnl?: number })?.total_unrealized_pnl ?? 0;
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load positions.");
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    loadData();
  });
</script>

<section class="page" id="page-positions">
  <div class="page-container">
    <div class="page-header">
      <h2>Position</h2>
      <span class={`pnl-banner ${totalPnl >= 0 ? "pnl-pos" : "pnl-neg"}`}>
        PnL {formatMoney(totalPnl)}
      </span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Shares</th>
            <th>Avg Cost</th>
            <th>Price</th>
            <th>PnL</th>
            <th>Return</th>
          </tr>
        </thead>
        <tbody>
          {#if loading}
            <tr>
              <td colspan="6">Loading...</td>
            </tr>
            {:else if error}
              <tr>
                <td colspan="6" class="error-text">{error}</td>
              </tr>
          {:else if positions.length === 0}
            <tr>
              <td colspan="6">No active positions.</td>
            </tr>
          {:else}
            {#each positions as pos}
              <tr on:click={() => goTrade(pos.ticker)}>
                <td><span class="ticker-badge">{pos.ticker}</span></td>
                <td>{pos.shares}</td>
                <td>{pos.avg_cost ? `$${pos.avg_cost.toFixed(2)}` : "-"}</td>
                <td>{pos.current_price ? `$${pos.current_price.toFixed(2)}` : "-"}</td>
                <td class={pos.pnl >= 0 ? "text-gain" : "text-loss"}>{formatMoney(pos.pnl)}</td>
                <td class={pos.return_pct >= 0 ? "text-gain" : "text-loss"}>{formatPercent(pos.return_pct)}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>

    <div class="pos-card-list">
      {#if loading}
        <div class="card pos-card">
          <div class="pos-card-details">Loading...</div>
        </div>
        {:else if error}
          <div class="card pos-card">
            <div class="pos-card-details error-text">{error}</div>
          </div>
      {:else if positions.length === 0}
        <div class="card pos-card">
          <div class="pos-card-details">No active positions.</div>
        </div>
      {:else}
        {#each positions as pos}
          <div class="card pos-card" on:click={() => goTrade(pos.ticker)}>
            <div class="pos-card-top">
              <span class="ticker-badge">{pos.ticker}</span>
              <span class={`return-badge ${pos.return_pct >= 0 ? "return-pos" : "return-neg"}`}>
                {formatPercent(pos.return_pct)}
              </span>
            </div>
            <div class="pos-card-details">
              <span>{pos.shares} shares @ {pos.avg_cost ? `$${pos.avg_cost.toFixed(2)}` : "-"}</span>
              <span>Price: {pos.current_price ? `$${pos.current_price.toFixed(2)}` : "-"} · PnL: <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"}>{formatMoney(pos.pnl)}</span></span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</section>
