<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { formatDateTime } from "../lib/utils/format";

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
    if (value.toUpperCase().includes("BUY")) return "매수";
    if (value.toUpperCase().includes("SELL")) return "매도";
    if (value.toUpperCase().includes("HOLD")) return "관망";
    return value;
  };

  const loadReports = async (t: string) => {
    loading = true;
    error = "";
    try {
      reports = (await fetchReportsByTicker(t)) as Report[];
    } catch (err) {
      error = err instanceof Error ? err.message : "불러오지 못했습니다.";
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
      <h2>{ticker} 아카이브</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card" style="padding:16px">{error}</div>
    {:else if reports.length === 0}
      <div class="card" style="padding:16px">리포트가 없습니다.</div>
    {:else}
      <div class="archive-list">
        {#each reports as report}
          <div class="card archive-card">
            <div class="archive-top">
              <div style="display:flex;align-items:center;gap:8px">
                <span class="cycle-badge">리포트 #{report.id}</span>
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
