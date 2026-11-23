<script lang="ts">
  import { fetchPositionsMarket, fetchPositionsClosed, fetchMetrics, fetchPortfolioHoldings, fetchPortfolioClosedTickers } from "../lib/api/endpoints";
  import { formatAmount, formatSignedAmount, formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { currencyFilter, showAmount, matchesCurrency } from "../stores/currency";
  import { viewMode, portfolioRefreshTrigger } from "../stores/mode";

  type PositionMarket = {
    position_id: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number | null;
    return_pct: number | null;
  };

  type ClosedPosition = {
    position_id: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    return_pct: number | null;
    currency: string;
    outcome: string;
    opened_at: string | null;
    closed_at: string | null;
  };

  let loading = true;
  let error = "";
  let positions: PositionMarket[] = [];
  let closedPositions: ClosedPosition[] = [];
  let pnlByCurrency: Record<string, {total_unrealized_pnl: number | null}> = {};
  let requestId = 0;
  let tab: "active" | "closed" = "active";
  let portfolioHoldings: Array<{ ticker: string; shares: number; current_value_base?: number; allocation_pct?: number; currency?: string }> = [];
  let portfolioClosed: Array<{ ticker: string; last_trade_at?: string }> = [];
  let portfolioConfig: { base_currency?: string } | null = null;

  const tradeLink = (ticker: string, positionId?: number) => `#/trade/${encodeURIComponent(ticker.toLowerCase())}${positionId ? "?position=" + positionId : ""}`;

  const loadData = async () => {
    const current = ++requestId;
    loading = true;
    error = "";
    try {
      if ($viewMode === "portfolio") {
        const [holdingsRes, closedRes] = await Promise.all([
          fetchPortfolioHoldings(),
          fetchPortfolioClosedTickers(),
        ]);
        if (current !== requestId) return;
        const h = holdingsRes as { holdings?: Array<{ ticker: string; shares: number; current_value_base?: number; allocation_pct?: number; currency?: string }>; base_currency?: string };
        portfolioHoldings = h?.holdings ?? [];
        portfolioConfig = { base_currency: h?.base_currency };
        portfolioClosed = (closedRes as { items?: Array<{ ticker: string; last_trade_at?: string }> })?.items ?? [];
        positions = [];
        closedPositions = [];
        pnlByCurrency = {};
      } else {
        const [positionsRes, closedRes, metricsRes] = await Promise.all([
          fetchPositionsMarket(),
          fetchPositionsClosed(),
          fetchMetrics(),
        ]);
        if (current !== requestId) return;
        positions = (positionsRes as PositionMarket[]) || [];
        closedPositions = (closedRes as ClosedPosition[]) || [];
        pnlByCurrency = (metricsRes as { by_currency: typeof pnlByCurrency }).by_currency;
        portfolioHoldings = [];
        portfolioClosed = [];
      }
    } catch (err) {
      if (current !== requestId) return;
      error = formatErrorMessage(err, "투자를 불러오지 못했습니다.");
    } finally {
      if (current === requestId) loading = false;
    }
  };

  $: $viewMode, $portfolioRefreshTrigger, loadData();

  $: currencyPnl = pnlByCurrency?.[$currencyFilter]?.total_unrealized_pnl;

  const getTotalAmount = (pos: PositionMarket) =>
    pos.current_price != null ? pos.current_price * pos.shares : null;

  $: filteredPositions = positions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));
  $: filteredClosed = closedPositions.filter((p) => matchesCurrency(p.ticker, $currencyFilter));
  $: filteredPortfolioHoldings = portfolioHoldings.filter((h) => matchesCurrency(h.ticker, $currencyFilter));
  $: filteredPortfolioClosed = portfolioClosed.filter((c) => matchesCurrency(c.ticker, $currencyFilter));

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
      {#if $viewMode === "analysis" && $showAmount && !loading && !error && currencyPnl != null}
        <span class={`pnl-banner ${currencyPnl >= 0 ? "pnl-pos" : "pnl-neg"}`}>
          평가손익 {formatSignedAmount(currencyPnl, $currencyFilter === "KRW" ? ".KS" : "USD")}
        </span>
      {/if}
    </div>

    <div class="tab-bar" style="margin-bottom:16px">
      <button class={`tab-btn ${tab === "active" ? "active" : ""}`} on:click={() => (tab = "active")}>
        보유중 <span class="tab-count">{$viewMode === "portfolio" ? filteredPortfolioHoldings.length : filteredPositions.length}</span>
      </button>
      <button class={`tab-btn ${tab === "closed" ? "active" : ""}`} on:click={() => (tab = "closed")}>
        이전 투자 <span class="tab-count">{$viewMode === "portfolio" ? filteredPortfolioClosed.length : filteredClosed.length}</span>
      </button>
    </div>

    {#if tab === "active"}
      {#if $viewMode === "portfolio"}
        <div class="pos-card-list list-grid">
          {#if loading}
            <div class="pos-card list-row"><div class="pos-card-details">불러오는 중...</div></div>
          {:else if error}
            <div class="pos-card list-row"><div class="pos-card-details error-text">{error}</div></div>
          {:else if filteredPortfolioHoldings.length === 0}
            <div class="pos-card list-row"><div class="pos-card-details">보유중인 투자가 없습니다.</div></div>
          {:else}
            {#each filteredPortfolioHoldings as h}
              <a class="pos-card list-row" href={tradeLink(h.ticker)}>
                <div class="pos-card-top">
                  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                    <span class="ticker-badge">{h.ticker}</span>
                    {#if $tickerNames[h.ticker]}
                      <span class="ticker-tag">{$tickerNames[h.ticker]}</span>
                    {/if}
                  </div>
                  {#if h.allocation_pct != null}
                    <span class="return-badge return-pos">{h.allocation_pct.toFixed(1)}%</span>
                  {/if}
                </div>
                <div class="pos-card-details">
                  <span>보유 {h.shares}주</span>
                  <span>
                    {#if $showAmount && h.current_value_base != null}
                      {portfolioConfig?.base_currency === "USD"
                        ? `$${h.current_value_base.toLocaleString("en-US", { maximumFractionDigits: 2 })}`
                        : `₩${h.current_value_base.toLocaleString("ko-KR", { maximumFractionDigits: 0 })}`}
                    {/if}
                  </span>
                </div>
              </a>
            {/each}
          {/if}
        </div>
      {:else}
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
                <tr on:click={() => (window.location.hash = tradeLink(pos.ticker, pos.position_id))}>
                  <td>
                    <a href={tradeLink(pos.ticker, pos.position_id)} class="ticker-badge">{pos.ticker}</a>
                    {#if $tickerNames[pos.ticker]}
                      <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>
                    {/if}
                  </td>
                  <td>{pos.shares}</td>
                  <td>{pos.avg_cost ? formatAmount(pos.avg_cost, pos.ticker) : "-"}</td>
                  <td>
                    {#if totalAmount !== null}
                      <span>{formatAmount(totalAmount, pos.ticker)}</span>
                      <span class={(pos.pnl ?? 0) >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                        ({formatSignedAmount(pos.current_price == null || pos.avg_cost == null ? null : pos.pnl, pos.ticker)})
                      </span>
                    {:else}
                      -
                    {/if}
                  </td>
                  <td class={(pos.return_pct ?? 0) >= 0 ? "text-gain" : "text-loss"}>{formatPercent(pos.current_price == null || pos.avg_cost == null ? null : pos.return_pct)}</td>
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
            <a class="pos-card list-row" href={tradeLink(pos.ticker, pos.position_id)}>
              <div class="pos-card-top">
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                  <span class="ticker-badge">{pos.ticker}</span>
                  {#if $tickerNames[pos.ticker]}
                    <span class="ticker-tag">{$tickerNames[pos.ticker]}</span>
                  {/if}
                </div>
                <span class={`return-badge ${(pos.return_pct ?? 0) >= 0 ? "return-pos" : "return-neg"}`}>
                  {formatPercent(pos.current_price == null || pos.avg_cost == null ? null : pos.return_pct)}
                </span>
              </div>
              <div class="pos-card-details">
                <span>보유 {pos.shares} · 1주 평균 {pos.avg_cost ? formatAmount(pos.avg_cost, pos.ticker) : "-"}</span>
                <span>
                  총 금액 {totalAmount !== null ? formatAmount(totalAmount, pos.ticker) : "-"}
                  <span class={(pos.pnl ?? 0) >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                    ({formatSignedAmount(pos.current_price == null || pos.avg_cost == null ? null : pos.pnl, pos.ticker)})
                  </span>
                </span>
              </div>
            </a>
          {/each}
        {/if}
      </div>
      {/if}
    {:else}
      <div class="pos-card-list list-grid">
        {#if loading}
          <div class="pos-card list-row"><div class="pos-card-details">불러오는 중...</div></div>
        {:else if error}
          <div class="pos-card list-row"><div class="pos-card-details error-text">{error}</div></div>
        {:else if $viewMode === "portfolio"}
          {#if filteredPortfolioClosed.length === 0}
            <div class="pos-card list-row"><div class="pos-card-details">이전 투자가 없습니다.</div></div>
          {:else}
            {#each filteredPortfolioClosed as c}
              <a class="pos-card list-row" href={tradeLink(c.ticker)}>
                <div class="pos-card-top">
                  <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                    <span class="ticker-badge">{c.ticker}</span>
                    {#if $tickerNames[c.ticker]}
                      <span class="ticker-tag">{$tickerNames[c.ticker]}</span>
                    {/if}
                  </div>
                  <span class="badge badge-muted">종료</span>
                </div>
                <div class="pos-card-details">
                  <span style="color:var(--text-dim)">
                    {c.last_trade_at ? formatDate(c.last_trade_at) : ""}
                  </span>
                </div>
              </a>
            {/each}
          {/if}
        {:else if filteredClosed.length === 0}
          <div class="pos-card list-row"><div class="pos-card-details">이전 투자가 없습니다.</div></div>
        {:else}
          {#each filteredClosed as cp}
            {@const days = holdingDays(cp.opened_at, cp.closed_at)}
            <a class="pos-card list-row" href={tradeLink(cp.ticker, cp.position_id)}>
              <div class="pos-card-top">
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                  <span class="ticker-badge">{cp.ticker}</span>
                  {#if $tickerNames[cp.ticker]}
                    <span class="ticker-tag">{$tickerNames[cp.ticker]}</span>
                  {/if}
                </div>
                <div style="display:flex;gap:6px;align-items:center">
                  <span class={`badge ${cp.outcome === "win" ? "badge-gain" : cp.outcome === "loss" ? "badge-loss" : ""}`}>
                    {cp.outcome === "win" ? "승" : cp.outcome === "loss" ? "패" : "체결 기록 불완전"}
                  </span>
                  <span class={`return-badge ${cp.return_pct == null ? "" : cp.return_pct >= 0 ? "return-pos" : "return-neg"}`}>
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
            </a>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</section>
