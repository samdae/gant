<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import { onMount } from "svelte";
  import {
    fetchReflections,
    fetchReflectionRetryCandidates,
    requestReflectionRetry,
  } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames, instrumentText } from "../stores/tickerNames";
  import AnalysisTabs from "../components/AnalysisTabs.svelte";

  type Reflection = {
    id: number;
    position_id: number;
    ticker?: string;
    outcome: string;
    return_pct: number;
    created_at: string;
  };

  type RetryCandidate = {
    position_id: number;
    ticker: string;
    return_pct: number | null;
    closed_at: string | null;
    reflection_id: number | null;
    status: "missing" | "failed" | "completed";
    retryable: boolean;
  };

  let loading = true;
  let error = "";
  let reflections: Reflection[] = [];
  let candidates: RetryCandidate[] = [];
  let candidateLoading = false;
  let candidateError = "";
  let retrying: Record<number, boolean> = {};

  let filter: "all" | "win" | "loss" = "all";
  let hasMore = true;
  let loadingMore = false;

  let generation = 0;
  const PAGE_SIZE = 15;

  const loadCandidates = async () => {
    candidateLoading = true;
    candidateError = "";
    try {
      const rows = (await fetchReflectionRetryCandidates(40)) as RetryCandidate[];
      candidates = (rows || []).filter((r) => r.retryable);
    } catch (err) {
      candidateError = formatErrorMessage(err, "재검증 대상 상태를 조회하지 못했습니다.");
    } finally {
      candidateLoading = false;
    }
  };

  const loadData = async (append = false) => {
    const request = ++generation;
    if (append) {
      loadingMore = true;
    } else {
      loading = true;
    }
    error = "";
    try {
      const cursor = append && reflections.length > 0 ? reflections[reflections.length - 1].id : undefined;
      const outcome = filter === "all" ? undefined : filter;
      const res = (await fetchReflections(PAGE_SIZE, outcome, cursor)) as Reflection[];
      if (request !== generation) return;
      if (append) {
        reflections = [...reflections, ...res];
      } else {
        reflections = res || [];
      }
      hasMore = res.length >= PAGE_SIZE;
    } catch (err) {
      if (request !== generation) return;
      error = formatErrorMessage(err, "회고 목록을 불러오지 못했습니다.");
    } finally {
      if (request !== generation) return;
      loading = false;
      loadingMore = false;
    }
  };

  const setFilter = (f: "all" | "win" | "loss") => {
    filter = f;
    reflections = [];
    hasMore = true;
    loadData();
  };

  const retryOne = async (row: RetryCandidate) => {
    retrying[row.position_id] = true;
    retrying = { ...retrying };
    error = "";

    try {
      await requestReflectionRetry(row.position_id);
      await Promise.all([loadCandidates(), loadData(false)]);
    } catch (err) {
      error = formatErrorMessage(err, `${instrumentText(row.ticker, $tickerNames)} 반성 재실행 실패`);
    } finally {
      retrying[row.position_id] = false;
      retrying = { ...retrying };
    }
  };

  onMount(() => {
    loadData();
    if (!isPublicViewer) loadCandidates();
  });

  const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    try {
      return new Date(iso).toLocaleDateString("ko-KR", { year: "numeric", month: "short", day: "numeric" });
    } catch {
      return "-";
    }
  };

  const displayName = (ticker?: string) => {
    if (!ticker) return "";
    return $tickerNames[ticker] || "";
  };
</script>

<section class="page" id="page-reflections">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? "매매 검증" : "AI분석"}</h2>
    </div>
    {#if isForecastLab}<p class="folio-deck">종료된 거래의 손익과 당시 판단을 검토합니다. 전체 통화 기준입니다.</p>{:else}<AnalysisTabs />{/if}

    {#if candidates.length > 0}
      <div class="card" style="margin-bottom:14px">
        <div class="card-header">
          <h3>재검증이 필요한 거래</h3>
        </div>
        <div class="retry-list">
          {#each candidates as c}
            <div class="retry-row">
              <div class="retry-left">
                {#if isForecastLab}<InstrumentLabel ticker={c.ticker} />{:else}<span class="ticker-badge">{c.ticker}</span>
                {#if displayName(c.ticker)}
                  <span class="ticker-tag">{displayName(c.ticker)}</span>
                {/if}{/if}
                <span class="badge badge-warn">{c.status === "missing" ? "미생성" : "실패"}</span>
              </div>
              <div class="retry-right">
                <span class={c.return_pct != null && c.return_pct >= 0 ? "text-gain" : "text-loss"}>
                  {c.return_pct != null ? formatPercent(c.return_pct) : "-"}
                </span>
                <span class="reflection-date">{formatDate(c.closed_at)}</span>
                <button class="btn btn-primary retry-btn" on:click={() => retryOne(c)} disabled={!!retrying[c.position_id]}>
                  {retrying[c.position_id] ? "재실행 중..." : "재실행"}
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else if candidateError && isForecastLab}
      <div class="review-state" role="alert">{candidateError}
        <button class="btn btn-secondary" on:click={loadCandidates}>재검증 대상 다시 조회</button>
      </div>
    {:else if candidateLoading}
      <div class="card" style="padding:12px;margin-bottom:14px;color:var(--text-dim)"><PendingState label="매매 검증 대상 조회 중" /></div>
    {/if}

    {#if isForecastLab}
    <div class="review-switch" role="group" aria-label="거래 결과">
      <button aria-pressed={filter === "all"} on:click={() => setFilter("all")}
        ><span>전체</span></button
      >
      <button aria-pressed={filter === "win"} on:click={() => setFilter("win")}><span>승</span></button>
      <button aria-pressed={filter === "loss"} on:click={() => setFilter("loss")}
        ><span>패</span></button
      >
    </div>
    {:else}
    <div class="tab-bar" style="margin-bottom:16px">
      <button class={`tab-btn ${filter === "all" ? "active" : ""}`} on:click={() => setFilter("all")}>전체</button>
      <button class={`tab-btn ${filter === "win" ? "active" : ""}`} on:click={() => setFilter("win")}>승</button>
      <button class={`tab-btn ${filter === "loss" ? "active" : ""}`} on:click={() => setFilter("loss")}>패</button>
    </div>

    {/if}

    {#if loading}
      <div class="card" style="padding:16px"><PendingState label="매매 검증 조회 중"/></div>
    {:else if error}
      <div class="card" style="padding:16px"><span class="error-text">{error}</span> <button class="btn btn-secondary" on:click={() => loadData()}>다시 조회</button></div>
    {:else if reflections.length === 0}
      {#if isForecastLab}
      <section class="review-empty">
        <header>종료 거래 검증 기록</header>
        <div>
          <h3>
            {filter === "all" ? "아직 검증 기록이 없습니다" : "선택한 결과에 해당하는 기록이 없습니다"}
          </h3>
          <p>
            {filter === "all"
              ? "거래가 종료되고 검증이 완료되면 수익률과 당시 판단에 대한 교훈을 확인할 수 있습니다."
              : "전체 결과에서 다른 거래의 검증 기록을 확인할 수 있습니다."}
          </p>
          {#if filter !== "all"}<button on:click={() => setFilter("all")}>전체 결과 보기</button>{:else}<a
              href="#/positions">포지션 확인</a
            >{/if}
        </div>
      </section>
      {:else}<div class="card" style="padding:16px">회고 기록이 없습니다.</div>{/if}
    {:else}
      {#if isForecastLab}
      <div class="review-register">
        <table>
          <caption>종료 거래 검증 기록</caption>
          <thead><tr><th>종목</th><th>결과</th><th>수익률</th><th class="review-extra">작성일</th></tr></thead>
          <tbody
            >{#each reflections as ref}<tr
                ><td
                  ><a href={`#/reflections/${ref.id}`}>{#if ref.ticker}<InstrumentLabel ticker={ref.ticker} />{:else}포지션 #{ref.position_id}{/if}</a>
                  <span class="review-mobile-date">작성 {formatDate(ref.created_at)}</span></td
                ><td>{ref.outcome === "win" ? "승" : ref.outcome === "loss" ? "패" : "미확정"}</td><td
                  >{formatPercent(ref.return_pct)}</td
                ><td class="review-extra">{formatDate(ref.created_at)}</td></tr
              >{/each}</tbody
          >
        </table>
      </div>
      {:else}
      <div class="reflection-list list-grid">
        {#each reflections as ref}
          <a class="reflection-card list-row" href={`#/reflections/${ref.id}`}>
            <div class="reflection-left">
              {#if ref.ticker}
                <span class="ticker-badge">{ref.ticker}</span>
                {#if displayName(ref.ticker)}
                  <span class="ticker-tag">{displayName(ref.ticker)}</span>
                {/if}
              {/if}
            </div>

            <div class="reflection-right">
              <span class={`badge ${ref.outcome === "win" ? "badge-gain" : "badge-loss"}`}>
                {ref.outcome === "win" ? "승" : "패"}
              </span>
              <span class={ref.return_pct >= 0 ? "text-gain" : "text-loss"}>
                {formatPercent(ref.return_pct)}
              </span>
              <span class="reflection-date">{formatDate(ref.created_at)}</span>
              <span class="reflection-chevron">›</span>
            </div>
          </a>
        {/each}
      </div>

      {/if}
      {#if hasMore}
        <div style="text-align:center;margin-top:16px">
          <button class="btn btn-secondary" on:click={() => loadData(true)} disabled={loadingMore}>
            {#if loadingMore}<PendingState label="검증 기록 조회 중"/>{:else}더 보기{/if}
          </button>
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .retry-list {
    display: flex;
    flex-direction: column;
  }

  .retry-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 16px;
    border-top: 1px solid var(--border);
  }

  .retry-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .retry-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .retry-btn {
    padding: 6px 10px;
    font-size: 0.75rem;
    white-space: nowrap;
  }

  .reflection-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .reflection-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 16px;
    text-decoration: none;
    color: inherit;
  }

  .reflection-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .reflection-right {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8125rem;
  }

  .reflection-date {
    color: var(--text-dim);
    font-size: 0.75rem;
    white-space: nowrap;
  }

  .reflection-chevron {
    color: var(--text-dim);
    font-size: 1rem;
    line-height: 1;
  }
</style>
