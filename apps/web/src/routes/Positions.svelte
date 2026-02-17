<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPositionsMarket, fetchMetrics } from "../lib/api/endpoints";
  import { formatMoney, formatMoneyPlain, formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";

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
      error = formatErrorMessage(err, "투자를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    loadData();
  });

  const getTotalAmount = (pos: PositionMarket) =>
    pos.avg_cost ? pos.avg_cost * pos.shares : null;
</script>

<section class="page" id="page-positions">
  <div class="page-container">
    <div class="page-header">
      <h2>투자</h2>
      <span class={`pnl-banner ${totalPnl >= 0 ? "pnl-pos" : "pnl-neg"}`}>
        손익 {formatMoney(totalPnl)}
      </span>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>티커</th>
            <th>보유</th>
            <th>1주 평균</th>
            <th>총 금액</th>
            <th>수익률</th>
          </tr>
        </thead>
        <tbody>
          {#if loading}
            <tr>
              <td colspan="5">불러오는 중...</td>
            </tr>
            {:else if error}
              <tr>
                <td colspan="5" class="error-text">{error}</td>
              </tr>
          {:else if positions.length === 0}
            <tr>
              <td colspan="5">투자가 없습니다.</td>
            </tr>
          {:else}
            {#each positions as pos}
              {@const totalAmount = getTotalAmount(pos)}
              <tr on:click={() => goTrade(pos.ticker)}>
                <td>
                  <span class="ticker-badge">{pos.ticker}</span>
                  {#if $tickerNames[pos.ticker]}
                    <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>
                  {/if}
                </td>
                <td>{pos.shares}</td>
                <td>{pos.avg_cost ? `$${pos.avg_cost.toFixed(2)}` : "-"}</td>
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
          <div class="pos-card-details">불러오는 중...</div>
        </div>
        {:else if error}
          <div class="card pos-card">
            <div class="pos-card-details error-text">{error}</div>
          </div>
      {:else if positions.length === 0}
        <div class="card pos-card">
          <div class="pos-card-details">투자가 없습니다.</div>
        </div>
      {:else}
        {#each positions as pos}
          {@const totalAmount = getTotalAmount(pos)}
          <div class="card pos-card" on:click={() => goTrade(pos.ticker)}>
            <div class="pos-card-top">
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                <span class="ticker-badge">{pos.ticker}</span>
                {#if $tickerNames[pos.ticker]}
                  <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>
                {/if}
              </div>
              <span class={`return-badge ${pos.return_pct >= 0 ? "return-pos" : "return-neg"}`}>
                {formatPercent(pos.return_pct)}
              </span>
            </div>
            <div class="pos-card-details">
            <span>보유 {pos.shares} · 1주 평균 {pos.avg_cost ? `$${pos.avg_cost.toFixed(2)}` : "-"}</span>
            <span>
              총 금액 {totalAmount !== null ? formatMoneyPlain(totalAmount) : "-"}
              <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                ({formatMoney(pos.pnl)})
              </span>
            </span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
</section>
