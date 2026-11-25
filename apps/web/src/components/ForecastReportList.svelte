<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import { onDestroy, onMount } from "svelte";
  import { isPublicViewer } from "../lib/workspace";
  import {
    researchGet,
    probability,
    type CaseRow,
  } from "../lib/researchEvidence";
  import { currencyFilter } from "../stores/currency";
  import { instrumentName, tickerNames } from "../stores/tickerNames";
  import InstrumentLabel from "./InstrumentLabel.svelte";

  export let query = "";
  let rows: CaseRow[] = [];
  let busy = true,
    error = false,
    more = false,
    mounted = false;
  let current: AbortController;
  const size = 20;
  $: market =
    $currencyFilter === "USD" ? "us" : $currencyFilter === "KRW" ? "kr" : "";
  $: if (mounted) load(market);
  $: needle = query.trim().toLowerCase();
  $: visible = rows.filter((row) =>
    [row.ticker, instrumentName(row.ticker, $tickerNames)].some((value) =>
      value.toLowerCase().includes(needle),
    ),
  );

  async function load(region: string, before?: number) {
    current?.abort();
    const req = new AbortController();
    current = req;
    busy = true;
    error = false;
    if (!before) {
      rows = [];
      more = false;
    }
    const params = new URLSearchParams({ limit: String(size + 1) });
    if (!isPublicViewer) params.set("published_only", "true");
    if (region) params.set("market", region);
    if (before) params.set("before_id", String(before));
    try {
      const data = await researchGet<CaseRow[]>("cases?" + params, req.signal);
      if (req.signal.aborted) return;
      rows = [...rows, ...data.slice(0, size)];
      more = data.length > size;
    } catch {
      if (!req.signal.aborted) error = true;
    } finally {
      if (!req.signal.aborted) busy = false;
    }
  }
  onMount(() => {
    mounted = true;
  });
  onDestroy(() => current?.abort());
</script>

<section class="forecast-reports" aria-label="확률 예측 리포트">
  <h3>확률 예측</h3>
  {#if visible.length}
    <div class="list-columns" aria-hidden="true">
      <span>회사 · 사례</span><span>상승 확률</span><span>관측일</span>
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
      예측 목록을 불러오지 못했습니다. <button
        on:click={() => load(market, rows.at(-1)?.id)}>다시 조회</button
      >
    </p>
  {:else if !visible.length}<p role="status">
      {#if busy}<PendingState label="확률 예측 조회 중"/>{:else}{needle
          ? "조회한 예측에서 일치하는 종목이 없습니다."
          : "발행된 확률 예측이 없습니다."}{/if}
    </p>{/if}
  {#if more && !error}<button
      disabled={busy}
      on:click={() => load(market, rows[rows.length - 1].id)}
      >{#if busy}<PendingState label="이전 예측 조회 중" />{:else}이전 예측 더 보기{/if}</button
    >{/if}
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
  h3 {
    margin: 0;
    padding: 0.9rem 1rem;
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
