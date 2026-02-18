<script lang="ts">
  import { onMount, onDestroy } from "svelte";
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

  type OHLCPoint = {
    date: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    volume: number | null;
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
    isToday: boolean;
  };

  /* ── fixed layout constants ── */
  const Y_AXIS_W = 44;          // fixed Y-axis width in px (rendered via separate SVG)
  const CHART_H = 200;          // total chart height in px
  const PRICE_RATIO = 0.78;     // price area takes 78% of height
  const VOL_RATIO = 0.15;       // volume area takes 15%
  const GAP_RATIO = 0.07;       // gap between price and volume

  const PRICE_H = CHART_H * PRICE_RATIO;
  const VOL_H = CHART_H * VOL_RATIO;
  const GAP_H = CHART_H * GAP_RATIO;
  const PAD_TOP = 12;
  const PAD_BOTTOM = 20;
  const PLOT_H = PRICE_H - PAD_TOP - 4;
  const VOL_TOP = PRICE_H + GAP_H;

  /* ── zoom ── */
  const MIN_PW = 8;            // minimum point width (zoomed out max)
  const MAX_PW = 40;           // maximum point width (zoomed in max)
  const DEFAULT_PW = 14;       // default point width per data point
  let pointWidth = DEFAULT_PW;

  let ticker = "";
  let loading = true;
  let error = "";
  let summary: PositionMarket | null = null;
  let reports: PositionDetail["reports"] = [];
  let trades: PositionDetail["trades"] = [];
  let tab: "report" | "history" = "report";
  let totalAmount: number | null = null;
  let selectedHistoryId = "";
  let positionId: number | null = null;
  let positionOpenedAt: string | null = null;
  let avgCost: number | null = null;

  /* ── chart state ── */
  let rawPoints: OHLCPoint[] = [];
  let chartMode: "line" | "candle" = "candle";
  let chartTrend: "up" | "down" | "flat" = "flat";
  let chartStats: ChartStats = {
    last: null, change: null, changePct: null,
    high: null, low: null,
    startLabel: "", endLabel: "",
    count: 0, isToday: false,
  };
  let chartLoading = false;

  /* ── derived chart data (recomputed on zoom or data change) ── */
  let svgWidth = 0;
  let chartLinePath = "";
  let chartAreaPath = "";
  let chartBaselineY = 0;
  let chartLastPoint: { x: number; y: number; value: number } | null = null;
  let chartEntryPoint: { x: number; y: number } | null = null;

  type CandleBar = { x: number; w: number; bodyTop: number; bodyBottom: number; wickTop: number; wickBottom: number; up: boolean };
  let candles: CandleBar[] = [];

  type VolumeBar = { x: number; w: number; y: number; h: number; up: boolean };
  let volumeBars: VolumeBar[] = [];

  /* Y-axis (fixed, doesn't scroll) */
  let yAxisLabels: Array<{ y: number; label: string }> = [];
  let yGridLines: number[] = [];

  /* X-axis labels (inside scrollable area) */
  let xAxisLabels: Array<{ x: number; label: string; anchor: "start" | "end" | "middle" }> = [];

  type MappedPoint = { x: number; y: number; value: number; date: string; idx: number };
  let mappedPoints: MappedPoint[] = [];

  /* trade markers */
  type TradeMarker = { x: number; y: number; price: number; action: "buy" | "sell"; shares: number; date: string };
  let tradeMarkers: TradeMarker[] = [];
  let avgCostLineY: number | null = null;

  /* crosshair */
  let crosshair: { visible: boolean; x: number; y: number; price: string; date: string; labelY: number } =
    { visible: false, x: 0, y: 0, price: "", date: "", labelY: 0 };

  /* DOM refs */
  let scrollContainerEl: HTMLDivElement;
  let chartSvgEl: SVGSVGElement;

  /* pinch zoom state */
  let pinchStartDist = 0;
  let pinchStartPW = DEFAULT_PW;

  /* ── helpers ── */
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

  const formatChartDate = (value: string) => {
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return `${date.getMonth() + 1}/${date.getDate()}`;
    const match = String(value).match(/(\d{4})-(\d{2})-(\d{2})/);
    if (match) return `${Number(match[2])}/${Number(match[3])}`;
    return String(value).slice(0, 5);
  };

  /** Extract YYYY-MM-DD from any string (handles pandas Series format) */
  const extractDateStr = (value: string): string | null => {
    const match = String(value).match(/(\d{4}-\d{2}-\d{2})/);
    return match ? match[1] : null;
  };

  const formatAxisVal = (value: number) => {
    if (value >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (value >= 100) return value.toFixed(0);
    if (value >= 1) return value.toFixed(1);
    return value.toFixed(2);
  };

  const isDateToday = (dateStr: string): boolean => {
    const d = new Date();
    return dateStr === `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };

  /* ── data loading ── */
  const loadDetail = async (t: string) => {
    loading = true;
    error = "";
    resetChart();
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
      trades = detail.trades || [];
      positionOpenedAt = detail.position?.opened_at || null;
      avgCost = detail.position?.avg_cost ?? summary?.avg_cost ?? null;
      selectedHistoryId = "";
    } catch (err) {
      error = formatErrorMessage(err, "데이터를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  $: if ($params?.ticker) { ticker = String($params.ticker).toUpperCase(); }
  $: if (ticker) { loadDetail(ticker); }
  $: totalAmount = summary?.avg_cost ? summary.avg_cost * summary.shares : null;

  /* ── chart building ── */
  const resetChart = () => {
    rawPoints = [];
    mappedPoints = [];
    candles = [];
    volumeBars = [];
    tradeMarkers = [];
    avgCostLineY = null;
    chartLinePath = "";
    chartAreaPath = "";
    yAxisLabels = [];
    yGridLines = [];
    xAxisLabels = [];
    chartLastPoint = null;
    chartEntryPoint = null;
    chartTrend = "flat";
    chartStats = { last: null, change: null, changePct: null, high: null, low: null, startLabel: "", endLabel: "", count: 0, isToday: false };
  };

  /** Core render — called whenever rawPoints or pointWidth changes */
  const renderChart = () => {
    if (rawPoints.length === 0) return;
    const points = rawPoints;
    const validPoints = points.filter((p) => typeof p.close === "number") as Array<OHLCPoint & { close: number }>;
    if (validPoints.length === 0) return;

    const len = points.length;
    const pw = pointWidth;
    const PAD_LEFT = 6;   // small left padding inside scrollable area
    const PAD_RIGHT = 8;
    const chartW = PAD_LEFT + len * pw + PAD_RIGHT;
    svgWidth = chartW;

    /* price range */
    const allHighs = validPoints.map((p) => p.high ?? p.close);
    const allLows = validPoints.map((p) => (p.low ?? p.close));
    const min = Math.min(...allLows);
    const max = Math.max(...allHighs);
    const pad = Math.max((max - min) * 0.08, max * 0.01, 1);
    const yMin = min - pad;
    const yMax = max + pad;
    const range = yMax - yMin || 1;

    chartBaselineY = PAD_TOP + PLOT_H;

    const toY = (v: number) => PAD_TOP + (1 - (v - yMin) / range) * PLOT_H;
    const toX = (idx: number) => PAD_LEFT + idx * pw + pw / 2;
    const barW = Math.min(pw * 0.65, 10);

    /* line points */
    const mapped: MappedPoint[] = [];
    points.forEach((p, idx) => {
      if (typeof p.close !== "number") return;
      mapped.push({ x: toX(idx), y: toY(p.close), value: p.close, date: p.date, idx });
    });
    mappedPoints = mapped;
    chartLastPoint = mapped.length > 0 ? mapped[mapped.length - 1] : null;
    chartLinePath = mapped.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");

    /* candles */
    const cArr: CandleBar[] = [];
    points.forEach((p, idx) => {
      if (p.open == null || p.close == null) return;
      const o = p.open; const c = p.close;
      const h = p.high ?? Math.max(o, c); const l = p.low ?? Math.min(o, c);
      const up = c >= o;
      const bodyH = Math.max(Math.abs(toY(Math.min(o, c)) - toY(Math.max(o, c))), 0.8);
      cArr.push({
        x: toX(idx) - barW / 2, w: barW,
        bodyTop: toY(Math.max(o, c)), bodyBottom: toY(Math.max(o, c)) + bodyH,
        wickTop: toY(h), wickBottom: toY(l), up,
      });
    });
    candles = cArr;

    /* volume */
    const volumes = points.map((p) => p.volume ?? 0).filter((v) => v > 0);
    const maxVol = volumes.length > 0 ? Math.max(...volumes) : 1;
    const vArr: VolumeBar[] = [];
    points.forEach((p, idx) => {
      if (!p.volume || p.volume <= 0) return;
      const vh = (p.volume / maxVol) * VOL_H;
      const up = (p.close ?? 0) >= (p.open ?? 0);
      vArr.push({ x: toX(idx) - barW / 2, w: barW, y: VOL_TOP + VOL_H - vh, h: vh, up });
    });
    volumeBars = vArr;

    /* entry point area fill */
    const entryDateStr = positionOpenedAt ? positionOpenedAt.slice(0, 10) : null; // "YYYY-MM-DD"
    let entryIdx = -1;

    // match opened_at date against chart data dates
    if (entryDateStr) {
      entryIdx = points.findIndex((p) => {
        const pd = extractDateStr(p.date);
        return pd != null && pd >= entryDateStr;
      });
    }

    // fallback 1: use earliest buy trade date in chart
    if (entryIdx < 0 && trades.length > 0) {
      const buyTrades = trades
        .filter((t) => t.action.toUpperCase().includes("BUY"))
        .sort((a, b) => a.executed_at.localeCompare(b.executed_at));
      for (const bt of buyTrades) {
        const btDate = bt.executed_at.slice(0, 10);
        const idx = points.findIndex((p) => extractDateStr(p.date) === btDate);
        if (idx >= 0) { entryIdx = idx; break; }
      }
    }

    // fallback 2: entry/trade date is AFTER the last chart data point → use last point
    if (entryIdx < 0) {
      const lastChartDateStr = extractDateStr(points[points.length - 1].date);
      const checkDateStr = entryDateStr ?? (trades.length > 0 ? trades[0].executed_at.slice(0, 10) : null);
      if (lastChartDateStr && checkDateStr && checkDateStr > lastChartDateStr) {
        entryIdx = points.length - 1;
      }
    }


    if (entryIdx >= 0) {
      const areaPoints = mapped.filter((mp) => mp.idx >= entryIdx);
      if (areaPoints.length > 0) {
        const s = areaPoints[0]; const e = areaPoints[areaPoints.length - 1];
        chartAreaPath = `M ${s.x.toFixed(1)} ${chartBaselineY} L ${areaPoints.map((p) => `${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" L ")} L ${e.x.toFixed(1)} ${chartBaselineY} Z`;
        chartEntryPoint = { x: s.x, y: s.y };
        console.log("[ENTRY DEBUG] chartEntryPoint SET:", chartEntryPoint);
      } else { chartAreaPath = ""; chartEntryPoint = null; console.log("[ENTRY DEBUG] areaPoints empty!"); }
    } else { chartAreaPath = ""; chartEntryPoint = null; console.log("[ENTRY DEBUG] entryIdx < 0, no entry point"); }

    /* trend & stats */
    const entryValue = chartEntryPoint && entryIdx >= 0 ? (mapped.find((mp) => mp.idx >= entryIdx)?.value ?? null) : null;
    const baseValue = entryValue ?? validPoints[0].close;
    const lastValue = validPoints[validPoints.length - 1].close;
    const changeValue = baseValue !== null ? lastValue - baseValue : null;
    const changePct = baseValue && changeValue !== null ? (changeValue / baseValue) * 100 : null;
    chartTrend = typeof changeValue === "number" && changeValue !== 0 ? (changeValue > 0 ? "up" : "down") : "flat";

    const lastDate = points[points.length - 1]?.date ?? "";
    chartStats = {
      last: lastValue, change: changeValue, changePct,
      high: max, low: min,
      startLabel: formatChartDate(points[0].date),
      endLabel: formatChartDate(lastDate),
      count: validPoints.length,
      isToday: isDateToday(lastDate),
    };

    /* Y-axis labels & grid (these are in px coords matching the fixed SVG) */
    const ySteps = 4;
    const labels: typeof yAxisLabels = [];
    const grids: number[] = [];
    for (let i = 0; i <= ySteps; i++) {
      const val = yMin + (range * (ySteps - i)) / ySteps;
      const y = PAD_TOP + (i / ySteps) * PLOT_H;
      labels.push({ y, label: formatAxisVal(val) });
      grids.push(y);
    }
    yAxisLabels = labels;
    yGridLines = grids;

    /* X-axis labels */
    const step = len <= 8 ? 1 : len <= 15 ? 2 : len <= 30 ? 5 : 10;
    const xLabels: typeof xAxisLabels = [];
    for (let i = 0; i < len; i += step) {
      const isFirst = i === 0;
      const isLast = i >= len - step;
      xLabels.push({
        x: toX(i),
        label: formatChartDate(points[i].date),
        anchor: isFirst ? "start" : isLast ? "end" : "middle",
      });
    }
    // ensure last point is labeled
    if (xLabels.length > 0 && xLabels[xLabels.length - 1].x !== toX(len - 1)) {
      xLabels.push({ x: toX(len - 1), label: formatChartDate(points[len - 1].date), anchor: "end" });
    }
    xAxisLabels = xLabels;

    /* trade markers */
    const markers: TradeMarker[] = [];
    if (trades.length > 0) {
      // build a date→index map for O(1) lookups (using extracted date string)
      const dateMap = new Map<string, number>();
      points.forEach((p, idx) => {
        const d = extractDateStr(p.date);
        if (d) dateMap.set(d, idx);
      });

      for (const trade of trades) {
        const tradeDate = trade.executed_at.slice(0, 10); // "YYYY-MM-DD"
        const idx = dateMap.get(tradeDate);
        if (idx == null) continue;
        const isBuy = trade.action.toUpperCase().includes("BUY");
        const price = trade.price;
        markers.push({
          x: toX(idx),
          y: toY(price),
          price,
          action: isBuy ? "buy" : "sell",
          shares: trade.shares,
          date: tradeDate,
        });
      }
    }
    tradeMarkers = markers;

    /* avg cost horizontal line */
    if (avgCost != null && avgCost > yMin && avgCost < yMax) {
      avgCostLineY = toY(avgCost);
    } else {
      avgCostLineY = null;
    }
  };

  /** Reactively re-render when data or zoom changes */
  $: if (rawPoints.length > 0 && pointWidth && (trades || true) && (positionOpenedAt || true) && (avgCost || true)) {
    renderChart();
  }

  const loadChart = async () => {
    if (!positionId) return;
    chartLoading = true;
    try {
      const res = (await fetchPositionGraph(positionId, 30)) as { points: OHLCPoint[] };
      rawPoints = res.points || [];
      // scroll to the right (latest data) after render
      requestAnimationFrame(() => {
        if (scrollContainerEl) scrollContainerEl.scrollLeft = scrollContainerEl.scrollWidth;
      });
    } catch { resetChart(); }
    finally { chartLoading = false; }
  };

  /* ── crosshair ── */
  const handleChartPointer = (e: MouseEvent | TouchEvent) => {
    if (!chartSvgEl || mappedPoints.length === 0) return;
    // prevent scrolling while showing crosshair on single-finger touch
    const isTouchMove = "touches" in e && e.touches.length === 1;
    const rect = chartSvgEl.getBoundingClientRect();
    const clientX = "touches" in e ? e.touches[0].clientX : e.clientX;
    const svgX = ((clientX - rect.left) / rect.width) * svgWidth;

    let closest = mappedPoints[0];
    let minDist = Math.abs(svgX - closest.x);
    for (const mp of mappedPoints) {
      const d = Math.abs(svgX - mp.x);
      if (d < minDist) { closest = mp; minDist = d; }
    }

    const labelY = closest.y < PAD_TOP + 16 ? closest.y + 12 : closest.y - 6;
    crosshair = { visible: true, x: closest.x, y: closest.y, price: formatAxisVal(closest.value), date: formatChartDate(closest.date), labelY };
  };

  const handleChartLeave = () => { crosshair = { ...crosshair, visible: false }; };

  /* ── pinch zoom ── */
  const handleTouchStart = (e: TouchEvent) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      pinchStartDist = Math.sqrt(dx * dx + dy * dy);
      pinchStartPW = pointWidth;
    }
  };

  const handleTouchMove = (e: TouchEvent) => {
    if (e.touches.length === 2) {
      e.preventDefault();
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const scale = dist / pinchStartDist;
      pointWidth = Math.min(MAX_PW, Math.max(MIN_PW, Math.round(pinchStartPW * scale)));
    } else if (e.touches.length === 1) {
      handleChartPointer(e);
    }
  };

  const handleTouchEnd = (e: TouchEvent) => {
    if (e.touches.length < 2) {
      crosshair = { ...crosshair, visible: false };
    }
  };

  /* ── report helpers ── */
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
    if (report.scheduled_cycle != null) return `${report.scheduled_cycle} 회차`;
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

  onMount(() => { if (ticker) loadDetail(ticker); });

  $: if (positionId && positionOpenedAt) { loadChart(); }
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
            <span class="price-panel-period">{chartStats.startLabel} – {chartStats.endLabel}</span>
          {/if}
        </div>
        <div class="price-panel-top-right">
          {#if chartStats.isToday}
            <div class="price-panel-live"><span class="price-panel-live-dot"></span>LIVE</div>
          {:else if chartStats.endLabel}
            <div class="price-panel-lastdate">{chartStats.endLabel} 기준</div>
          {/if}
        </div>
      </div>
      <div class="price-panel-summary">
        <div class="price-panel-price">
          {chartStats.last !== null ? formatMoneyPlain(chartStats.last) : "-"}
        </div>
        {#if chartStats.count > 0}
          <div class="chart-mode-toggle">
            <button class={`chart-mode-btn ${chartMode === "candle" ? "active" : ""}`} on:click={() => (chartMode = "candle")} title="캔들 차트">
              <svg viewBox="0 0 16 16" width="14" height="14">
                <rect x="3" y="2" width="4" height="12" rx="0.5" fill="currentColor" opacity="0.25"/>
                <line x1="5" y1="0" x2="5" y2="2" stroke="currentColor" stroke-width="1.2"/>
                <line x1="5" y1="14" x2="5" y2="16" stroke="currentColor" stroke-width="1.2"/>
                <rect x="9" y="5" width="4" height="8" rx="0.5" fill="currentColor"/>
                <line x1="11" y1="2" x2="11" y2="5" stroke="currentColor" stroke-width="1.2"/>
                <line x1="11" y1="13" x2="11" y2="16" stroke="currentColor" stroke-width="1.2"/>
              </svg>
            </button>
            <button class={`chart-mode-btn ${chartMode === "line" ? "active" : ""}`} on:click={() => (chartMode = "line")} title="꺾은선 차트">
              <svg viewBox="0 0 16 16" width="14" height="14">
                <polyline points="1,12 5,6 9,9 15,3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        {/if}
      </div>

      {#if chartLoading}
        <div class="empty-state">차트 불러오는 중...</div>
      {:else if rawPoints.length === 0 && !chartLoading}
        <div class="empty-state">차트 데이터가 없습니다.</div>
      {:else}
        <!-- Chart container: fixed Y-axis + scrollable chart -->
        <div class="chart-container" style="height:{CHART_H}px">
          <!-- Fixed Y-axis -->
          <svg class="chart-yaxis" width={Y_AXIS_W} height={CHART_H} viewBox="0 0 {Y_AXIS_W} {CHART_H}">
            {#each yGridLines as gy}
              <line class="chart-grid-yaxis" x1="0" y1={gy} x2={Y_AXIS_W} y2={gy} />
            {/each}
            {#each yAxisLabels as label}
              <text class="yaxis-label" x={Y_AXIS_W - 4} y={label.y + 3} text-anchor="end">{label.label}</text>
            {/each}
            <!-- avg cost price on Y-axis -->
            {#if avgCostLineY != null && avgCost != null}
              <rect class="yaxis-avgcost-bg" x="0" y={avgCostLineY - 6} width={Y_AXIS_W} height="12" rx="2" />
              <text class="yaxis-avgcost-label" x={Y_AXIS_W - 4} y={avgCostLineY + 3} text-anchor="end">{formatAxisVal(avgCost)}</text>
            {/if}
            <!-- separator -->
            <line class="chart-vol-sep" x1="0" y1={VOL_TOP - 2} x2={Y_AXIS_W} y2={VOL_TOP - 2} />
            <text class="yaxis-vol-label" x={Y_AXIS_W - 4} y={VOL_TOP + 8} text-anchor="end">Vol</text>
          </svg>

          <!-- Scrollable chart area -->
          <div
            class="chart-scroll"
            bind:this={scrollContainerEl}
          >
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <svg
              bind:this={chartSvgEl}
              width={svgWidth}
              height={CHART_H}
              viewBox="0 0 {svgWidth} {CHART_H}"
              class="chart-main"
              on:mousemove={handleChartPointer}
              on:mouseleave={handleChartLeave}
              on:touchstart={handleTouchStart}
              on:touchmove|preventDefault={handleTouchMove}
              on:touchend={handleTouchEnd}
            >
              <defs>
                <linearGradient id="chart-area-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--chart-area-top)" stop-opacity="0.9" />
                  <stop offset="100%" stop-color="var(--chart-area-bottom)" stop-opacity="0.1" />
                </linearGradient>
              </defs>

              <!-- horizontal grid lines (extending across the scrollable area) -->
              {#each yGridLines as gy}
                <line class="chart-grid" x1="0" y1={gy} x2={svgWidth} y2={gy} />
              {/each}

              <!-- X-axis labels -->
              {#each xAxisLabels as label}
                <text class="chart-xlabel" x={label.x} y={PRICE_H + 2} text-anchor={label.anchor}>{label.label}</text>
              {/each}

              <!-- price baseline -->
              <line class="chart-axis" x1="0" y1={chartBaselineY} x2={svgWidth} y2={chartBaselineY} />

              <!-- entry area fill -->
              {#if chartAreaPath}
                <path class="chart-area" d={chartAreaPath} />
              {/if}

              <!-- candle or line -->
              {#if chartMode === "candle"}
                {#each candles as c}
                  <line
                    class={c.up ? "candle-wick candle-up" : "candle-wick candle-down"}
                    x1={c.x + c.w / 2} y1={c.wickTop}
                    x2={c.x + c.w / 2} y2={c.wickBottom}
                  />
                  <rect
                    class={c.up ? "candle-body candle-up" : "candle-body candle-down"}
                    x={c.x} y={c.bodyTop}
                    width={c.w}
                    height={Math.max(c.bodyBottom - c.bodyTop, 0.8)}
                    rx="0.5"
                  />
                {/each}
              {:else}
                <path class="chart-line" d={chartLinePath} />
                {#if chartLastPoint}
                  <circle class="chart-point-halo" cx={chartLastPoint.x} cy={chartLastPoint.y} r="4" />
                  <circle class="chart-point" cx={chartLastPoint.x} cy={chartLastPoint.y} r="2.2" />
                {/if}
              {/if}

              <!-- entry vertical line + arrow -->
              {#if chartEntryPoint}
                <polygon
                  class="entry-arrow"
                  points="{chartEntryPoint.x},{PAD_TOP} {chartEntryPoint.x - 4},{PAD_TOP - 8} {chartEntryPoint.x + 4},{PAD_TOP - 8}"
                />
                <line class="chart-entry-line" x1={chartEntryPoint.x} y1={PAD_TOP} x2={chartEntryPoint.x} y2={chartBaselineY} />
              {/if}

              <!-- avg cost horizontal line -->
              {#if avgCostLineY != null}
                <line class="avg-cost-line" x1="0" y1={avgCostLineY} x2={svgWidth} y2={avgCostLineY} />
              {/if}

              <!-- trade markers -->
              {#each tradeMarkers as tm}
                {#if tm.action === "buy"}
                  <polygon
                    class="trade-marker trade-buy"
                    points="{tm.x},{tm.y + 3} {tm.x - 5},{tm.y + 11} {tm.x + 5},{tm.y + 11}"
                  />
                  <text class="trade-marker-label trade-buy-label" x={tm.x} y={tm.y + 20} text-anchor="middle">${tm.price.toFixed(0)}</text>
                {:else}
                  <polygon
                    class="trade-marker trade-sell"
                    points="{tm.x},{tm.y - 3} {tm.x - 5},{tm.y - 11} {tm.x + 5},{tm.y - 11}"
                  />
                  <text class="trade-marker-label trade-sell-label" x={tm.x} y={tm.y - 14} text-anchor="middle">${tm.price.toFixed(0)}</text>
                {/if}
              {/each}

              <!-- volume separator -->
              <line class="chart-vol-sep" x1="0" y1={VOL_TOP - 2} x2={svgWidth} y2={VOL_TOP - 2} />

              <!-- volume bars -->
              {#each volumeBars as vb}
                <rect
                  class={vb.up ? "volume-bar vol-up" : "volume-bar vol-down"}
                  x={vb.x} y={vb.y} width={vb.w} height={vb.h} rx="0.4"
                />
              {/each}

              <!-- crosshair -->
              {#if crosshair.visible}
                <line class="crosshair-v" x1={crosshair.x} y1={PAD_TOP} x2={crosshair.x} y2={chartBaselineY} />
                <circle class="crosshair-dot" cx={crosshair.x} cy={crosshair.y} r="3" />
                <rect class="crosshair-bg" x={crosshair.x - 24} y={crosshair.labelY - 8} width="48" height="14" rx="3" />
                <text class="crosshair-price" x={crosshair.x} y={crosshair.labelY + 1} text-anchor="middle">{crosshair.price}</text>
                <rect class="crosshair-date-bg" x={crosshair.x - 18} y={PRICE_H - 2} width="36" height="12" rx="2" />
                <text class="crosshair-date" x={crosshair.x} y={PRICE_H + 6} text-anchor="middle">{crosshair.date}</text>
              {/if}
            </svg>
          </div>
        </div>
      {/if}

      {#if chartStats.count > 0}
        <div class="price-panel-footer">
          <div class="price-panel-stat"><span>고가</span><strong>{formatMoneyPlain(chartStats.high)}</strong></div>
          <div class="price-panel-stat"><span>저가</span><strong>{formatMoneyPlain(chartStats.low)}</strong></div>
        </div>
      {/if}
    </div>

    <div class="card-grid" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><h3>투자</h3></div>
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
                <span class={getDecisionClass(latestReport()?.final_trade_decision)}>{mapDecision(latestReport()?.final_trade_decision)}</span>
                <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(latestReport()?.created_at)}</span>
              </div>
              <div class="report-content markdown-body">{@html renderMd(getReportBody(latestReport()))}</div>
            </div>
          </div>
        {:else}
          <div class="card" style="padding:16px">AI분석이 없습니다.</div>
        {/if}
      {:else}
        <div class="history-list">
          {#if reports.length === 0}
            <div class="card history-entry"><div class="history-action">기록이 없습니다.</div></div>
          {:else}
            {#each sortedReports() as report}
              <div class="card history-entry">
                <button class="history-toggle" type="button" on:click={() => selectHistory(String(report.id))}>
                  <div class="history-top">
                    <span class="history-no">{getReportTitle(report)}</span>
                    <span class="history-date">{formatDateTime(report.created_at)}</span>
                    <span class="badge badge-gain">{mapDecision(report.final_trade_decision)}</span>
                  </div>
                </button>
                {#if selectedHistoryId === String(report.id)}
                  <div class="history-detail report-content markdown-body">{@html renderMd(getReportBody(report))}</div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    {/if}
  </div>
</section>
