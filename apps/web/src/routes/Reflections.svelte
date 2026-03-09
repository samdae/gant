<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchReflections,
    fetchReflectionRetryCandidates,
    requestReflectionRetry,
  } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
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
  let retrying: Record<number, boolean> = {};

  let filter: "all" | "win" | "loss" = "all";
  let hasMore = true;
  let loadingMore = false;

  const PAGE_SIZE = 15;

  const loadCandidates = async () => {
    candidateLoading = true;
    try {
      const rows = (await fetchReflectionRetryCandidates(40)) as RetryCandidate[];
      candidates = (rows || []).filter((r) => r.retryable);
    } catch (err) {
      console.error("failed to load retry candidates", err);
    } finally {
      candidateLoading = false;
    }
  };

  const loadData = async (append = false) => {
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
      if (append) {
        reflections = [...reflections, ...res];
      } else {
        reflections = res || [];
      }
      hasMore = res.length >= PAGE_SIZE;
    } catch (err) {
      error = formatErrorMessage(err, "회고 목록을 불러오지 못했습니다.");
    } finally {
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
      error = formatErrorMessage(err, `${displayName(row.ticker) || row.ticker} 반성 재실행 실패`);
    } finally {
      retrying[row.position_id] = false;
      retrying = { ...retrying };
    }
  };

  onMount(() => {
    loadData();
    loadCandidates();
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
      <h2>AI분석</h2>
    </div>
    <AnalysisTabs />

    {#if candidates.length > 0}
      <div class="card" style="margin-bottom:14px">
        <div class="card-header">
          <h3>반성 재실행 필요</h3>
        </div>
        <div class="retry-list">
          {#each candidates as c}
            <div class="retry-row">
              <div class="retry-left">
                <span class="ticker-badge">{c.ticker}</span>
                {#if displayName(c.ticker)}
                  <span class="ticker-tag">{displayName(c.ticker)}</span>
                {/if}
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
    {:else if candidateLoading}
      <div class="card" style="padding:12px;margin-bottom:14px;color:var(--text-dim)">반성 상태 확인 중...</div>
    {/if}

    <div class="tab-bar" style="margin-bottom:16px">
      <button class={`tab-btn ${filter === "all" ? "active" : ""}`} on:click={() => setFilter("all")}>전체</button>
      <button class={`tab-btn ${filter === "win" ? "active" : ""}`} on:click={() => setFilter("win")}>승</button>
      <button class={`tab-btn ${filter === "loss" ? "active" : ""}`} on:click={() => setFilter("loss")}>패</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card" style="padding:16px"><span class="error-text">{error}</span></div>
    {:else if reflections.length === 0}
      <div class="card" style="padding:16px">회고 기록이 없습니다.</div>
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

      {#if hasMore}
        <div style="text-align:center;margin-top:16px">
          <button class="btn btn-secondary" on:click={() => loadData(true)} disabled={loadingMore}>
            {loadingMore ? "불러오는 중..." : "더 보기"}
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
