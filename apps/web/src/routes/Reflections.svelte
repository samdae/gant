<script lang="ts">
  import { onMount } from "svelte";
  import { fetchReflections } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { marked } from "marked";
  import DOMPurify from "dompurify";

  type Reflection = {
    id: number;
    position_id: number;
    ticker?: string;
    reflection: string;
    key_lessons: string;
    outcome: string;
    return_pct: number;
    market: string | null;
    sector: string | null;
    industry: string | null;
    created_at: string;
  };

  let loading = true;
  let error = "";
  let reflections: Reflection[] = [];
  let filter: "all" | "win" | "loss" = "all";
  let hasMore = true;
  let loadingMore = false;

  const PAGE_SIZE = 15;

  const goTrade = (ticker: string) => {
    window.location.hash = `#/trade/${ticker.toLowerCase()}`;
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
    cursor = null;
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
    } catch { return "-"; }
  };

  const truncate = (text: string, max: number) =>
    text.length > max ? text.slice(0, max) + "..." : text;

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>데이터 없음</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

  let expandedId: number | null = null;
  const toggle = (id: number) => {
    expandedId = expandedId === id ? null : id;
  };
</script>

<section class="page" id="page-reflections">
  <div class="page-container">
    <div class="page-header">
      <h2>회고</h2>
    </div>

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
      <div class="reflection-list" style="display:flex;flex-direction:column;gap:12px">
        {#each reflections as ref}
          <button class="card reflection-card" type="button" on:click={() => toggle(ref.id)} style="text-align:left;cursor:pointer;width:100%;border:none">
            <div class="card-body" style="padding:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
                  {#if ref.ticker}
                    <span class="ticker-badge" on:click|stopPropagation={() => goTrade(ref.ticker || "")}>{ref.ticker}</span>
                    {#if $tickerNames[ref.ticker]}
                      <span class="ticker-tag">{$tickerNames[ref.ticker]}</span>
                    {/if}
                  {/if}
                  <span class={`badge ${ref.outcome === "win" ? "badge-gain" : "badge-loss"}`}>
                    {ref.outcome === "win" ? "승" : "패"}
                  </span>
                  <span class={ref.return_pct >= 0 ? "text-gain" : "text-loss"} style="font-size:0.8125rem;font-weight:600">
                    {formatPercent(ref.return_pct)}
                  </span>
                </div>
                <span style="font-size:0.75rem;color:var(--text-dim)">{formatDate(ref.created_at)}</span>
              </div>

              <div style="font-size:0.8125rem;color:var(--text-secondary);margin-bottom:4px">
                {truncate(ref.key_lessons, 120)}
              </div>

              {#if ref.market || ref.sector}
                <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
                  {#if ref.market}
                    <span class="badge badge-muted" style="font-size:0.6875rem">{ref.market}</span>
                  {/if}
                  {#if ref.sector}
                    <span class="badge badge-muted" style="font-size:0.6875rem">{ref.sector}</span>
                  {/if}
                  {#if ref.industry}
                    <span class="badge badge-muted" style="font-size:0.6875rem">{ref.industry}</span>
                  {/if}
                </div>
              {/if}

              {#if expandedId === ref.id}
                <div class="md-content" style="margin-top:12px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);font-size:0.8125rem;line-height:1.6;color:var(--text-secondary)">
                  {@html renderMd(ref.reflection)}
                </div>
              {/if}
            </div>
          </button>
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
