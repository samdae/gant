<script lang="ts">
  import { onMount } from "svelte";
  import { fetchPositionsMarket, fetchPositionsClosed, fetchMetrics } from "../lib/api/endpoints";
  import { formatAmount, formatSignedAmount, formatMoneyPlain, formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { currencyFilter, showAmount, matchesCurrency, tickerCurrency } from "../stores/currency";

  type PositionMarket = {
    position_id: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  type ClosedPosition = {
    position_id: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    return_pct: number;
    currency: string;
    outcome: string;
    opened_at: string | null;
    closed_at: string | null;
  };

  let loading = true;
  let error = "";
  let positions: PositionMarket[] = [];
  let closedPositions: ClosedPosition[] = [];
  let totalPnl = 0;
  let tab: "active" | "closed" = "active";

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
  };

  const loadData = async () => {
    loading = true;
    error = "";
    try {
      const [positionsRes, closedRes, metricsRes] = await Promise.all([
        fetchPositionsMarket(),
        fetchPositionsClosed(),
        fetchMetrics(),
      ]);
      positions = (positionsRes as PositionMarket[]) || [];
      closedPositions = (closedRes as ClosedPosition[]) || [];
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

  $: filteredPositions = positions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));
  $: filteredClosed = closedPositions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));

  const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    try {
      return new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
    } catch { return "-"; }
  };

  const holdingDays = (opened: string | null, closed: string | null) => {
    if (!opened || !closed) return null;
    try {
      const ms = new Date(closed).getTime() - new Date(opened).getTime();
      return Math.max(1, Math.round(ms / 86_400_000));
    } catch { return null; }
  };
</script>

<section class="page" id="page-positions">
  <div class="page-container">
    <div class="page-header">
      <h2>투자</h2>
      <span class={`pnl-banner ${totalPnl >= 0 ? "pnl-pos" : "pnl-neg"}`}>
        {#if $showAmount}
          손익 {formatSignedAmount(totalPnl, $currencyFilter === "KRW" ? ".KS" : "USD")}
        {:else}
          손익
        {/if}
      </span>
    </div>

    <div class="tab-bar" style="margin-bottom:16px">
      <button class={`tab-btn ${tab === "active" ? "active" : ""}`} on:click={() => (tab = "active")}>
        보유중 <span class="tab-count">{filteredPositions.length}</span>
      </button>
      <button class={`tab-btn ${tab === "closed" ? "active" : ""}`} on:click={() => (tab = "closed")}>
        이전 투자 <span class="tab-count">{filteredClosed.length}</span>
      </button>
    </div>

    {#if tab === "active"}
      <div class="table-wrap">
        <table class="data-table list-table">
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
              <tr><td colspan="5">불러오는 중...</td></tr>
            {:else if error}
              <tr><td colspan="5" class="error-text">{error}</td></tr>
            {:else if filteredPositions.length === 0}
              <tr><td colspan="5">보유중인 투자가 없습니다.</td></tr>
            {:else}
              {#each filteredPositions as pos}
                {@const totalAmount = getTotalAmount(pos)}
                <tr on:click={() => goTrade(pos.ticker)}>
                  <td>
                    <span class="ticker-badge">{pos.ticker}</span>
                    {#if $tickerNames[pos.ticker]}
                      <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>
                    {/if}
                  </td>
                  <td>{pos.shares}</td>
                  <td>{pos.avg_cost ? formatAmount(pos.avg_cost, pos.ticker) : "-"}</td>
                  <td>
                    {#if totalAmount !== null}
                      <span>{formatAmount(totalAmount, pos.ticker)}</span>
                      <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                        ({formatSignedAmount(pos.pnl, pos.ticker)})
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

      <div class="pos-card-list list-grid">
        {#if loading}
          <div class="pos-card list-row"><div class="pos-card-details">불러오는 중...</div></div>
        {:else if error}
          <div class="pos-card list-row"><div class="pos-card-details error-text">{error}</div></div>
        {:else if filteredPositions.length === 0}
          <div class="pos-card list-row"><div class="pos-card-details">보유중인 투자가 없습니다.</div></div>
        {:else}
          {#each filteredPositions as pos}
            {@const totalAmount = getTotalAmount(pos)}
            <div class="pos-card list-row" on:click={() => goTrade(pos.ticker)}>
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
                <span>보유 {pos.shares} · 1주 평균 {pos.avg_cost ? formatAmount(pos.avg_cost, pos.ticker) : "-"}</span>
                <span>
                  총 금액 {totalAmount !== null ? formatAmount(totalAmount, pos.ticker) : "-"}
                  <span class={pos.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                    ({formatSignedAmount(pos.pnl, pos.ticker)})
                  </span>
                </span>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {:else}
      <div class="pos-card-list list-grid">
        {#if loading}
          <div class="pos-card list-row"><div class="pos-card-details">불러오는 중...</div></div>
        {:else if filteredClosed.length === 0}
          <div class="pos-card list-row"><div class="pos-card-details">이전 투자가 없습니다.</div></div>
        {:else}
          {#each filteredClosed as cp}
            {@const days = holdingDays(cp.opened_at, cp.closed_at)}
            <div class="pos-card list-row" on:click={() => goTrade(cp.ticker)}>
              <div class="pos-card-top">
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                  <span class="ticker-badge">{cp.ticker}</span>
                  {#if $tickerNames[cp.ticker]}
                    <span class="ticker-tag">{$tickerNames[cp.ticker]}</span>
                  {/if}
                </div>
                <div style="display:flex;gap:6px;align-items:center">
                  <span class={`badge ${cp.outcome === "win" ? "badge-gain" : "badge-loss"}`}>
                    {cp.outcome === "win" ? "승" : "패"}
                  </span>
                  <span class={`return-badge ${cp.return_pct >= 0 ? "return-pos" : "return-neg"}`}>
                    {formatPercent(cp.return_pct)}
                  </span>
                </div>
              </div>
              <div class="pos-card-details">
                <span>
                  {cp.shares}주 · 평균 {cp.avg_cost ? formatAmount(cp.avg_cost, cp.ticker) : "-"}
                </span>
                <span style="color:var(--text-dim)">
                  {formatDate(cp.opened_at)} ~ {formatDate(cp.closed_at)}{days ? ` (${days}일)` : ""}
                </span>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</section>
