<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import RefreshButton from "./RefreshButton.svelte";
  import { onDestroy, onMount } from "svelte";
  import { querystring } from "svelte-spa-router";
  import ResearchFilters from "./ResearchFilters.svelte";
  import { readResearchFilters } from "../lib/researchDates";
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
  let market = "",
    from = "",
    to = "",
    refresh = 0,
    mounted = false;
  $: ({ market, from, to } = readResearchFilters($querystring || ""));
  function filter(region: string, start: string, end: string) {
    const params = new URLSearchParams($querystring || "");
    for (const [key, value] of [
      ["market", region],
      ["from_date", start],
      ["to_date", end],
    ]) {
      if (value) params.set(key, value);
      else params.delete(key);
    }
    window.location.hash =
      window.location.hash.split("?")[0] + (params.size ? "?" + params : "");
  }
  let status: Status | null = null,
    stats: Stats | null = null;
  let statusError = "",
    statsError = "",
    statsBusy = false,
    statusBusy = false;
  let statsKey = "", manual = false, announcement = "";
  $: if (manual && !statsBusy && !statusBusy) {
    announcement = statsError || statusError ? "일부 자료를 갱신하지 못했습니다." : "자료를 갱신했습니다.";
    manual = false;
  }
  function refreshNow() {
    if (statsBusy || statusBusy) return;
    announcement = "";
    statusBusy = true;
    manual = true;
    refresh++;
  }
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
    const key = [region,start,end].join("|");
    if (key !== statsKey) stats = null;
    statsKey = key;
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
        statsError = stats ? "성과 갱신에 실패했습니다. 마지막 조회 결과입니다." : "성과 기록을 불러오지 못했습니다.";
    } finally {
      if (!request.signal.aborted) statsBusy = false;
    }
  }
  async function loadStatus(_refresh: number) {
    statusRequest?.abort();
    const request = new AbortController();
    statusRequest = request;
    statusBusy = true;
    statusError = "";
    try {
      const value = await researchGet<Status>("status", request.signal);
      if (!request.signal.aborted) status = value;
    } catch {
      if (!request.signal.aborted) {
        statusError = status ? "관측 상태 갱신에 실패했습니다. 마지막 조회 결과입니다." : "관측 상태를 불러오지 못했습니다.";
      }
    } finally {
      if (!request.signal.aborted) statusBusy = false;
    }
  }
  onMount(() => {
    mounted = true;
    timer = setInterval(() => {
      if (!document.hidden && !statsBusy && !statusBusy) refresh++;
    }, 60000);
  });
  onDestroy(() => {
    clearInterval(timer);
    statRequest?.abort();
    statusRequest?.abort();
  });
</script>

<section class="review" class:results-view={view === "results"}>
  <header class="heading">
    <h2>{view === "observe" ? "관측 현황" : "예측 성과"}</h2>
    <RefreshButton label={view === "observe" ? "관측 현황 새로고침" : "예측 성과 새로고침"}
      busy={statsBusy || statusBusy} on:click={refreshNow} />
    <span class="refresh-announcement" role="status">{announcement}</span>
  </header>
  <ResearchFilters
    {market}
    {from}
    {to}
    on:market={(e) => filter(e.detail, from, to)}
    on:range={(e) => filter(market, e.detail.from, e.detail.to)}
  />
  {#if rangeError}<p role="alert">종료일을 시작일 이후로 선택해 주세요.</p>
  {:else if statsError}<p role="alert">{statsError}</p>
  {:else if statsBusy && !stats}<p><PendingState label="관측 기간의 성과 조회 중" /></p>
  {/if}
  {#if stats}<dl class="counts">
      {#each Object.entries(caseStates).filter(([key]) => (stats?.counts?.[key] ?? 0) > 0) as [key, label]}<div
        >
          <dt>{label}</dt>
          <dd>{stats?.counts?.[key] ?? "—"}</dd>
        </div>{:else}<div>
          <dt>관측 사례</dt>
          <dd>
            {Object.keys(caseStates).every((key) => stats?.counts?.[key] === 0)
              ? "0"
              : "미확인"}
          </dd>
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
            <table class="watch-table">
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
                    <td class:no-hold={!phase.failures?.[t.ticker]}
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
    {:else if statusBusy}<p><PendingState label="관찰 목록 조회 중" /></p>{/if}
  {:else if stats && !stats.comparisons?.length && !stats.reference_comparisons?.length && !stats.calibration?.length && !stats.sector_by_basis?.length}
    <section class="cohort-empty">
      <h3>비교할 채점 표본이 없습니다</h3>
      <p>
        같은 종목·회차의 예측이 만기를 지나면 방법별 점수와 확률 보정을 확인할
        수 있습니다.
      </p>
      <a href="#/research">발행된 예측 확인</a>
      <details>
        <summary>비교 기준과 분류 기억 발행 현황</summary>
        <p>
          Brier 점수는 낮을수록 정확합니다. 같은 사례의 공통 예측을 비교하고,
          확률 보정은 구간별 실제 상승률을 사용합니다.
        </p>
        <p>
          {status?.reference_enabled === false
            ? "기존 운영 리포트 수집이 꺼져 있습니다."
            : "기존 운영 예측은 같은 기간에 발행하고 채점된 사례만 비교합니다."}
        </p>
        <dl class="coverage">
          {#each Object.entries(coverageLabels) as [key, label]}<div>
              <dt>{label}</dt>
              <dd>{stats.sector_coverage?.[key] ?? "—"}</dd>
            </div>{/each}
        </dl>
      </details>
    </section>
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
  .refresh-announcement {position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%);}

  .counts {
    border-block:1px solid var(--fl-line);
    margin:16px 0;
  }
  .counts div { display:flex; align-items:baseline; gap:.6rem; }
  .counts div dd { order:-1; font-size:1.45rem; color:var(--fl-ink); }
  .review > section > h3 { margin-bottom:.6rem; }

  .cohort-empty,
  .review > section {
    background: var(--fl-surface, #202124);
    border: 1px solid var(--fl-line, #3b3d41);
    border-radius: var(--fl-radius,16px);
    padding: 1rem 1.2rem;
    margin-block: 0.9rem;
  }
  .cohort-empty a {
    display: inline-block;
    color: var(--fl-accent, #d5f65e);
    font-weight: 650;
    margin: 0.4rem 0 0.7rem;
  }
  .cohort-empty details {
    border-top: 1px solid var(--fl-line, #3b3d41);
    padding-top: 0.7rem;
  }
  .cohort-empty summary {
    cursor: pointer;
    font-weight: 600;
  }
  .review {
    color: var(--fl-ink, #f4f2e9);
    font-variant-numeric: tabular-nums;
  }
  .heading {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    justify-content: space-between;
  }
  h2,
  h3,
  h4 {
    margin: 0;
  }
  h2 {
    font:730 clamp(1.8rem,3vw,2.65rem)/1.15 var(--fl-display);
    letter-spacing:-.035em;
  }
  h3 {
    font-size: 1.18rem;
  }
  .review > section {
    padding: clamp(17px,2.6vw,30px);
    border-top: 1px solid var(--fl-line, #3b3d41);
  }
  p,
  small,
  dt {
    color: var(--fl-muted, #b5b4ad);
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
    border-top: 1px solid var(--fl-line, #3b3d41);
    padding: 0.75rem 0;
  }
  article p {
    font-size: 0.91rem;
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
    border-bottom: 1px solid var(--fl-line, #3b3d41);
    text-align: right;
  }
  th:first-child {
    text-align: left;
  }
  thead th {
    white-space: nowrap;
    color: var(--fl-muted, #b5b4ad);
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
    td,
    th {
      padding: 0.55rem 0.3rem;
    }
  }
  @media (max-width: 600px) {
    .watch-table,
    .watch-table tbody {
      display: block;
    }
    .watch-table thead {
      position: absolute;
      width: 1px;
      height: 1px;
      overflow: hidden;
      clip-path: inset(50%);
    }
    .watch-table tbody tr {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.3rem 0.65rem;
      align-items: start;
      padding: 0.6rem 0;
      border-top: 1px solid var(--fl-line, #3b3d41);
    }
    .watch-table tbody :is(th, td) {
      padding: 0;
      border: 0;
      text-align: left;
      white-space: normal;
    }
    .watch-table tbody th {
      grid-column: 1;
      grid-row: 1 / 3;
    }
    .watch-table tbody td:nth-child(2),
    .watch-table tbody td:nth-child(3) {
      grid-column: 2;
      text-align: right;
      font-size: 0.8rem;
      color: var(--fl-muted, #b5b4ad);
    }
    .watch-table tbody td:last-child {
      grid-column: 1/-1;
      color: var(--fl-muted, #b5b4ad);
      font-size: 0.8rem;
    }
    .watch-table tbody td:last-child::before {
      content: "최근 관측 보류 · ";
    }
    .watch-table tbody td.no-hold {
      display: none;
    }
  }
  .results-view article h4,
  .results-view caption {
    color: var(--fl-forecast);
  }
  .counts dd,
  .coverage dd {
    color: var(--fl-ink);
  }
</style>
