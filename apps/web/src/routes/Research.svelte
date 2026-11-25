<script context="module" lang="ts">
  // The router remounts this view when a filtered detail URL becomes the list URL.
  let reopenForFilter: { hash: string; control: "market" | "date" } | null =
    null;
</script>

<script lang="ts">
  import { onDestroy, onMount, tick } from "svelte";
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
  import ResearchFilters from "../components/ResearchFilters.svelte";
  import ResearchReview from "../components/ResearchReview.svelte";
  import ResearchEvidence from "../components/ResearchEvidence.svelte";

  import { readResearchFilters } from "../lib/researchDates";
  let market = "",
    from = "",
    to = "";
  let pagination: { query: string; cursors: (number | undefined)[] } = {
    query: "",
    cursors: [undefined],
  };
  $: ({ market, from, to } = readResearchFilters($querystring || ""));
  $: filterQuery = new URLSearchParams(
    Object.fromEntries(
      Object.entries({ market, from_date: from, to_date: to }).filter(
        ([, v]) => v,
      ),
    ),
  ).toString();
  $: cursors =
    pagination.query === filterQuery ? pagination.cursors : [undefined];
  $: suffix = filterQuery ? "?" + filterQuery : "";
  let rows: CaseRow[] = [],
    selected: ResearchCase | null = null,
    busy = true,
    detailBusy = true,
    more = false;
  let listError = "",
    detailError = "",
    mounted = false;
  let listRequest: AbortController, detailRequest: AbortController;
  let picker: HTMLDialogElement;
  let leavingDetail = false;
  const size = 8;
  $: archive = ["/results", "/performance", "/observe"].includes($location);
  $: explicit = $location.match(/^\/research\/([1-9]\d*)$/)?.[1];
  $: selectedId = explicit ? Number(explicit) : rows[0]?.id;
  $: if (mounted && !archive && !leavingDetail)
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
  function filter(
    control: "market" | "date",
    region: string,
    start = from,
    end = to,
  ) {
    const params = new URLSearchParams();
    if (region) params.set("market", region);
    if (start) params.set("from_date", start);
    if (end) params.set("to_date", end);
    const hash = "#/research" + (params.size ? "?" + params : "");
    if (explicit && picker.open) {
      leavingDetail = true;
      reopenForFilter = { hash, control };
    }
    window.location.hash = hash;
  }
  onMount(() => {
    mounted = true;
    const pending = reopenForFilter;
    reopenForFilter = null;
    if (pending?.hash === window.location.hash) {
      tick().then(() => {
        if (!picker?.isConnected || window.location.hash !== pending.hash)
          return;
        picker.showModal();
        const selector =
          pending.control === "date" ? ".range-trigger" : "[role=combobox]";
        picker.querySelector<HTMLButtonElement>(selector)?.focus();
      });
    }
  });
  function returnToCaseTrigger() {
    picker?.parentElement
      ?.querySelector<HTMLButtonElement>(".choose")
      ?.focus({ preventScroll: true });
  }
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
      {#if !selected}<button
          class="choose"
          on:click={() => picker.showModal()}
          aria-haspopup="dialog"
          >사례 선택 <svg
            viewBox="0 0 16 16"
            width="14"
            height="14"
            aria-hidden="true"
            ><path
              d="m4 6 4 4 4-4"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
            /></svg
          ></button
        >{/if}
      <dialog
        bind:this={picker}
        aria-label="사례 선택"
        on:close={returnToCaseTrigger}
      >
        <header>
          <h2>사례 선택</h2>
          <button
            class="close"
            on:click={() => picker.close()}
            aria-label="사례 선택 닫기">닫기</button
          >
        </header>
        <ResearchFilters
          {market}
          {from}
          {to}
          on:market={(e) => filter("market", e.detail)}
          on:range={(e) => filter("date", market, e.detail.from, e.detail.to)}
        />
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
          <div class="register">
            {#each rows as row (row.id)}
              <a
                on:click={() => picker.close()}
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
          {#if cursors.length > 1}<button
              class="older"
              on:click={() => {
                pagination = {
                  query: filterQuery,
                  cursors: cursors.slice(0, -1),
                };
                window.location.hash = "#/research" + suffix;
              }}>이전 페이지</button
            >{/if}
          {#if more}<button
              class="older"
              disabled={busy}
              on:click={() => {
                pagination = {
                  query: filterQuery,
                  cursors: [...cursors, rows[rows.length - 1].id],
                };
                window.location.hash = "#/research" + suffix;
              }}>{busy ? "조회 중" : "다음 페이지"}</button
            >{/if}
        {/if}
      </dialog>
      <div class="detail-pane">
        {#if detailBusy}<p role="status">사례 근거를 불러오는 중입니다.</p>
        {:else if detailError}<p role="alert">
            {detailError}
            <button on:click={() => loadCase(selectedId)}>다시 조회</button>
          </p>
        {:else if selected}<ResearchEvidence data={selected}
            ><button
              class="choose"
              on:click={() => picker.showModal()}
              aria-haspopup="dialog"
              >사례 선택 <svg
                viewBox="0 0 16 16"
                width="14"
                height="14"
                aria-hidden="true"
                ><path
                  d="m4 6 4 4 4-4"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.7"
                /></svg
              ></button
            ></ResearchEvidence
          >
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
    max-width: 1440px;
    margin: auto;
    padding: 18px clamp(14px, 2.5vw, 36px) 52px;
    color: var(--fl-ink);
  }

  button {
    font: inherit;
    color: inherit;
  }
  button {
    border: 1px solid var(--fl-line);
    border-radius: 4px;
    background: var(--fl-surface);
    padding: 8px 12px;
  }
  button {
    cursor: pointer;
  }
  dialog {
    color-scheme: dark;
    background: var(--fl-surface);
  }
  button:focus-visible,
  .register a:focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: 2px;
  }
  .choose {
    align-self: flex-start;
    font-weight: 650;
    display: flex;
    gap: 14px;
    align-items: center;
  }
  .choose svg {
    color: var(--fl-accent);
  }
  dialog {
    width: min(490px, calc(100% - 30px));
    max-height: 75dvh;
    padding: 22px;
    border: 1px solid var(--fl-line);
    border-radius: 16px;
    color: var(--fl-ink);
    box-shadow: 0 16px 55px #0008;
    overflow: auto;
  }
  dialog::backdrop {
    background: #000a;
  }
  dialog header,
  .row-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  dialog header {
    justify-content: space-between;
    margin-bottom: 16px;
  }
  dialog h2 {
    margin: 0;
    font-size: 1.3rem;
  }
  .register {
    display: grid;
    gap: 1px;
    margin-block: 16px;
  }
  .register a {
    display: grid;
    gap: 5px;
    padding: 12px;
    border: 1px solid var(--fl-line);
    color: inherit;
    border-radius: 4px;
  }
  .register a.selected {
    background: #303427;
    border-color: var(--fl-accent);
  }
  .row-meta {
    justify-content: space-between;
    color: var(--fl-muted);
    font-size: 0.82rem;
  }
  .detail-pane {
    min-width: 0;
  }
  .blank {
    background: var(--fl-surface);
    padding: 24px;
    border-radius: 12px;
  }
  @media (max-width: 600px) {
    .research-desk {
      padding: 10px 12px 42px;
    }
    dialog {
      margin: auto auto 0;
      width: 100%;
      max-width: 100%;
      border-radius: 16px 16px 0 0;
    }
  }
</style>
