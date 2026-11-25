<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import InstrumentLabel from "./InstrumentLabel.svelte";
  import { marketName, researchGet, timeLabel } from "../lib/researchEvidence";
  import {
    basis,
    caseStates,
    coverageLabels,
    group,
    holdReason,
    method,
    pct,
    phases,
    score,
    shared,
    spec,
    type Stats,
    type Status,
  } from "../lib/researchReview";

  export let view: "results" | "observe";
  const incoming = new URLSearchParams(location.hash.split("?")[1] || "");
  const initialDate = (key: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(incoming.get(key) || "")
      ? incoming.get(key) || ""
      : "";
  let market = ["us", "kr"].includes(incoming.get("market") || "")
      ? incoming.get("market") || ""
      : "",
    from = initialDate("from_date"),
    to = initialDate("to_date"),
    refresh = 0,
    mounted = false;
  let status: Status | null = null,
    stats: Stats | null = null;
  let statusError = "",
    statsError = "",
    statsBusy = false;
  let statRequest: AbortController, statusRequest: AbortController;
  let timer: ReturnType<typeof setInterval>;
  $: rangeError = Boolean(from && to && from > to);
  $: if (mounted) loadStats(market, from, to, refresh);
  $: if (mounted) loadStatus(refresh);
  $: universe =
    status?.tickers.filter((t) => !market || t.market === market) || [];
  $: normal = (stats?.comparisons || []).filter(
    (r) => r.treated !== "memory_sector",
  );
  $: sector = (stats?.comparisons || []).filter(
    (r) => r.treated === "memory_sector",
  );
  $: phase = status?.progress || {};

  async function loadStats(
    region: string,
    start: string,
    end: string,
    _refresh: number,
  ) {
    statRequest?.abort();
    const request = new AbortController();
    statRequest = request;
    stats = null;
    statsError = "";
    statsBusy = false;
    if (start && end && start > end) return;
    statsBusy = true;
    const qs = new URLSearchParams();
    if (region) qs.set("market", region);
    if (start) qs.set("from_date", start);
    if (end) qs.set("to_date", end);
    try {
      const value = await researchGet<Stats>(
        "stats" + (qs.size ? "?" + qs : ""),
        request.signal,
      );
      if (!request.signal.aborted) stats = value;
    } catch {
      if (!request.signal.aborted)
        statsError = "성과 기록을 불러오지 못했습니다.";
    } finally {
      if (!request.signal.aborted) statsBusy = false;
    }
  }
  async function loadStatus(_refresh: number) {
    statusRequest?.abort();
    const request = new AbortController();
    statusRequest = request;
    statusError = "";
    try {
      const value = await researchGet<Status>("status", request.signal);
      if (!request.signal.aborted) status = value;
    } catch {
      if (!request.signal.aborted) {
        status = null;
        statusError = "관측 상태를 불러오지 못했습니다.";
      }
    }
  }
  onMount(() => {
    mounted = true;
    timer = setInterval(() => {
      if (!document.hidden) refresh++;
    }, 60000);
  });
  onDestroy(() => {
    clearInterval(timer);
    statRequest?.abort();
    statusRequest?.abort();
  });
</script>

<section class="review">
  <header class="heading">
    <h2>{view === "observe" ? "관찰 종목" : "연구 성과"}</h2>
    <button on:click={() => refresh++}>새로고침</button>
  </header>
  <div class="filters" aria-label="시장과 관측 기간">
    <label
      >시장<select bind:value={market}
        ><option value="">전체 시장</option><option value="us">미국</option
        ><option value="kr">한국</option></select
      ></label
    >
    <label>관측 시작일<input type="date" bind:value={from} /></label>
    <label>관측 종료일<input type="date" bind:value={to} /></label>
    {#if market || from || to}<button
        on:click={() => {
          market = "";
          from = "";
          to = "";
        }}>전체 기간·시장</button
      >{/if}
  </div>
  {#if rangeError}<p role="alert">종료일을 시작일 이후로 선택해 주세요.</p>
  {:else if statsError}<p role="alert">{statsError}</p>
  {:else if statsBusy}<p role="status">관측 기간의 성과를 조회하고 있습니다.</p>
  {:else if stats}<dl class="counts">
      {#each Object.entries(caseStates) as [key, label]}<div>
          <dt>{label}</dt>
          <dd>{stats.counts?.[key] ?? "—"}</dd>
        </div>{/each}
    </dl>{/if}
  {#if statusError}<p role="alert">{statusError}</p>{/if}
  {#if view === "observe"}
    {#if status}
      <section>
        <h3>수집 진행</h3>
        <p>
          {status.scheduler_enabled ? "자동 관측 켜짐" : "자동 관측 꺼짐"} · {phases[
            phase.phase || ""
          ] || "시작 대기"}
          {#if phase.ticker}
            · <InstrumentLabel
              ticker={phase.ticker}
              inline
            />{/if}{#if phase.method}
            · {method(phase.method)}{/if}
          {#if phase.attempted != null && phase.total != null}
            · {phase.attempted}/{phase.total}종목{/if}
        </p>
        {#if phase.finished_at || phase.started_at}<p>
            {phase.finished_at ? "최근 종료" : "시작"}
            {timeLabel(phase.finished_at || phase.started_at)}
          </p>{/if}
      </section>
      <section>
        <h3>현재 등록 종목 <small>{universe.length}개</small></h3>
        <p>
          시장 필터가 적용된 현재 관찰 목록입니다. 관측 기간은 위 사례 수에
          적용됩니다.
        </p>
        {#if universe.length}
          <div class="scroll">
            <table>
              <thead
                ><tr
                  ><th>종목</th><th>시장</th><th>현재 분류</th><th
                    >최근 관측 보류</th
                  ></tr
                ></thead
              >
              <tbody
                >{#each universe as t}<tr
                    ><th><InstrumentLabel ticker={t.ticker} name={t.name} /></th
                    ><td>{marketName(t.market)}</td><td>{group(t)}</td>
                    <td
                      >{phase.failures?.[t.ticker]
                        ? holdReason(phase.failures[t.ticker])
                        : "—"}</td
                    ></tr
                  >{/each}</tbody
              >
            </table>
          </div>
        {:else}<p>등록된 관찰 종목이 없습니다.</p>{/if}
      </section>
    {:else if !statusError}<p role="status">
        관찰 목록을 불러오는 중입니다.
      </p>{/if}
  {:else if stats}
    <section>
      <h3>방법별 공통 채점</h3>
      <p>
        같은 사례에서 발행한 상승 확률을 비교합니다. Brier 점수가 낮을수록 실제
        결과에 가까웠습니다.
      </p>
      {#if normal.length}
        {#each normal as r}<article>
            <h4>{method(r.control)} → {method(r.treated)}</h4>
            <small>{spec(r)}</small>
            <p>
              {shared(r)} · Brier {score(r.control_brier)} → {score(
                r.treated_brier,
              )} · 개선량 {score(r.improvement)}
            </p>
            {#if r.control_paper_return != null}<p>
                모의 총수익률 평균 {pct(r.control_paper_return)} → {pct(
                  r.treated_paper_return,
                )} · 상승 확률 50% 초과 시 보유, 그 외 현금
              </p>{/if}
          </article>{/each}
      {:else}<p class="empty">공통으로 채점된 사례가 아직 없습니다.</p>{/if}
    </section>
    <section>
      <h3>분류 기억 비교</h3>
      <p>같은 모델·시장 입력에서 서로 다른 기억을 선택한 예측만 채점합니다.</p>
      <dl class="coverage">
        {#each Object.entries(coverageLabels) as [key, label]}<div>
            <dt>{label}</dt>
            <dd>{stats.sector_coverage?.[key] ?? "—"}</dd>
          </div>{/each}
      </dl>
      {#each sector as r}<article>
          <h4>{method(r.control)} → {method(r.treated)}</h4>
          <small>{spec(r)}</small>
          <p>
            {shared(r)} · Brier {score(r.control_brier)} → {score(
              r.treated_brier,
            )} · 개선량 {score(r.improvement)}
          </p>
        </article>
      {:else}<p class="empty">
          서로 다른 기억으로 채점된 쌍이 아직 없습니다.
        </p>{/each}
      {#if stats.sector_by_basis?.length}<div class="scroll">
          <table>
            <caption>선택 근거별 성적</caption><thead
              ><tr
                ><th>선택 근거 · 모델</th><th>채점 쌍</th><th>Brier 개선량</th
                ></tr
              ></thead
            >
            <tbody
              >{#each stats.sector_by_basis as r}<tr
                  ><th>{basis(r)}<small>{spec(r)}</small></th><td>{r.n}</td><td
                    >{score(r.improvement)}</td
                  ></tr
                >{/each}</tbody
            >
          </table>
        </div>{/if}
    </section>
    <section>
      <h3>확률 보정</h3>
      <p>발행 확률 구간별 평균 예측을 실제 상승 비율과 비교합니다.</p>
      {#if stats.calibration?.length}<div class="scroll">
          <table>
            <thead
              ><tr
                ><th>방법 · 구간</th><th>평균 예측</th><th>실제 상승</th><th
                  >표본</th
                ></tr
              ></thead
            >
            <tbody
              >{#each stats.calibration as r}<tr
                  ><th
                    >{method(r.method)} · {pct(r.lower)} ~ {pct(r.upper)}<small
                      >{spec(r)}</small
                    ></th
                  ><td>{pct(r.mean_probability)}</td><td
                    >{pct(r.observed_rate)}</td
                  ><td>{r.n}</td></tr
                >{/each}</tbody
            >
          </table>
        </div>
      {:else}<p class="empty">
          확률 구간을 평가할 채점 표본이 아직 없습니다.
        </p>{/if}
    </section>
    <section>
      <h3>기존 운영 예측과 비교</h3>
      {#each stats.reference_comparisons || [] as r}<article>
          <h4>운영 모델 → {method(r.method)}</h4>
          <small>{spec(r)}</small>
          <p>
            {shared(r)} · Brier {score(r.source_brier)} → {score(
              r.method_brier,
            )} · 개선량 {score(r.improvement)}
          </p>
        </article>
      {:else}<p class="empty">
          {status?.reference_enabled === false
            ? "기존 운영 리포트 수집이 꺼져 있습니다."
            : "같은 기간에 발행하고 채점한 공통 표본이 아직 없습니다."}
        </p>{/each}
    </section>
  {/if}
</section>

<style>
  .review {
    color: #222321;
    font-variant-numeric: tabular-nums;
  }
  .heading,
  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }
  .heading {
    justify-content: space-between;
  }
  h2,
  h3,
  h4 {
    margin: 0;
  }
  h2 {
    font-size: 1.65rem;
  }
  h3 {
    font-size: 1.18rem;
  }
  .filters {
    margin-block: 1rem;
    align-items: flex-end;
  }
  label {
    display: grid;
    gap: 0.25rem;
    font-size: 0.85rem;
  }
  button,
  select,
  input {
    font: inherit;
    color: inherit;
    background: #fff;
    border: 1px solid #aaa49e;
    border-radius: 0.25rem;
    padding: 0.38rem 0.6rem;
  }
  button {
    cursor: pointer;
  }
  .review > section {
    padding: 1.2rem 0;
    border-top: 1px solid #c7c1ba;
  }
  p,
  small,
  dt {
    color: #605b56;
  }
  p {
    margin: 0.45rem 0;
    line-height: 1.55;
  }
  small {
    font-size: 0.79rem;
    overflow-wrap: anywhere;
  }
  article {
    border-top: 1px solid #e2ddd6;
    padding: 0.75rem 0;
  }
  article p {
    font-size: 0.91rem;
  }
  button:focus-visible,
  select:focus-visible,
  input:focus-visible {
    outline: 2px solid #852641;
    outline-offset: 2px;
  }
  .counts,
  .coverage {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(6.3rem, 1fr));
    gap: 0.75rem;
    padding: 0.8rem 0;
  }
  dd {
    margin: 0.2rem 0 0;
    font-size: 1.2rem;
    font-weight: 650;
  }
  dt {
    font-size: 0.82rem;
  }
  .scroll {
    max-width: 100%;
    overflow-x: auto;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.9rem;
  }
  caption {
    text-align: left;
    font-weight: 650;
    padding: 0.65rem 0;
  }
  td,
  th {
    padding: 0.65rem 0.45rem;
    border-bottom: 1px solid #ded9d3;
    text-align: right;
  }
  th:first-child {
    text-align: left;
  }
  thead th {
    white-space: nowrap;
    color: #514c47;
  }
  tbody th {
    font-weight: 550;
  }
  td {
    white-space: nowrap;
  }
  th small {
    display: block;
    font-weight: 400;
  }
  .empty {
    padding-block: 0.4rem;
  }
  @media (max-width: 480px) {
    label {
      min-width: 0;
    }
    input {
      max-width: 9.25rem;
    }
    td,
    th {
      padding: 0.55rem 0.3rem;
    }
  }
</style>
