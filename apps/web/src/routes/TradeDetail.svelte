<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import ReportDecisionEvidence from "../components/ReportDecisionEvidence.svelte";
  import DecisionBadge from "../components/DecisionBadge.svelte";
  import { isForecastLab } from "../lib/workspace";
  import { onMount, onDestroy } from "svelte";
  import { params, querystring } from "svelte-spa-router";
  import {
    fetchPositionDetail,
    fetchPositions,
    fetchPositionsMarket,
    fetchReportsByTicker,
    fetchPositionGraph,
    fetchPortfolioTrades,
    fetchPortfolioHoldings,
  } from "../lib/api/endpoints";
  import { viewMode } from "../stores/mode";
  import { formatMoney, formatMoneyPlain, formatPercent, formatDateTime, formatErrorMessage, formatAmount, formatSignedAmount } from "../lib/utils/format";
  import { renderNarrative } from "../lib/utils/researchMarkdown";

  type PositionMarket = {
    position_id?: number;
    ticker: string;
    shares: number;
    avg_cost: number | null;
    current_price: number | null;
    pnl: number;
    return_pct: number;
  };

  type PortfolioTrade = {
    id: number;
    ticker: string;
    action: string;
    shares: number;
    price: number;
    currency?: string;
    executed_at: string;
  };

  type PositionDetail = {
    position: { id: number; ticker: string; shares: number; avg_cost: number | null; opened_at?: string | null };
    trades: Array<{ id: number; action: string; shares: number; price: number; executed_at: string }>;
    reports: Array<{
      id: number;
      created_at: string;
      scheduled_cycle?: number;
      decision_position?: string;
      portfolio_action?: string;
      portfolio_shares?: number;
      portfolio_rationale?: string;
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
  let portfolioTrades: PortfolioTrade[] = [];
  let portfolioBaseCurrency = "";
  let portfolioHolding: { shares: number; current_value_base?: number } | null = null;
  let tab: "report" | "history" | "trades" = "report";
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
  let chartError = false;

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

  /* pinch zoom + touch gesture state */
  let pinchStartDist = 0;
  let pinchStartPW = DEFAULT_PW;
  let longPressTimer: ReturnType<typeof setTimeout> | null = null;
  let longPressActive = false;
  let touchStartX = 0;
  let touchStartY = 0;
  const LONG_PRESS_MS = 280;
  const MOVE_CANCEL_PX = 10;

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
  let detailRequest = 0;
  const loadDetail = async (t: string, query: string) => {
    const requestId = ++detailRequest;
    const selected = new URLSearchParams(query).get("position");
    positionId = null;
    summary = null;
    positionOpenedAt = null;
    avgCost = null;
    trades = [];
    reports = [];
    loading = true;
    error = "";
    resetChart();
    try {
      if ($viewMode === "portfolio") {
        const [holdingsRes, tradesRes] = await Promise.all([
          fetchPortfolioHoldings(),
          fetchPortfolioTrades(t, undefined, 100),
        ]);
        if (requestId !== detailRequest) return;
        const h = holdingsRes as { base_currency?: string; holdings?: Array<{ ticker: string; shares: number; current_value_base?: number }> };
        portfolioBaseCurrency = h?.base_currency || "";
        const holding = h?.holdings?.find((x) => x.ticker.toUpperCase() === t.toUpperCase());
        portfolioHolding = holding ? { shares: holding.shares, current_value_base: holding.current_value_base } : null;
        portfolioTrades = ((tradesRes as { items?: PortfolioTrade[] })?.items ?? []) as PortfolioTrade[];
        summary = portfolioHolding
          ? {
              ticker: t,
              shares: portfolioHolding.shares,
              avg_cost: null,
              current_price: null,
              pnl: 0,
              return_pct: 0,
            }
          : null;
        positionId = null;
        positionOpenedAt = portfolioTrades.length > 0 ? portfolioTrades[portfolioTrades.length - 1]?.executed_at ?? null : null;
        reports = [];
        trades = [];
        selectedHistoryId = "";
        tab = "trades";
        return;
      }

      tab = "report";
      const positionsMarket = (await fetchPositionsMarket()) as PositionMarket[];
      if (requestId !== detailRequest) return;
      const current = positionsMarket.find((p) => p.ticker.toUpperCase() === t);
      let targetId = selected ? Number(selected) : current?.position_id;
      if (!selected && !targetId) {
        const closed = (await fetchPositions("closed")) as Array<{ id: number; ticker: string }>;
        if (requestId !== detailRequest) return;
        targetId = closed.find((p) => p.ticker.toUpperCase() === t)?.id;
      }
      if (selected && (!Number.isSafeInteger(targetId) || Number(targetId) <= 0)) {
        throw new Error("잘못된 포지션 번호입니다.");
      }
      summary = current && current.position_id === targetId ? current : null;
      if (!targetId) {
        const latest = (await fetchReportsByTicker(t)) as PositionDetail["reports"];
        if (requestId !== detailRequest) return;
        reports = latest;
        positionId = null;
        positionOpenedAt = null;
        portfolioHolding = null;
        portfolioTrades = [];
        selectedHistoryId = "";
        return;
      }


      portfolioHolding = null;
      portfolioTrades = [];
      const detail = (await fetchPositionDetail(targetId)) as PositionDetail;
      if (requestId !== detailRequest) return;
      if (detail.position.ticker.toUpperCase() !== t) throw new Error("종목과 포지션이 일치하지 않습니다.");
      positionId = targetId;
      reports = detail.reports || [];
      trades = detail.trades || [];
      positionOpenedAt = detail.position?.opened_at || null;
      avgCost = detail.position?.avg_cost ?? summary?.avg_cost ?? null;
      selectedHistoryId = "";
    } catch (err) {
      if (requestId !== detailRequest) return;
      error = formatErrorMessage(err, "데이터를 불러오지 못했습니다.");
    } finally {
      if (requestId === detailRequest) loading = false;
    }
  };

  $: if ($params?.ticker) { ticker = String($params.ticker).toUpperCase(); }
  $: if (ticker && $viewMode) { loadDetail(ticker, $querystring ?? ""); }
  $: totalAmount = summary?.current_price != null ? summary.current_price * summary.shares : null;

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
    const PAD_LEFT = 6;   // small left padding inside scrollable area
    const PAD_RIGHT = 8;

    // Fill available mobile viewport width first, then allow horizontal expansion by zoom.
    const minInnerW = Math.max(0, (scrollContainerEl?.clientWidth || 0) - PAD_LEFT - PAD_RIGHT);
    const effectivePw = Math.max(pointWidth, len > 0 ? minInnerW / len : pointWidth);
    const chartW = PAD_LEFT + len * effectivePw + PAD_RIGHT;
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
    const toX = (idx: number) => PAD_LEFT + idx * effectivePw + effectivePw / 2;
    const barW = Math.min(effectivePw * 0.65, 10);

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
      } else { chartAreaPath = ""; chartEntryPoint = null; }
    } else { chartAreaPath = ""; chartEntryPoint = null; }

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

  const loadChart = async (id: number) => {
    chartLoading = true;
    chartError = false;
    try {
      const res = (await fetchPositionGraph(id, 30)) as { points: OHLCPoint[] };
      if (id !== positionId) return;
      rawPoints = res.points || [];
      // scroll to the right (latest data) after render
      requestAnimationFrame(() => {
        if (scrollContainerEl) scrollContainerEl.scrollLeft = scrollContainerEl.scrollWidth;
      });
    } catch { if (id === positionId) { resetChart(); chartError = true; } }
    finally { if (id === positionId) chartLoading = false; }
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
  const clearLongPressTimer = () => {
    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }
  };

  const handleTouchStart = (e: TouchEvent) => {
    if (e.touches.length === 2) {
      clearLongPressTimer();
      longPressActive = false;
      e.preventDefault();
      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      pinchStartDist = Math.sqrt(dx * dx + dy * dy);
      pinchStartPW = pointWidth;
      return;
    }

    if (e.touches.length === 1) {
      const t = e.touches[0];
      touchStartX = t.clientX;
      touchStartY = t.clientY;
      longPressActive = false;
      clearLongPressTimer();
      longPressTimer = setTimeout(() => {
        longPressActive = true;
        handleChartPointer(e);
      }, LONG_PRESS_MS);
    }
  };

  const handleTouchMove = (e: TouchEvent) => {
    if (e.touches.length === 2) {
      clearLongPressTimer();
      longPressActive = false;
      e.preventDefault();
      if (!scrollContainerEl) return;

      const dx = e.touches[1].clientX - e.touches[0].clientX;
      const dy = e.touches[1].clientY - e.touches[0].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const scale = dist / pinchStartDist;

      const prevSvgWidth = Math.max(1, svgWidth);
      const nextPointWidth = Math.min(MAX_PW, Math.max(MIN_PW, Math.round(pinchStartPW * scale)));

      // Keep pinch midpoint anchored while zooming (instead of always expanding from left edge).
      const midClientX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      const containerRect = scrollContainerEl.getBoundingClientRect();
      const pinchX = Math.max(0, Math.min(containerRect.width, midClientX - containerRect.left));
      const anchorRatio = (scrollContainerEl.scrollLeft + pinchX) / prevSvgWidth;

      pointWidth = nextPointWidth;

      requestAnimationFrame(() => {
        if (!scrollContainerEl) return;
        const nextSvgWidth = Math.max(1, svgWidth);
        const target = anchorRatio * nextSvgWidth - pinchX;
        const maxScroll = Math.max(0, nextSvgWidth - scrollContainerEl.clientWidth);
        scrollContainerEl.scrollLeft = Math.max(0, Math.min(maxScroll, target));
      });
      return;
    }

    if (e.touches.length === 1) {
      const t = e.touches[0];
      const moved = Math.abs(t.clientX - touchStartX) > MOVE_CANCEL_PX || Math.abs(t.clientY - touchStartY) > MOVE_CANCEL_PX;
      if (moved && !longPressActive) {
        clearLongPressTimer();
      }

      // Crosshair mode only after long press; otherwise keep native horizontal pan.
      if (longPressActive) {
        e.preventDefault();
        handleChartPointer(e);
      }
    }
  };

  const handleTouchEnd = (e: TouchEvent) => {
    if (e.touches.length === 0) {
      clearLongPressTimer();
      longPressActive = false;
      crosshair = { ...crosshair, visible: false };
    }
  };

  /* ── report helpers ── */
  $: latest = [...reports].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  $: sortedReports = [...reports].sort((a, b) =>
    (b.scheduled_cycle ?? -1) - (a.scheduled_cycle ?? -1) || b.created_at.localeCompare(a.created_at));

  const getReportTitle = (report?: PositionDetail["reports"][number] | null) => {
    if (!report) return "";
    if (report.scheduled_cycle != null) return `${report.scheduled_cycle} 회차`;
    return `AI분석 #${report.id}`;
  };

  const getReportBody = (report?: PositionDetail["reports"][number] | null) => {
    if (!report) return "";
    return report.final_trade_decision || "";
  };

  const getReportDecision = (report?: PositionDetail["reports"][number] | null) => {
    if (!report) return null;
    return report.portfolio_action || report.decision_position || null;
  };

  const getExecutionNote = (report?: PositionDetail["reports"][number] | null) => {
    if (!report || !report.portfolio_action) return "";
    const action = report.portfolio_action.toUpperCase();
    const shares = report.portfolio_shares;
    if ((action === "BUY" || action === "SELL") && (shares == null || shares <= 0)) {
      return "주문 수량이 0주로 계산되어 매매가 실행되지 않았습니다.";
    }
    return "";
  };

  const renderMd = (text?: string | null) => renderNarrative(text, "데이터 없음");

  const selectHistory = (reportId: string) => {
    selectedHistoryId = selectedHistoryId === reportId ? "" : reportId;
  };

  const handleResize = () => {
    if (rawPoints.length > 0) renderChart();
  };

  onMount(() => {
    window.addEventListener("resize", handleResize);
  });

  onDestroy(() => {
    window.removeEventListener("resize", handleResize);
  });

  $: if (positionId && positionOpenedAt) { loadChart(positionId); }
  $: if (scrollContainerEl && rawPoints.length > 0) { renderChart(); }
</script>

<section class="page" id="page-trade">
  <div class="page-container">
    <div class="page-header">
      {#if isForecastLab}<a class="folio-up" href="#/positions">← 보유·종료 명세</a>{:else}<button class="back-btn" aria-label="뒤로" on:click={() => history.back()}>&larr;</button>{/if}
      <h2>{#if isForecastLab}<InstrumentLabel {ticker} />{:else}{ticker}{/if}</h2>
      {#if summary?.current_price != null && summary.avg_cost != null}
        <span class={`pnl-banner ${summary.return_pct >= 0 ? "pnl-pos" : "pnl-neg"}`}>
          {formatPercent(summary.return_pct)}
        </span>
      {/if}
    </div>

    {#if isForecastLab && !loading && !error}
      <dl class="review-facts">
        <div>
          <dt>계좌</dt>
          <dd>{$viewMode === "portfolio" ? "포트폴리오" : "종목별 분석"}</dd>
        </div>
        {#if summary}
          <div>
            <dt>보유 수량</dt>
            <dd>{summary.shares}주</dd>
          </div>
          {#if $viewMode === "portfolio"}
            <div>
              <dt>평가액</dt>
              <dd>
                {portfolioHolding?.current_value_base != null && portfolioBaseCurrency
                  ? portfolioHolding.current_value_base.toLocaleString() + " " + portfolioBaseCurrency
                  : "—"}
              </dd>
            </div>
          {:else}
            <div>
              <dt>평균 단가</dt>
              <dd>{formatAmount(summary.avg_cost, ticker)}</dd>
            </div>
            <div>
              <dt>평가손익</dt>
              <dd>{formatSignedAmount(summary.pnl, ticker)}</dd>
            </div>
            <div>
              <dt>평가액</dt>
              <dd>{formatAmount(totalAmount, ticker)}</dd>
            </div>
          {/if}
        {:else}
          <div>
            <dt>현재 보유</dt>
            <dd>조회된 잔고 없음</dd>
          </div>
        {/if}
      </dl>
    {/if}
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
          {chartStats.last !== null ? formatAmount(chartStats.last, ticker) : "-"}
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

      {#if chartLoading || loading}
        <div class="empty-state"><PendingState label="차트 불러오는 중..."/></div>
      {:else if chartError}
        <div class="empty-state" role="alert">가격 차트를 불러오지 못했습니다.</div>
      {:else if rawPoints.length === 0}
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
              on:touchmove={handleTouchMove}
              on:touchend={handleTouchEnd}
              on:touchcancel={handleTouchEnd}
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
                  <text class="trade-marker-label trade-buy-label" x={tm.x} y={tm.y + 20} text-anchor="middle">{formatAmount(tm.price, ticker)}</text>
                {:else}
                  <polygon
                    class="trade-marker trade-sell"
                    points="{tm.x},{tm.y - 3} {tm.x - 5},{tm.y - 11} {tm.x + 5},{tm.y - 11}"
                  />
                  <text class="trade-marker-label trade-sell-label" x={tm.x} y={tm.y - 14} text-anchor="middle">{formatAmount(tm.price, ticker)}</text>
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
          <div class="price-panel-stat"><span>고가</span><strong>{formatAmount(chartStats.high, ticker)}</strong></div>
          <div class="price-panel-stat"><span>저가</span><strong>{formatAmount(chartStats.low, ticker)}</strong></div>
        </div>
      {/if}
    </div>

    {#if !isForecastLab}
    <div class="card-grid" style="margin-bottom:16px">
      <div class="card">
        <div class="card-header"><h3>투자</h3></div>
        <div class="card-body">
          <div class="stat-row"><span class="stat-label">보유</span><span class="stat-value">{summary?.shares ?? "-"}</span></div>
          <div class="stat-row"><span class="stat-label">1주 평균</span><span class="stat-value">{summary?.avg_cost ? formatAmount(summary.avg_cost, ticker) : "-"}</span></div>
          <div class="stat-row">
            <span class="stat-label">총 금액</span>
            <span class="stat-value">
              {#if totalAmount !== null}
                {formatAmount(totalAmount, ticker)}
                <span class={summary && summary.pnl >= 0 ? "text-gain" : "text-loss"} style="margin-left:2px">
                  ({summary ? formatSignedAmount(summary.pnl, ticker) : "-"})
                </span>
              {:else}
                -
              {/if}
            </span>
          </div>
        </div>
      </div>
    </div>

    {/if}
    {#if isForecastLab}
    <div class="review-switch" role="group" aria-label="거래 상세 보기">
      {#if $viewMode === "portfolio"}
        <button aria-pressed={tab === "trades"} on:click={() => (tab = "trades")}
          ><span>거래 내역</span></button
        >
      {:else}
        <button aria-pressed={tab === "report"} on:click={() => (tab = "report")}
          ><span>최신 AI 분석</span></button
        >
        <button aria-pressed={tab === "history"} on:click={() => (tab = "history")}
          ><span>분석 이력</span></button
        >
      {/if}
    </div>
    {:else}
    <div class="tab-bar">
      {#if $viewMode === "portfolio"}
        <button class={`tab-btn ${tab === "trades" ? "active" : ""}`} on:click={() => (tab = "trades")}>거래 내역</button>
      {:else}
        <button class={`tab-btn ${tab === "report" ? "active" : ""}`} on:click={() => (tab = "report")}>최신 AI분석</button>
        <button class={`tab-btn ${tab === "history" ? "active" : ""}`} on:click={() => (tab = "history")}>기록</button>
      {/if}
    </div>

    {/if}
    {#if loading}
      <div class="card" style="padding:16px"><PendingState label="거래 기록 조회 중"/></div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if isForecastLab && $viewMode === "portfolio" && tab === "trades"}
      {#if portfolioTrades.length}
        <div class="review-register">
          <table>
            <caption>포트폴리오 체결 내역</caption>
            <thead><tr><th>거래 일시</th><th>구분</th><th>체결 수량</th><th>체결 단가</th></tr></thead>
            <tbody
              >{#each portfolioTrades as tr}<tr
                  ><td>{formatDateTime(tr.executed_at)}</td><td
                    ><DecisionBadge value={tr.action || ""} /></td
                  ><td>{tr.shares}주</td><td>{formatAmount(tr.price, ticker)}</td></tr
                >{/each}</tbody
            >
          </table>
        </div>
      {:else}<div class="review-state">이 계좌에 기록된 체결 내역이 없습니다.
        <a href={"#/reports/" + encodeURIComponent(ticker.toLowerCase())}>이 종목의 분석 리포트</a>
      </div>{/if}
    {:else if $viewMode === "portfolio" && tab === "trades"}
      <div class="history-list">
        {#if portfolioTrades.length === 0}
          <div class="card history-entry"><div class="history-action">거래 내역이 없습니다.</div></div>
        {:else}
          {#each portfolioTrades as tr}
            <div class="card history-entry">
              <div class="history-top" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span class={tr.action?.toLowerCase().includes("buy") ? "badge badge-gain" : "badge badge-loss"}>
                  {tr.action?.toLowerCase().includes("buy") ? "매수" : tr.action?.toLowerCase().includes("sell") ? "매도" : tr.action || "-"}
                </span>
                <span>{tr.shares}주</span>
                <span>{formatAmount(tr.price, ticker)}</span>
                <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(tr.executed_at)}</span>
              </div>
            </div>
          {/each}
        {/if}
      </div>
    {:else if tab === "report"}
        {#if latest}
          <div class="card" style="margin-bottom:12px">
            <div class="card-body">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                {#if isForecastLab && latest}<ReportDecisionEvidence report={latest} />{:else}<span class={getDecisionClass(getReportDecision(latest))}>{mapDecision(getReportDecision(latest))}</span>{/if}
                <span style="font-size:0.8125rem;color:var(--text-dim)">{formatDateTime(latest?.created_at)}</span>
              </div>
              {#if !isForecastLab && getExecutionNote(latest)}
                <div style="font-size:0.78rem;color:var(--text-dim);margin-bottom:8px">
                  {getExecutionNote(latest)}
                </div>
              {/if}
              <div class="report-content markdown-body">{@html renderMd(getReportBody(latest))}</div>
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
            {#each sortedReports as report}
              <div class="card history-entry">
                <button class="history-toggle" type="button" on:click={() => selectHistory(String(report.id))}>
                  <div class="history-top">
                    <span class="history-no">{getReportTitle(report)}</span>
                    <span class="history-date">{formatDateTime(report.created_at)}</span>
                    {#if isForecastLab}<ReportDecisionEvidence {report} />{:else}<span class={getDecisionClass(getReportDecision(report))}>{mapDecision(getReportDecision(report))}</span>{/if}
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
  </div>
</section>
