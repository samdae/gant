<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import RefreshButton from "./RefreshButton.svelte";
  import { onDestroy, onMount } from "svelte";
  import {
    researchGet,
    probability,
    type CaseRow,
  } from "../lib/researchEvidence";
  import { currencyFilter } from "../stores/currency";
  import { instrumentName, tickerNames } from "../stores/tickerNames";
  import InstrumentLabel from "./InstrumentLabel.svelte";

  export let query = "";
  type ForecastTicker = Pick<CaseRow, "id" | "ticker" | "market" | "data_session" | "forecast_probabilities">;
  let rows: ForecastTicker[] = [];
  let busy = true, error = false;
  let current: AbortController;
  $: market =
    $currencyFilter === "USD" ? "us" : $currencyFilter === "KRW" ? "kr" : "";
  $: needle = query.trim().toLowerCase();
  $: visible = rows.filter((row) => (!market || row.market === market) &&
    [row.ticker, instrumentName(row.ticker, $tickerNames)].some((value) =>
      value.toLowerCase().includes(needle),
    ),
  );

  async function load(refresh = false) {
    current?.abort();
    const req = new AbortController();
    current = req;
    busy = true;
    error = false;
    try {
      const data = await researchGet<ForecastTicker[]>("forecast-tickers", req.signal, { refresh });
      if (!req.signal.aborted) rows = data;
    } catch {
      if (!req.signal.aborted) error = true;
    } finally {
      if (!req.signal.aborted) busy = false;
    }
  }
  onMount(() => { load(); });
  onDestroy(() => current?.abort());
</script>

<section class="forecast-reports" aria-label="확률 예측 리포트">
  <header class="forecast-heading">
    <h3>확률 예측</h3>
    <RefreshButton label="확률 예측 새로고침" {busy} on:click={() => load(true)} />
  </header>
  {#if visible.length}
    <div class="list-columns" aria-hidden="true">
      <span>회사 · 최근 예측</span><span>상승 확률</span><span>관측일</span>
    </div>
  {/if}
  {#each visible as row (row.id)}
    <a href={"#/research/" + row.id}>
      <span class="subject"
        ><InstrumentLabel ticker={row.ticker} /><small
          >{row.market === "kr" ? "한국" : "미국"} · 사례 #{row.id}</small
        ></span
      >
      <span class="figure"
        ><small>단일 모델 상승 확률</small><strong
          >{probability(row.forecast_probabilities?.single)}</strong
        ></span
      >
      <span class="day"
        ><small>관측일</small><time>{row.data_session}</time></span
      >
    </a>
  {/each}
  {#if error}<p role="alert">
      {rows.length ? "예측 목록을 갱신하지 못했습니다. 마지막 조회 결과입니다." : "예측 목록을 불러오지 못했습니다."}
      <button on:click={() => load(true)}>다시 조회</button
      >
    </p>
  {:else if !visible.length}<p role="status">
      {#if busy}<PendingState label="확률 예측 조회 중"/>{:else}{needle
          ? "조회한 예측에서 일치하는 종목이 없습니다."
          : "발행된 확률 예측이 없습니다."}{/if}
    </p>{/if}
</section>

<style>
  .list-columns {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(7rem, 0.5fr) minmax(
        6rem,
        0.45fr
      );
    gap: 0.75rem;
    padding: 0.45rem 1rem;
    background: var(--fl-surface-subtle, #27282b);
    color: var(--fl-muted, #b5b4ad);
    font-size: 0.8rem;
  }
  .subject {
    display: grid;
    gap: 0.25rem;
  }
  @media (max-width: 520px) {
    .list-columns {
      display: none;
    }
  }
  .forecast-reports {
    margin-block: 1rem 1.5rem;
    border: 1px solid var(--fl-line, #3b3d41);
    border-radius: 0.25rem;
    overflow: hidden;
    background: var(--fl-surface, #202124);
  }
  .forecast-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: .75rem;
    padding: .2rem .45rem .2rem 1rem;
  }
  h3 {
    margin: 0;
    font-size: 1.08rem;
  }
  a {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(7rem, 0.5fr) minmax(
        6rem,
        0.45fr
      );
    align-items: center;
    gap: 0.75rem;
    padding: 0.85rem 1rem;
    border-top: 1px solid var(--fl-line, #3b3d41);
    text-decoration: none;
    color: var(--fl-ink, #f4f2e9);
  }
  a:hover,
  a:focus-visible {
    background: var(--fl-surface-subtle, #27282b);
  }
  small {
    display: block;
    color: var(--fl-muted, #b5b4ad);
    font-size: 0.77rem;
  }
  .figure small,
  .day small {
    display: none;
  }
  @media (max-width: 520px) {
    .figure small,
    .day small {
      display: block;
    }
  }
  .figure strong {
    font-size: clamp(1.15rem, 2vw, 1.55rem);
    letter-spacing: -0.025em;
    line-height: 1.3;
  }
  @media (min-width: 521px) {
    .figure,
    .day,
    .list-columns span:not(:first-child) {
      text-align: right;
    }
  }
  .figure,
  .day {
    font-variant-numeric: tabular-nums;
  }
  strong {
    color: var(--fl-forecast, #c3a9ff);
  }
  p,
  button {
    margin: 0.5rem 1rem 1rem;
  }
  @media (max-width: 520px) {
    a {
      grid-template-columns: minmax(0, 1fr) auto;
    }
    .day {
      grid-column: 1 / -1;
      font-size: 0.8rem;
      color: var(--fl-muted, #b5b4ad);
    }
    .day small {
      display: inline;
      margin-right: 0.35rem;
    }
  }
</style>
