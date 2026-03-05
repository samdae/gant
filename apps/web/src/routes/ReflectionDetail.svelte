<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { marked } from "marked";
  import DOMPurify from "dompurify";
  import { fetchReflectionDetail } from "../lib/api/endpoints";
  import { formatPercent, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import AnalysisTabs from "../components/AnalysisTabs.svelte";

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
  let reflection: Reflection | null = null;
  let reflectionId = 0;

  $: reflectionId = Number($params?.id || 0);

  const loadData = async (id: number) => {
    if (!id || Number.isNaN(id)) return;
    loading = true;
    error = "";
    reflection = null;
    try {
      reflection = (await fetchReflectionDetail(id)) as Reflection;
    } catch (err) {
      error = formatErrorMessage(err, "회고 상세를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    if (reflectionId) loadData(reflectionId);
  });

  $: if (reflectionId) loadData(reflectionId);

  const formatDate = (iso?: string | null) => {
    if (!iso) return "-";
    try {
      return new Date(iso).toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return "-";
    }
  };

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>내용 없음</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

  const displayName = (ticker?: string) => {
    if (!ticker) return "";
    return $tickerNames[ticker] || "";
  };
</script>

<section class="page" id="page-reflection-detail">
  <div class="page-container">
    <div class="page-header reflection-page-header">
      <a href="#/reflections" class="back-link" aria-label="뒤로">&larr;</a>
      <h2>AI분석</h2>
    </div>
    <AnalysisTabs />

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card" style="padding:16px"><span class="error-text">{error}</span></div>
    {:else if !reflection}
      <div class="card" style="padding:16px">회고 데이터를 찾을 수 없습니다.</div>
    {:else}
      <div class="reflection-detail-top card">
        <div class="card-body">
          <div class="reflection-top-row">
            <div class="reflection-top-left">
              {#if reflection.ticker}
                <span class="ticker-badge">{reflection.ticker}</span>
                {#if displayName(reflection.ticker)}
                  <span class="ticker-tag">{displayName(reflection.ticker)}</span>
                {/if}
              {/if}
            </div>
            <span class={`badge ${reflection.outcome === "win" ? "badge-gain" : "badge-loss"}`}>
              {reflection.outcome === "win" ? "승" : "패"}
            </span>
          </div>

          <div class="reflection-meta-row">
            <span class={reflection.return_pct >= 0 ? "text-gain" : "text-loss"}>{formatPercent(reflection.return_pct)}</span>
            <span class="dot">·</span>
            <span>{formatDate(reflection.created_at)}</span>
            {#if reflection.market}
              <span class="dot">·</span>
              <span>{reflection.market}</span>
            {/if}
          </div>
        </div>
      </div>

      <div class="card reflection-report-card">
        <div class="card-header">
          <h3>회고 리포트</h3>
        </div>
        <div class="card-body reflection-report-body markdown-body">
          {@html renderMd(reflection.reflection)}
        </div>
      </div>

      <div class="card reflection-lessons-card">
        <div class="card-header">
          <h3>핵심 교훈</h3>
        </div>
        <div class="card-body reflection-lessons-body markdown-body">
          {@html renderMd(reflection.key_lessons)}
        </div>
      </div>
    {/if}
  </div>
</section>

<style>
  .reflection-page-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .back-link {
    color: var(--text-dim);
    text-decoration: none;
    font-size: 1.25rem;
    line-height: 1;
  }

  .back-link:hover {
    color: var(--text);
  }

  .reflection-detail-top {
    margin-bottom: 12px;
  }

  .reflection-top-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .reflection-top-left {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .reflection-meta-row {
    margin-top: 8px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 0.8125rem;
    color: var(--text-dim);
  }

  .dot {
    opacity: 0.6;
  }

  .reflection-report-card,
  .reflection-lessons-card {
    margin-top: 12px;
  }

  .reflection-report-body,
  .reflection-lessons-body {
    padding: 18px;
    font-size: 0.9rem;
    line-height: 1.8;
    color: var(--text-secondary);
  }
</style>
