<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";

  type Report = {
    id: number;
    created_at: string;
    final_trade_decision?: string;
    investment_plan?: string;
  };

  let ticker = "";
  let loading = true;
  let error = "";
  let reports: Report[] = [];

  const mapDecision = (value?: string | null) => {
    if (!value) return "-";
    if (value.toUpperCase().includes("BUY")) return "Buy";
    if (value.toUpperCase().includes("SELL")) return "Sell";
    if (value.toUpperCase().includes("HOLD")) return "Hold";
    return value;
  };

  const loadReports = async (t: string) => {
    loading = true;
    error = "";
    try {
      reports = (await fetchReportsByTicker(t)) as Report[];
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load archive.");
    } finally {
      loading = false;
    }
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadReports(ticker);
  }

  onMount(() => {
    if (ticker) loadReports(ticker);
  });
</script>

<section class="page" id="page-archive">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker} Archive</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">Loading...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if reports.length === 0}
      <div class="card" style="padding:16px">No reports yet.</div>
    {:else}
      <div class="archive-list">
        {#each reports as report}
          <div class="card archive-card">
            <div class="archive-top">
              <div style="display:flex;align-items:center;gap:8px">
                <span class="cycle-badge">Report #{report.id}</span>
                <span class="badge badge-gain">{mapDecision(report.final_trade_decision)}</span>
              </div>
              <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(report.created_at)}</span>
            </div>
            <div class="archive-details">
              <span>{report.investment_plan || report.final_trade_decision || ""}</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>
