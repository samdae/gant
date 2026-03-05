<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReflections } from "../lib/api/endpoints";
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

  let loading = true;
  let error = "";
  let reflections: Reflection[] = [];
  let filter: "all" | "win" | "loss" = "all";
  let hasMore = true;
  let loadingMore = false;

  const PAGE_SIZE = 15;

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

  onMount(() => {
    loadData();
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
