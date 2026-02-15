<script lang="ts">
  import { searchMemories } from "../lib/api/endpoints";

  type MemoryResult = {
    rrf_score?: number;
    situation?: string;
    recommendation?: string;
    metadata?: {
      ticker?: string;
      return_pct?: number;
      outcome_label?: string;
      outcome?: string;
    };
  };

  let query = "반도체 모멘텀 전략";
  let loading = false;
  let error = "";
  let results: MemoryResult[] = [];

  const runSearch = async () => {
    if (!query.trim()) return;
    loading = true;
    error = "";
    try {
      results = (await searchMemories(query)) as MemoryResult[];
    } catch (err) {
      error = err instanceof Error ? err.message : "검색 실패";
    } finally {
      loading = false;
    }
  };
</script>

<section class="page" id="page-search">
  <div class="page-container">
    <div class="page-header">
      <h2>메모리 검색</h2>
    </div>

    <div class="search-form">
      <div class="search-controls">
        <input
          type="text"
          class="input"
          bind:value={query}
          placeholder="매매 메모리 검색..."
          on:keydown={(e) => e.key === "Enter" && runSearch()}
        />
        <button class="btn btn-primary" on:click={runSearch} disabled={loading}>검색</button>
      </div>
    </div>

    <div class="search-results" id="searchResults">
      {#if loading}
        <div class="results-count">검색 중...</div>
      {:else if error}
        <div class="results-count">{error}</div>
      {:else}
        <div class="results-count">검색 결과 {results.length}건</div>

        {#if results.length === 0}
          <div class="card result-card">결과가 없습니다.</div>
        {:else}
          {#each results as result}
            <div class="card result-card">
              <div class="result-top">
                <span class={`outcome-badge ${result.metadata?.outcome === "loss" ? "outcome-lose" : "outcome-win"}`}>
                  {result.metadata?.outcome_label || (result.metadata?.outcome === "loss" ? "⚠️ 실패" : "✅ 성공")}
                </span>
                <span class="ticker-badge">{result.metadata?.ticker || "-"}</span>
                <span class="rrf-score">RRF: {result.rrf_score?.toFixed(2) ?? "-"}</span>
              </div>
              <div class="result-meta">
                <span style="font-size:0.8125rem;color:var(--text-dim)">
                  수익률: {result.metadata?.return_pct != null ? `${result.metadata?.return_pct.toFixed(2)}%` : "-"}
                </span>
              </div>
              <div class="result-content">
                {#if result.situation}
                  <div class="result-section">
                    <strong>상황</strong>
                    <p>{result.situation}</p>
                  </div>
                {/if}
                {#if result.recommendation}
                  <div class="result-section">
                    <strong>권고</strong>
                    <p>{result.recommendation}</p>
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      {/if}
    </div>
  </div>
</section>
