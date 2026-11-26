<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import { researchGet, type CaseRow } from "../lib/researchEvidence";
  import { isPublicViewer } from "../lib/workspace";
  import SelectMenu from "./SelectMenu.svelte";
  import PendingState from "./PendingState.svelte";

  export let ticker: string;
  export let caseId: number;
  export let session: string;
  export let published: boolean;
  const dispatch = createEventDispatcher<{ change: number }>();
  type Round = Pick<CaseRow, "id" | "data_session">;
  let rounds: Round[] = [];
  let request: AbortController;
  let loading = true, error = false;
  let recheckedId: number | undefined;
  $: load(ticker);
  // A directly opened or refreshed case can be newer than a cached ticker page.
  $: if (published && !loading && !error && !rounds.some(row => row.id === caseId) && recheckedId !== caseId) {
    recheckedId = caseId;
    load(ticker, true);
  }
  $: options = rounds.map((row, index) => ({
    value: String(row.id), label: (rounds.length - index) + "회차 · " + row.data_session,
  }));

  async function load(symbol: string, refresh = false) {
    request?.abort();
    const controller = new AbortController();
    request = controller;
    rounds = [];
    loading = true;
    error = false;
    const size = 200;
    const query = new URLSearchParams({ ticker: symbol, limit: String(size) });
    if (!isPublicViewer) query.set("published_only", "true");
    const all: Round[] = [];
    let before = Infinity;
    try {
      while (true) {
        const page = await researchGet<CaseRow[]>("cases?" + query, controller.signal, { refresh });
        if (controller.signal.aborted) return;
        for (const row of page) {
          if (row.ticker !== symbol || !Number.isSafeInteger(row.id) || row.id <= 0 || row.id >= before)
            throw new Error("Invalid ticker history");
          all.push({ id: row.id, data_session: row.data_session });
          before = row.id;
        }
        if (page.length < size) break;
        query.set("before_id", String(before));
      }
      rounds = all.sort((a, b) => b.data_session.localeCompare(a.data_session) || b.id - a.id);
    } catch {
      if (!controller.signal.aborted) error = true;
    } finally {
      if (!controller.signal.aborted) loading = false;
    }
  }

  onDestroy(() => request?.abort());
</script>

<div class="forecast-rounds">
  <label for="forecast-round">예측 회차</label>
  {#if error}
    <span role="alert">회차 조회 실패</span><button on:click={() => load(ticker, true)}>다시 조회</button>
  {:else}
    <SelectMenu id="forecast-round" ariaLabel="예측 회차" value={String(caseId)} {options}
      placeholder={session + " · 관측 사례"} on:change={e => dispatch("change", Number(e.detail))} />
    {#if loading}<PendingState label="종목의 예측 회차 조회 중" />{/if}
  {/if}
</div>

<style>
  .forecast-rounds {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    grid-column: 1 / -1;
    gap: .5rem .75rem;
    margin-top: .45rem;
    color: var(--fl-muted);
    font-size: .82rem;
  }
  label { font-weight: 650; }
</style>
