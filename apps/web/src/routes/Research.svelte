<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { location } from "svelte-spa-router";
  import {
    marketName,
    probability,
    researchGet,
    caseListStatus,
    type CaseRow,
    type ResearchCase,
  } from "../lib/researchEvidence";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import ResearchEvidence from "../components/ResearchEvidence.svelte";
  import { instrumentText, tickerNames } from "../stores/tickerNames";

  let rows: CaseRow[] = [],
    selected: ResearchCase | null = null,
    market = "",
    busy = true,
    detailBusy = true,
    more = false;
  let listError = "",
    detailError = "",
    mounted = false;
  let listRequest: AbortController, detailRequest: AbortController;
  let viewer: HTMLIFrameElement,
    height = 1,
    observer: ResizeObserver;
  const size = 8;
  $: archive = ["/results", "/performance"].includes($location);
  $: explicit = $location.match(/^\/research\/([1-9]\d*)$/)?.[1];
  $: selectedId = explicit ? Number(explicit) : rows[0]?.id;
  $: if (mounted && !archive) loadList(market);
  $: if (mounted && !archive) loadCase(selectedId);

  async function loadList(region: string, before?: number) {
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
      if (before) query.set("before_id", String(before));
      const items = await researchGet<CaseRow[]>("cases?" + query, req.signal);
      if (req.signal.aborted) return;
      more = items.length > size;
      rows = [...(before ? rows : []), ...items.slice(0, size)];
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
  function fitViewer() {
    observer?.disconnect();
    const body = viewer.contentDocument?.body;
    if (!body) return;
    const measure = () =>
      (height = Math.ceil(body.getBoundingClientRect().height));
    measure();
    observer = new ResizeObserver(measure);
    observer.observe(body);
  }
  function filter(region: string) {
    if (explicit) window.location.hash = "#/research";
    market = region;
  }
  onMount(() => {
    mounted = true;
  });
  onDestroy(() => {
    listRequest?.abort();
    detailRequest?.abort();
    observer?.disconnect();
  });
</script>

<div class="research-desk">
  <header class="desk-header">
    <div>
      <h1>예측 연구</h1>
      <p>발행 당시의 근거와 5거래일 뒤의 결과를 확인합니다.</p>
    </div>
    <nav aria-label="연구 보기">
      <a
        class:active={!archive}
        aria-current={!archive ? "page" : undefined}
        href="#/research">사례 탐색</a
      ><a
        class:active={archive}
        aria-current={archive ? "page" : undefined}
        href="#/results">성과 분석</a
      >
    </nav>
  </header>
  {#if archive}
    <iframe
      bind:this={viewer}
      title="연구 성과와 관측 현황"
      src="/research/?embedded=1#results"
      style:height={height + "px"}
      on:load={fitViewer}
    ></iframe>
  {:else}
    <div class="workarea">
      <aside aria-label="연구 사례 목록">
        <div class="list-head">
          <h2>관측 사례</h2>
          <select
            value={market}
            aria-label="시장 선택"
            on:change={(e) => filter(e.currentTarget.value)}
            ><option value="">전체 시장</option><option value="kr">한국</option
            ><option value="us">미국</option></select
          >
        </div>
        {#if listError}<p role="alert">
            {listError}
            <button on:click={() => loadList(market)}>다시 조회</button>
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
                (window.location.hash = "#/research/" + e.currentTarget.value)}
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
          <div class="register">
            {#each rows as row (row.id)}
              <a
                href={"#/research/" + row.id}
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
          {#if more}<button
              class="older"
              disabled={busy}
              on:click={() => loadList(market, rows[rows.length - 1].id)}
              >{busy ? "조회 중" : "이전 사례 더 보기"}</button
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
    max-width: var(--content-max);
    padding: var(--content-top) var(--content-gutter) 48px;
    margin: 0 auto;
    color: #182e38;
  }
  .desk-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 12px 18px;
    padding-bottom: 18px;
    border-bottom: 1px solid #c8d4d5;
    margin-bottom: 20px;
  }
  h1,
  h2,
  p {
    margin: 0;
  }
  h1 {
    font-size: clamp(1.65rem, 3vw, 2.2rem);
    font-weight: 730;
    letter-spacing: -0.055em;
    line-height: 1.25;
  }
  h2 {
    font-size: 1.03rem;
    letter-spacing: -0.03em;
  }
  .desk-header p,
  aside > p,
  .blank p {
    font-size: 0.89rem;
    color: #516571;
    margin-top: 6px;
  }
  nav {
    display: flex;
    gap: 4px;
    border: 1px solid #cbd8d8;
    padding: 3px;
    border-radius: 7px;
    background: white;
  }
  nav a {
    padding: 6px 12px;
    font-size: 0.86rem;
    border-radius: 4px;
    color: #405660;
  }
  nav a.active {
    background: #204d47;
    color: white;
  }
  .workarea {
    display: grid;
    grid-template-columns: minmax(215px, 0.36fr) minmax(0, 1fr);
    gap: clamp(16px, 2.6vw, 32px);
    align-items: start;
  }
  aside,
  .detail-pane {
    min-width: 0;
  }
  .list-head,
  .row-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 7px;
  }
  .list-head {
    margin-bottom: 11px;
  }
  .list-head select,
  .mobile-picker select,
  button {
    background: white;
    color: #263d46;
    font: inherit;
    font-size: 0.84rem;
    border: 1px solid #b9c9c9;
    border-radius: 5px;
    padding: 5px 8px;
    max-width: 100%;
  }
  .register {
    border-block: 1px solid #c8d4d5;
  }
  .register a {
    display: grid;
    gap: 5px;
    border-bottom: 1px solid #d6dfdf;
    border-left: 3px solid transparent;
    padding: 12px;
    background: white;
    font-size: 1rem;
    overflow-wrap: anywhere;
  }
  .register a:last-child {
    border-bottom: 0;
  }
  .register a.selected {
    border-left-color: #24755e;
    background: #eaf4ef;
  }
  .register a:hover {
    background: #f0f5f3;
  }
  .row-meta {
    font-size: 0.76rem;
    color: #4a6068;
    flex-wrap: wrap;
  }
  .older {
    margin-top: 10px;
    width: 100%;
    min-height: 36px;
  }
  .mobile-picker {
    display: none;
  }
  .blank {
    padding: clamp(20px, 4vw, 40px);
    border-block: 1px solid #ced9da;
    background: #fff;
  }
  iframe {
    display: block;
    width: 100%;
    border: 0;
  }
  @media (max-width: 900px) {
    .workarea {
      grid-template-columns: minmax(190px, 0.38fr) minmax(0, 1fr);
    }
  }
  @media (max-width: 720px) {
    .workarea {
      grid-template-columns: minmax(0, 1fr);
      gap: 16px;
    }
    .register {
      display: none;
    }
    .mobile-picker {
      display: grid;
      gap: 4px;
      color: #526675;
      font-size: 0.8rem;
    }
    .mobile-picker select {
      width: 100%;
      min-height: 40px;
    }
    .desk-header {
      align-items: start;
    }
    .list-head {
      margin-bottom: 6px;
    }
    .older {
      width: auto;
    }
    .research-desk {
      padding-inline: 14px;
    }
  }
</style>
