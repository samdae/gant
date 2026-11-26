<script lang="ts">
  import DecisionBadge from "./DecisionBadge.svelte";
  import { formatDateTime } from "../lib/utils/format";

  type Fill = {
    action: string;
    shares: number;
    price: number;
    currency: string;
    executed_at: string;
  };
  export let report: {
    stored_decision_position?: string | null;
    decision_position?: string | null;
    portfolio_action?: string | null;
    portfolio_shares?: number | null;
    execution_trades?: Fill[];
  };
  const shareCount = new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 });
  $: analysis = report.stored_decision_position === undefined
    ? report.decision_position : report.stored_decision_position;
</script>

<span class="evidence">
  <span class="fact"><span class="label">분석 판단</span><DecisionBadge value={analysis || ""} /></span>
  <span class="fact">
    <span class="label">실행 제안</span><DecisionBadge value={report.portfolio_action || ""} />
    {#if report.portfolio_shares != null}<span>{shareCount.format(report.portfolio_shares)}주</span>{/if}
  </span>
  <span class="fact fills">
    <span class="label">종목 계좌 체결</span>
    {#if !Array.isArray(report.execution_trades)}<span>기록 미확인</span>
    {:else if !report.execution_trades.length}<span>연결된 체결 기록 없음</span>
    {:else}
      {#each report.execution_trades as fill}
        <span class="fill"><DecisionBadge value={fill.action} />
          {shareCount.format(fill.shares)}주 · {fill.price.toLocaleString(undefined, { maximumSignificantDigits: 12 })} {fill.currency}
          <time datetime={fill.executed_at}>{formatDateTime(fill.executed_at)}</time>
        </span>
      {/each}
    {/if}
  </span>
</span>

<style>
  .evidence { display:grid; grid-template-columns:minmax(5rem,1fr) minmax(6rem,1fr) minmax(9rem,1.6fr); gap:14px; width:100%; min-width:0; }
  .fact { display:flex; flex-wrap:wrap; gap:6px; align-content:start; align-items:center; color:var(--fl-ink); font-size:.88rem; }
  .label { width:100%; color:var(--fl-muted); font-size:.79rem; font-weight:600; }
  .fill { display:flex; flex-wrap:wrap; align-items:center; gap:4px; font-variant-numeric:tabular-nums; }
  time { color:var(--fl-muted); }
  @media(max-width:550px) { .evidence { grid-template-columns:1fr 1fr; } .fills { grid-column:1/-1; } }
</style>
