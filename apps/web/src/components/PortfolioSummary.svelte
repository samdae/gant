<script lang="ts">
  import { formatPercent } from "../lib/utils/format";

  export let config: { total_fund?: number; available_cash?: number; initial_capital?: number; base_currency?: string } | null;
  $: currency = config?.base_currency;
  $: money = currency && ["USD", "KRW"].includes(currency)
    ? new Intl.NumberFormat("ko-KR", { style: "currency", currency, maximumFractionDigits: currency === "KRW" ? 0 : 2 })
    : null;
  $: rate = config?.total_fund != null && config.initial_capital != null && config.initial_capital > 0
    ? 100 * (config.total_fund / config.initial_capital - 1) : null;
</script>

<section class="account desk-panel" aria-label="계좌 요약">
  <header><h3>모의 계좌 잔액</h3>{#if currency}<span>기준 통화 {currency}</span>{/if}</header>
  <dl>
    <div class="balance"><dt>총자산</dt><dd>{config?.total_fund != null && money ? money.format(config.total_fund) : "—"}</dd></div>
    <div><dt>총 수익률</dt><dd class:text-gain={rate != null && rate > 0} class:text-loss={rate != null && rate < 0}>{rate != null ? formatPercent(rate) : "—"}</dd></div>
    <div><dt>가용 현금</dt><dd>{config?.available_cash != null && money ? money.format(config.available_cash) : "—"}</dd></div>
  </dl>
</section>

<style>
  .account { grid-column: 1 / -1; padding: clamp(14px, 2vw, 24px); }
  header { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }
  header span, dt { color: var(--fl-muted); font-size: .82rem; }
  dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr)); gap: 15px; margin: 16px 0 0; }
  .balance dd {font-size:clamp(1.65rem,3vw,2.4rem); color:var(--fl-ink, #f4f2e9);}
  dd { margin: 3px 0 0; font-size: clamp(1.25rem, 2vw, 1.8rem); font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
</style>
