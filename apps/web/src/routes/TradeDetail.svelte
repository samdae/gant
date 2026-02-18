<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import {
    fetchPositionDetail,
    fetchPositions,
    fetchPositionsMarket,
    fetchReportsByTicker,
    fetchPositionGraph,
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
    position: { id: number; ticker: string; shares: number; avg_cost: number | null; opened_at?: string | null };
    trades: Array<{ id: number; action: string; shares: number; price: number; executed_at: string }>;
    reports: Array<{
      id: number;
      created_at: string;
      scheduled_cycle?: number;
      final_trade_decision?: string;
      investment_plan?: string;
    }>;
  };

  type ChartStats = {
    last: number | null;
    change: number | null;
    changePct: number | null;
    high: number | null;
    low: number | null;
    startLabel: string;
    endLabel: string;
    count: number;
  };

  let ticker = "";
  let loading = true;
  let error = "";
  let summary: PositionMarket | null = null;
  let reports: PositionDetail["reports"] = [];
  let tab: "report" | "history" = "report";
  let totalAmount: number | null = null;
  let selectedHistoryId = "";
  let positionId: number | null = null;
  let positionOpenedAt: string | null = null;
  let chartPoints: Array<{ x: number; y: number }> = [];
  let chartLinePath = "";
  let chartAreaPath = "";
  let chartYLabels: Array<{ y: number; label: string }> = [];
  let chartXLabels: Array<{ x: number; label: string; anchor: "start" | "end" | "middle" }> = [];
  let chartBaselineY = 0;
  let chartLastPoint: { x: number; y: number; value: number } | null = null;
  let chartEntryPoint: { x: number; y: number } | null = null;
  let chartTrend: "up" | "down" | "flat" = "flat";
  let chartStats: ChartStats = {
    last: null,
    change: null,
    changePct: null,
    high: null,
    low: null,
    startLabel: "",
    endLabel: "",
    count: 0,
  };
  let chartLoading = false;

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
    chartLinePath = "";
    chartAreaPath = "";
    chartPoints = [];
    chartYLabels = [];
    chartXLabels = [];
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
        positionId = null;
        positionOpenedAt = null;
        selectedHistoryId = "";
        return;
      }

      positionId = target.id;

      const detail = (await fetchPositionDetail(target.id)) as PositionDetail;
      reports = detail.reports || [];
      positionOpenedAt = detail.position?.opened_at || null;
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

  const formatChartDate = (value: string) => {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) {
      return `${date.getMonth() + 1}.${date.getDate()}`;
    }
    const match = String(value).match(/(\d{4})-(\d{2})-(\d{2})/);
    if (match) return `${Number(match[2])}.${Number(match[3])}`;
    return String(value).slice(0, 5);
  };

  const formatChartAxisValue = (value: number) => Math.round(value).toLocaleString();

  const buildChartXLabels = (points: Array<{ date: string; close: number | null }>) => {
    const count = points.length;
    if (count === 0) return [] as Array<{ x: number; label: string; anchor: "start" | "end" | "middle" }>;
    const indices =
      count >= 5
        ? [
            0,
            Math.floor((count - 1) / 4),
            Math.floor((count - 1) / 2),
            Math.floor(((count - 1) * 3) / 4),
            count - 1,
          ]
        : Array.from({ length: count }, (_, idx) => idx);
    const width = 120;
    const left = 12;
    const right = 6;
    const plotWidth = width - left - right;
    return indices.map((idx, position) => {
      const x = count === 1 ? left + plotWidth / 2 : left + (idx / (count - 1)) * plotWidth;
      const anchor = position === 0 ? ("start" as const) : position === indices.length - 1 ? ("end" as const) : ("middle" as const);
      return { x, label: formatChartDate(points[idx].date), anchor };
    });
  };

  const buildChart = (points: Array<{ date: string; close: number | null }>) => {
    const validPoints = points.filter((p) => typeof p.close === "number") as Array<{
      date: string;
      close: number;
    }>;
    if (validPoints.length === 0) {
      chartPoints = [];
      chartLinePath = "";
      chartAreaPath = "";
      chartYLabels = [];
      chartXLabels = [];
      chartBaselineY = 0;
      chartLastPoint = null;
      chartEntryPoint = null;
      chartTrend = "flat";
      chartStats = {
        last: null,
        change: null,
        changePct: null,
        high: null,
        low: null,
        startLabel: "",
        endLabel: "",
        count: 0,
      };
      return;
    }

    const values = validPoints.map((p) => p.close);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = Math.max((max - min) * 0.08, max * 0.01, 1);
    const yMin = min - pad;
    const yMax = max + pad;
    const range = yMax - yMin || 1;

    const width = 120;
    const height = 70;
    const left = 12;
    const right = 6;
    const top = 8;
    const bottom = 14;
    const plotWidth = width - left - right;
    const plotHeight = height - top - bottom;
    chartBaselineY = top + plotHeight;

    const len = points.length;
    const mapped = points.map((p, idx) => {
      const value = typeof p.close === "number" ? p.close : null;
      const x = len === 1 ? left + plotWidth / 2 : left + (idx / (len - 1)) * plotWidth;
      if (value === null) return null;
      const y = top + (1 - (value - yMin) / range) * plotHeight;
      return { x, y, value, date: p.date };
    });

    const mappedPoints = mapped.filter(Boolean) as Array<{ x: number; y: number; value: number; date: string }>;
    chartPoints = mappedPoints.map((p) => ({ x: p.x, y: p.y }));
    chartLastPoint = mappedPoints.length > 0 ? mappedPoints[mappedPoints.length - 1] : null;
    chartLinePath = mappedPoints.map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

    const entryDate = positionOpenedAt ? new Date(positionOpenedAt) : null;
    if (entryDate) entryDate.setDate(entryDate.getDate() + 1);
    const entryIndex = entryDate
      ? points.findIndex((p) => new Date(p.date) >= entryDate)
      : -1;

    if (entryIndex >= 0) {
      const areaPoints = mapped.slice(entryIndex).filter(Boolean) as Array<{
        x: number;
        y: number;
        value: number;
        date: string;
      }>;
      if (areaPoints.length > 0) {
        const areaStart = areaPoints[0];
        const areaEnd = areaPoints[areaPoints.length - 1];
        chartAreaPath = `M ${areaStart.x} ${chartBaselineY} L ${areaPoints
          .map((p) => `${p.x} ${p.y}`)
          .join(" L ")} L ${areaEnd.x} ${chartBaselineY} Z`;
        chartEntryPoint = { x: areaStart.x, y: areaStart.y };
      } else {
        chartAreaPath = "";
        chartEntryPoint = null;
      }
    } else {
      chartAreaPath = "";
      chartEntryPoint = null;
    }

    const entryValue = chartEntryPoint
      ? (mapped.slice(entryIndex).find(Boolean) as { value: number } | undefined)?.value ?? null
      : null;
    const baseValue = entryValue ?? validPoints[0].close;
    const lastValue = validPoints[validPoints.length - 1].close;
    const changeValue = baseValue !== null ? lastValue - baseValue : null;
    const changePct = baseValue && changeValue !== null ? (changeValue / baseValue) * 100 : null;
    chartTrend = typeof changeValue === "number" && changeValue !== 0 ? (changeValue > 0 ? "up" : "down") : "flat";
    chartStats = {
      last: lastValue,
      change: changeValue,
      changePct,
      high: max,
      low: min,
      startLabel: formatChartDate(points[0].date),
      endLabel: formatChartDate(points[points.length - 1].date),
      count: validPoints.length,
    };

    const mid = (yMin + yMax) / 2;
    chartYLabels = [
      { y: top, label: formatChartAxisValue(yMax) },
      { y: top + plotHeight / 2, label: formatChartAxisValue(mid) },
      { y: top + plotHeight, label: formatChartAxisValue(yMin) },
    ];

    chartXLabels = buildChartXLabels(points);
  };

  const loadChart = async () => {
    if (!positionId) return;
    chartLoading = true;
    try {
      const res = (await fetchPositionGraph(positionId)) as {
        points: Array<{ date: string; close: number | null }>;
      };
      buildChart(res.points || []);
    } catch {
      chartPoints = [];
      chartLastPoint = null;
      chartTrend = "flat";
      chartEntryPoint = null;
      chartStats = {
        last: null,
        change: null,
        changePct: null,
        high: null,
        low: null,
        startLabel: "",
        endLabel: "",
        count: 0,
      };
    } finally {
      chartLoading = false;
    }
  };

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

  $: if (positionId && positionOpenedAt) {
    loadChart();
  }

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

      <div class={`price-panel ${chartTrend}`}>
        <div class="price-panel-top">
          <div class="price-panel-title">
            <span class="price-panel-label">가격</span>
            {#if chartStats.count > 0}
              <span class="price-panel-period">{chartStats.startLabel} - {chartStats.endLabel}</span>
            {/if}
          </div>
          {#if chartPoints.length > 0}
            <div class="price-panel-live">
              <span class="price-panel-live-dot"></span>
              LIVE
            </div>
          {/if}
        </div>
        <div class="price-panel-summary">
          <div class="price-panel-price">
            {chartStats.last !== null ? formatMoneyPlain(chartStats.last) : "-"}
          </div>
        </div>
        {#if chartLoading}
          <div class="empty-state">차트 불러오는 중...</div>
        {:else if chartLinePath === ""}
          <div class="empty-state">차트 데이터가 없습니다.</div>
        {:else}
          <svg viewBox="0 0 120 70" preserveAspectRatio="none" class="price-chart">
            <defs>
              <linearGradient id="chart-area-gradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="var(--chart-area-top)" stop-opacity="0.9" />
                <stop offset="100%" stop-color="var(--chart-area-bottom)" stop-opacity="0.1" />
              </linearGradient>
            </defs>
            {#each chartYLabels as label}
              <text class="chart-label" x="0" y={label.y + 3}>{label.label}</text>
            {/each}
            {#each chartXLabels as label}
              <text class="chart-label" x={label.x} y="67" text-anchor={label.anchor}>{label.label}</text>
            {/each}
            <line class="chart-axis" x1="12" y1={chartBaselineY} x2="114" y2={chartBaselineY} />
            {#if chartAreaPath}
              <path class="chart-area" d={chartAreaPath} />
            {/if}
            <path class="chart-line" d={chartLinePath} />
            {#if chartEntryPoint}
              <line
                class="chart-entry-line"
                x1={chartEntryPoint.x}
                y1={chartEntryPoint.y}
                x2={chartEntryPoint.x}
                y2={chartBaselineY}
              />
            {/if}
            {#if chartLastPoint}
              <circle class="chart-point-halo" cx={chartLastPoint.x} cy={chartLastPoint.y} r="3.2" />
              <circle class="chart-point" cx={chartLastPoint.x} cy={chartLastPoint.y} r="1.8" />
            {/if}
          </svg>
        {/if}
        {#if chartStats.count > 0}
          <div class="price-panel-footer">
            <div class="price-panel-stat">
              <span>고가</span>
              <strong>{formatMoneyPlain(chartStats.high)}</strong>
            </div>
            <div class="price-panel-stat">
              <span>저가</span>
              <strong>{formatMoneyPlain(chartStats.low)}</strong>
            </div>
          </div>
        {/if}
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
    {:else}
      {#if tab === "report"}
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
    {/if}
  </div>
</section>
