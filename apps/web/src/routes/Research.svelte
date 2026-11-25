<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { location, querystring } from "svelte-spa-router";
  import {
    marketName,
    probability,
    researchGet,
    caseListStatus,
    type CaseRow,
    type ResearchCase,
  } from "../lib/researchEvidence";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import ResearchReview from "../components/ResearchReview.svelte";
  import ResearchEvidence from "../components/ResearchEvidence.svelte";
  import { instrumentText, tickerNames } from "../stores/tickerNames";

  const initial = new URLSearchParams(
    window.location.hash.split("?")[1] || window.location.search,
  );
  let from = initial.get("from_date") || "",
    to = initial.get("to_date") || "";
  let draftFrom = from,
    draftTo = to,
    filterError = "";
  let cursors: (number | undefined)[] = [undefined];
  $: filterQuery = new URLSearchParams(
    Object.fromEntries(
      Object.entries({ market, from_date: from, to_date: to }).filter(
        ([, v]) => v,
      ),
    ),
  ).toString();
  $: suffix = filterQuery ? "?" + filterQuery : "";
  let rows: CaseRow[] = [],
    selected: ResearchCase | null = null,
    market = initial.get("market") || "",
    busy = true,
    detailBusy = true,
    more = false;
  let listError = "",
    detailError = "",
    mounted = false;
  let listRequest: AbortController, detailRequest: AbortController;
  const size = 8;
  $: archive = ["/results", "/performance", "/observe"].includes($location);
  $: explicit = $location.match(/^\/research\/([1-9]\d*)$/)?.[1];
  $: selectedId = explicit ? Number(explicit) : rows[0]?.id;
  $: if (mounted && !archive)
    loadList(market, from, to, cursors[cursors.length - 1]);
  $: if (mounted && !archive) loadCase(selectedId);

  async function loadList(
    region: string,
    start: string,
    end: string,
    before?: number,
  ) {
    listRequest?.abort();
    const req = new AbortController();
    listRequest = req;
    busy = true;
    listError = "";
    if (!before) {
      rows = [];
      more = false;
    }
    try {
      const query = new URLSearchParams({ limit: String(size + 1) });
      if (region) query.set("market", region);
      if (start) query.set("from_date", start);
      if (end) query.set("to_date", end);
      if (before) query.set("before_id", String(before));
      const items = await researchGet<CaseRow[]>("cases?" + query, req.signal);
      if (req.signal.aborted) return;
      more = items.length > size;
      rows = items.slice(0, size);
    } catch (e) {
      if (!req.signal.aborted) listError = "사례 목록을 불러오지 못했습니다.";
    } finally {
      if (!req.signal.aborted) busy = false;
    }
  }
  async function loadCase(id?: number) {
    detailRequest?.abort();
    const req = new AbortController();
    detailRequest = req;
    selected = null;
    detailError = "";
    detailBusy = Boolean(id);
    if (!id) return;
    try {
      const item = await researchGet<ResearchCase>("cases/" + id, req.signal);
      if (!req.signal.aborted) selected = item;
    } catch (e) {
      if (!req.signal.aborted)
        detailError = e instanceof Error ? e.message : "사례 조회 실패";
    } finally {
      if (!req.signal.aborted) detailBusy = false;
    }
  }
  function restoreFilter(query: string) {
    const params = new URLSearchParams(query);
    const region = params.get("market") || "";
    const start = params.get("from_date") || "";
    const end = params.get("to_date") || "";
    if (market === region && from === start && to === end) return;
    market = region;
    draftFrom = from = start;
    draftTo = to = end;
    cursors = [undefined];
    filterError = "";
  }
  $: if (mounted && !archive) restoreFilter($querystring || "");

  function filter(region: string) {
    if (draftFrom && draftTo && draftFrom > draftTo) {
      filterError = "시작일을 종료일보다 앞서 선택하세요.";
      return;
    }
    filterError = "";
    from = draftFrom;
    to = draftTo;
    market = region;
    cursors = [undefined];
    const params = new URLSearchParams(
      Object.fromEntries(
        Object.entries({ market, from_date: from, to_date: to }).filter(
          ([, v]) => v,
        ),
      ),
    );
    window.location.hash = "#/research" + (params.size ? "?" + params : "");
  }
  onMount(() => {
    mounted = true;
  });
  onDestroy(() => {
    listRequest?.abort();
    detailRequest?.abort();
  });
</script>

<div class="research-desk">
  {#if archive}
    <ResearchReview view={$location === "/observe" ? "observe" : "results"} />
  {:else}
    <div class="workarea">
      <aside aria-label="연구 사례 목록">
        <div class="filters">
          <label
            >시장<select
              value={market}
              on:change={(e) => filter(e.currentTarget.value)}
              ><option value="">전체 시장</option><option value="kr"
                >한국</option
              ><option value="us">미국</option></select
            ></label
          >
          <details class="date-filter">
            <summary>관측일 범위</summary>
            <form on:submit|preventDefault={() => filter(market)}>
              <label>시작일<input type="date" bind:value={draftFrom} /></label
              ><label>종료일<input type="date" bind:value={draftTo} /></label>
              <button>적용</button><button
                type="button"
                on:click={() => {
                  draftFrom = "";
                  draftTo = "";
                  filter(market);
                }}>초기화</button
              >
              {#if filterError}<span role="alert">{filterError}</span>{/if}
            </form>
          </details>
        </div>
        {#if listError}<p role="alert">
            {listError}
            <button
              on:click={() =>
                loadList(market, from, to, cursors[cursors.length - 1])}
              >다시 조회</button
            >
          </p>
        {:else if !rows.length}<p role="status">
            {busy
              ? "사례를 불러오는 중입니다."
              : "이 시장에 공개된 연구 사례가 없습니다."}
          </p>{/if}
        {#if rows.length}
          <label class="mobile-picker"
            >관측일·종목 선택
            <select
              value={selectedId}
              on:change={(e) =>
                (window.location.hash =
                  "#/research/" + e.currentTarget.value + suffix)}
            >
              {#if explicit && !rows.some((r) => r.id === selectedId)}<option
                  value={selectedId}
                  >{selected
                    ? instrumentText(selected.ticker, $tickerNames)
                    : "선택 사례"}</option
                >{/if}
              {#each rows as row}<option value={row.id}
                  >{row.data_session} · {instrumentText(
                    row.ticker,
                    $tickerNames,
                  )}</option
                >{/each}
            </select>
          </label>
          <details class="archive-list">
            <summary>사례 목록 · {rows.length}건</summary>
            <div class="register">
              {#each rows as row (row.id)}
                <a
                  href={"#/research/" + row.id + suffix}
                  class:selected={selectedId === row.id}
                  aria-current={selectedId === row.id ? "true" : undefined}
                >
                  <div class="row-meta">
                    <time>{row.data_session}</time><span
                      >{marketName(row.market)}</span
                    >
                  </div>
                  <InstrumentLabel ticker={row.ticker} />
                  <div class="row-meta">
                    <span
                      >단일 모델 {probability(
                        row.forecast_probabilities?.single,
                      )}</span
                    ><span>{caseListStatus(row)}</span>
                  </div>
                </a>
              {/each}
            </div>
          </details>
          {#if cursors.length > 1}<button
              class="older"
              on:click={() => {
                cursors = cursors.slice(0, -1);
                window.location.hash = "#/research" + suffix;
              }}>이전 페이지</button
            >{/if}
          {#if more}<button
              class="older"
              disabled={busy}
              on:click={() => {
                cursors = [...cursors, rows[rows.length - 1].id];
                window.location.hash = "#/research" + suffix;
              }}>{busy ? "조회 중" : "다음 페이지"}</button
            >{/if}
        {/if}
      </aside>
      <div class="detail-pane">
        {#if detailBusy}<p role="status">사례 근거를 불러오는 중입니다.</p>
        {:else if detailError}<p role="alert">
            {detailError}
            <button on:click={() => loadCase(selectedId)}>다시 조회</button>
          </p>
        {:else if selected}<ResearchEvidence data={selected} />
        {:else if !busy && !listError}<section class="blank">
            <h2>아직 관측 사례가 없습니다</h2>
            <p>
              사례가 동결되면 당시 가격과 발행 확률을 여기서 확인할 수 있습니다.
            </p>
          </section>{/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .research-desk {
    width: 100%;
    max-width: 1380px;
    margin: auto;
    padding: clamp(14px, 2.2vw, 28px) clamp(16px, 3.4vw, 48px) 48px;
    color: #282521;
  }
  aside {
    display: flex;
    align-items: baseline;
    gap: 7px 15px;
    flex-wrap: wrap;
    padding: 10px 0 12px;
  }
  .filters,
  .filters form,
  .filters label,
  .mobile-picker {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .filters {
    flex-wrap: wrap;
  }
  .filters label,
  .mobile-picker,
  .date-filter summary,
  .archive-list summary,
  .older {
    color: #5e574f;
    font-size: 0.78rem;
  }
  .filters select,
  .filters input,
  .mobile-picker select,
  button {
    font: inherit;
    background: #fff;
    color: #3b342e;
    border: 1px solid #cfc7bc;
    border-radius: 4px;
    padding: 5px 8px;
    max-width: 100%;
  }
  button,
  summary {
    cursor: pointer;
  }
  .date-filter[open] form {
    padding: 6px 0;
    flex-wrap: wrap;
  }
  .register {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1px;
    background: #ddd6cb;
    border: 1px solid #ddd6cb;
  }
  .register a {
    padding: 10px;
    background: white;
  }
  .register a.selected {
    background: #f6eaf0;
  }
  .archive-list[open] {
    flex: 1 0 100%;
  }
  .row-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #655d54;
    gap: 6px;
  }
  .detail-pane {
    min-width: 0;
    background: #fff;
    padding: 0 clamp(12px, 2.4vw, 30px);
  }
  .blank {
    padding: 15px;
  }
  .blank h2,
  .blank p {
    margin: 4px 0;
  }
  .mobile-picker select {
    min-width: 0;
  }
  @media (max-width: 620px) {
    .research-desk {
      padding-inline: 14px;
    }
    .detail-pane {
      padding: 0 10px;
    }
    .mobile-picker {
      flex: 1 0 100%;
      align-items: baseline;
    }
    .mobile-picker select {
      flex: 1;
    }
    .filters form {
      max-width: 100%;
    }
    aside {
      gap: 6px 10px;
    }
  }
</style>
