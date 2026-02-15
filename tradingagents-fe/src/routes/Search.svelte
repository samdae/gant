<script lang="ts">
  import { searchMemories } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";

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

  let query = "Semiconductor momentum strategy";
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
      error = formatErrorMessage(err, "Search failed.");
    } finally {
      loading = false;
    }
  };
</script>

<section class="page" id="page-search">
  <div class="page-container">
    <div class="page-header">
      <h2>Search</h2>
    </div>

    <div class="search-form">
      <div class="search-controls">
        <input
          type="text"
          class="input"
          bind:value={query}
          placeholder="Search memory..."
          on:keydown={(e) => e.key === "Enter" && runSearch()}
        />
        <button class="btn btn-primary" on:click={runSearch} disabled={loading}>Search</button>
      </div>
    </div>

    <div class="search-results" id="searchResults">
      {#if loading}
        <div class="results-count">Searching...</div>
      {:else if error}
        <div class="results-count error-text">{error}</div>
      {:else}
        <div class="results-count">Results {results.length}</div>

        {#if results.length === 0}
          <div class="card result-card">No results.</div>
        {:else}
          {#each results as result}
            <div class="card result-card">
              <div class="result-top">
                <span class={`outcome-badge ${result.metadata?.outcome === "loss" ? "outcome-lose" : "outcome-win"}`}>
                  {result.metadata?.outcome_label || (result.metadata?.outcome === "loss" ? "Loss" : "Win")}
                </span>
                <span class="ticker-badge">{result.metadata?.ticker || "-"}</span>
                <span class="rrf-score">RRF: {result.rrf_score?.toFixed(2) ?? "-"}</span>
              </div>
              <div class="result-meta">
                <span style="font-size:0.8125rem;color:var(--text-dim)">
                  Return: {result.metadata?.return_pct != null ? `${result.metadata?.return_pct.toFixed(2)}%` : "-"}
                </span>
              </div>
              <div class="result-content">
                {#if result.situation}
                  <div class="result-section">
                    <strong>Situation</strong>
                    <p>{result.situation}</p>
                  </div>
                {/if}
                {#if result.recommendation}
                  <div class="result-section">
                    <strong>Recommendation</strong>
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
