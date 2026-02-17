<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import {
    fetchPositionDetail,
    fetchPositions,
    fetchPositionsMarket,
    fetchReportsByTicker,
  } from "../lib/api/endpoints";
  import { formatMoney, formatMoneyPlain, formatPercent, formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { marked } from "marked";
  import DOMPurify from "dompurify";

  type PositionMarket = {
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  type PositionDetail = {
    position: { id: number; ticker: string; shares: number; avg_cost: number | null };
    trades: Array<{ id: number; action: string; shares: number; price: number; executed_at: string }>;
    reports: Array<{
      id: number;
      created_at: string;
      scheduled_cycle?: number;
      final_trade_decision?: string;
      investment_plan?: string;
    }>;
  };

  let ticker = "";
  let loading = true;
  let error = "";
  let summary: PositionMarket | null = null;
  let reports: PositionDetail["reports"] = [];
  let tab: "report" | "history" = "report";
  let totalAmount: number | null = null;
  let selectedHistoryId = "";

  const mapDecision = (value?: string | null) => {
    if (!value) return "-";
    if (value.toUpperCase().includes("BUY")) return "매수";
    if (value.toUpperCase().includes("SELL")) return "매도";
    if (value.toUpperCase().includes("HOLD")) return "관망";
    return value;
  };

  const getDecisionClass = (value?: string | null) => {
    if (!value) return "badge badge-muted";
    const upper = value.toUpperCase();
    if (upper.includes("BUY") || value.includes("매수")) return "badge badge-gain";
    if (upper.includes("SELL") || value.includes("매도")) return "badge badge-loss";
    if (upper.includes("HOLD") || value.includes("관망")) return "badge badge-muted";
    return "badge badge-muted";
  };

  const loadDetail = async (t: string) => {
    loading = true;
    error = "";
    try {
      const positionsMarket = (await fetchPositionsMarket()) as PositionMarket[];
      summary = positionsMarket.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;

      const active = (await fetchPositions("active")) as Array<{ id: number; ticker: string }>;
      let target = active.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;
      if (!target) {
        const closed = (await fetchPositions("closed")) as Array<{ id: number; ticker: string }>;
        target = closed.find((p) => p.ticker.toLowerCase() === t.toLowerCase()) || null;
      }
      if (!target) {
        reports = (await fetchReportsByTicker(t)) as PositionDetail["reports"];
        selectedHistoryId = "";
        return;
      }

      const detail = (await fetchPositionDetail(target.id)) as PositionDetail;
      reports = detail.reports || [];
      selectedHistoryId = "";
    } catch (err) {
      error = formatErrorMessage(err, "데이터를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadDetail(ticker);
  }

  $: totalAmount = summary?.avg_cost ? summary.avg_cost * summary.shares : null;

  const latestReport = () => {
    if (!reports || reports.length === 0) return null;
    return [...reports].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  };

  const sortedReports = () => {
    const list = [...reports];
    list.sort((a, b) => {
      const aCycle = a.scheduled_cycle ?? -1;
      const bCycle = b.scheduled_cycle ?? -1;
      if (aCycle !== bCycle) return bCycle - aCycle;
      return b.created_at.localeCompare(a.created_at);
    });
    return list;
  };

  const getReportTitle = (report?: PositionDetail["reports"][number] | null) => {
    if (!report) return "";
    if (report.scheduled_cycle !== undefined && report.scheduled_cycle !== null) {
      return `${report.scheduled_cycle} 회차`;
    }
    return `AI분석 #${report.id}`;
  };

  const getReportBody = (report?: PositionDetail["reports"][number] | null) => {
    if (!report) return "";
    return report.final_trade_decision || "";
  };

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>데이터 없음</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

  const selectHistory = (reportId: string) => {
    selectedHistoryId = selectedHistoryId === reportId ? "" : reportId;
  };

  onMount(() => {
    if (ticker) loadDetail(ticker);
  });

</script>

<section class="page" id="page-trade">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker}</h2>
      <span class={`pnl-banner ${summary && summary.return_pct >= 0 ? "pnl-pos" : "pnl-neg"}`}>
        {summary ? formatPercent(summary.return_pct) : "-"}
      </span>
    </div>

    <div class="card-grid" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header">
          <h3>투자</h3>
        </div>
        <div class="card-body">
          <div class="stat-row"><span class="stat-label">보유</span><span class="stat-value">{summary?.shares ?? "-"}</span></div>
          <div class="stat-row"><span class="stat-label">1주 평균</span><span class="stat-value">{summary?.avg_cost ? `$${summary.avg_cost.toFixed(2)}` : "-"}</span></div>
          <div class="stat-row">
            <span class="stat-label">총 금액</span>
            <span class="stat-value">
              {#if totalAmount !== null}
                {formatMoneyPlain(totalAmount)}
                <span class={summary && summary.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                  ({summary ? formatMoney(summary.pnl) : "-"})
                </span>
              {:else}
                -
              {/if}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="tab-bar">
      <button class={`tab-btn ${tab === "report" ? "active" : ""}`} on:click={() => (tab = "report")}>최신 AI분석</button>
      <button class={`tab-btn ${tab === "history" ? "active" : ""}`} on:click={() => (tab = "history")}>기록</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if tab === "report"}
        {#if latestReport()}
          <div class="card" style="margin-bottom:12px">
            <div class="card-body">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                <span class={getDecisionClass(latestReport()?.final_trade_decision)}>
                  {mapDecision(latestReport()?.final_trade_decision)}
                </span>
                <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(latestReport()?.created_at)}</span>
              </div>
              <div class="report-content markdown-body">
                {@html renderMd(getReportBody(latestReport()))}
              </div>
            </div>
          </div>
        {:else}
          <div class="card" style="padding:16px">AI분석이 없습니다.</div>
        {/if}
    {:else}
      <div class="history-list">
        {#if reports.length === 0}
          <div class="card history-entry">
            <div class="history-action">기록이 없습니다.</div>
          </div>
        {:else}
          {#each sortedReports() as report}
            <div class="card history-entry">
              <button
                class="history-toggle"
                type="button"
                on:click={() => selectHistory(String(report.id))}
              >
                <div class="history-top">
                  <span class="history-no">{getReportTitle(report)}</span>
                  <span class="history-date">{formatDateTime(report.created_at)}</span>
                  <span class="badge badge-gain">{mapDecision(report.final_trade_decision)}</span>
                </div>
              </button>
              {#if selectedHistoryId === String(report.id)}
                <div class="history-detail report-content markdown-body">
                  {@html renderMd(getReportBody(report))}
                </div>
              {/if}
            </div>
          {/each}
        {/if}
      </div>
    {/if}
  </div>
</section>
