<script lang="ts">
  import { percentChange, price, type Bar } from "../lib/researchEvidence";
  export let bars: Bar[] = [];
  export let volumeUnit = "";
  export let currency: string | undefined;
  let sessions = 0;
  let requestedMode: "line" | "candle" = "line";
  type Candle = Bar & { open: number; high: number; low: number };
  function hasOhlc(row: Bar): row is Candle {
    const { open, high, low } = row;
    return (
      typeof open === "number" &&
      Number.isFinite(open) &&
      open > 0 &&
      typeof high === "number" &&
      Number.isFinite(high) &&
      high >= Math.max(open, row.close) &&
      typeof low === "number" &&
      Number.isFinite(low) &&
      low > 0 &&
      low <= Math.min(open, row.close)
    );
  }
  const hasVolume = (value?: number) =>
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  const volumeText = (value?: number) =>
    hasVolume(value) ? value!.toLocaleString("ko-KR") + volumeUnit : "미기록";
  let selection: number | null = null;
  function inspectPrice(event: PointerEvent) {
    if (event.pointerType !== "mouse") return;
    const input = event.currentTarget as HTMLInputElement;
    const bounds = input.getBoundingClientRect();
    const fraction = Math.min(
      1,
      Math.max(0, (event.clientX - bounds.left) / bounds.width),
    );
    selection = Math.round(fraction * (series.length - 1));
  }
  $: all = bars
    .filter(
      (b) =>
        b &&
        /^\d{4}-\d{2}-\d{2}$/.test(b.date) &&
        Number.isFinite(Date.parse(b.date)) &&
        Number.isFinite(b.close) &&
        b.close > 0,
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  $: series = sessions ? all.slice(-sessions) : all;
  $: canCandle = series.some(hasOhlc);
  $: candles = requestedMode === "candle" && canCandle;
  $: values = candles
    ? series.filter(hasOhlc).flatMap((b) => [b.low, b.high])
    : series.map((b) => b.close);
  $: volumeMax = Math.max(
    0,
    ...series.filter((b) => hasVolume(b.volume)).map((b) => b.volume!),
  );
  $: hasAnyVolume = series.some((b) => hasVolume(b.volume));
  $: barWidth = Math.min(28, 300 / Math.max(series.length, 1));
  $: lo = Math.min(...values);
  $: hi = Math.max(...values);
  $: pad = Number.isFinite(lo) ? Math.max((hi - lo) * 0.12, hi * 0.002) : 0;
  $: min = lo - pad;
  $: max = hi + pad;
  $: from = Date.parse(series[0]?.date);
  $: to = Date.parse(series[series.length - 1]?.date);
  $: active = Math.min(selection ?? series.length - 1, series.length - 1);
  $: points = series.map((b, i) => ({
    x: series.length > 1 ? 12 + (475 * i) / (series.length - 1) : 249,
    y: 12 + (142 * (max - b.close)) / (max - min),
  }));
  $: yPrice = (value: number) => 12 + (142 * (max - value)) / (max - min);
  $: line = points
    .map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + "," + p.y.toFixed(1))
    .join(" ");
</script>

<section class="chart" aria-label="동결된 가격 차트">
  <header>
    <h3>발행 전 시세</h3>
    <div class="chart-controls">
      <div role="group" aria-label="시세 표시 방식">
        <button aria-pressed={!candles} on:click={() => (requestedMode = "line")}>라인</button>
        <button aria-pressed={candles} disabled={!canCandle}
          on:click={() => (requestedMode = "candle")}>캔들</button>
      </div>
      <div role="group" aria-label="차트 기간">
        {#each [5, 20, 0] as n}
          <button aria-pressed={sessions === n}
            on:click={() => {
              sessions = n;
              selection = null;
            }}>{n ? n + "일" : "전체"}</button>
        {/each}
      </div>
    </div>
  </header>
  {#if series.length}
    <div class="quote">
      <strong
        >{price(series[active].close)}<span class="unit"
          >{currency === "USD"
            ? "달러"
            : currency === "KRW"
              ? "원"
              : currency || ""}</span
        ></strong
      ><small
        >{series[active].date} 종가 · {currency ||
          "통화 미기록"}{#if series.length > 1}
          · 구간 등락 {percentChange(
            series[series.length - 1].close / series[0].close - 1,
          )}{/if}</small
      >
    </div>
    <div class="bar-values">
      {#each [["시가", series[active].open], ["고가", series[active].high], ["저가", series[active].low]] as pair}
        <span
          >{pair[0]}
          <b>{price(typeof pair[1] === "number" ? pair[1] : null, currency)}</b
          ></span
        >
      {/each}<span>거래량 <b>{volumeText(series[active].volume)}</b></span>
    </div>
    <div class="interactive">
      <svg
        viewBox={hasAnyVolume ? "0 0 570 250" : "0 0 570 184"}
        role="img"
        aria-label={from === to
          ? series[0].date + " 종가 한 건"
          : series[0].date +
            "부터 " +
            series[series.length - 1].date +
            "까지 동결 종가 " +
            series.length +
            "건"}
      >
        {#each [0, 0.5, 1] as t}<line
            x1="12"
            x2="492"
            y1={12 + 142 * t}
            y2={12 + 142 * t}
          /><text x="500" y={16 + 142 * t}
            >{(max - (max - min) * t).toLocaleString("ko-KR", {
              notation: Math.abs(max) >= 10000 ? "compact" : "standard",
              maximumFractionDigits: 2,
            })}</text
          >{/each}
        {#if candles}
          {#each series as b, i}{#if hasOhlc(b)}
              <g class="candle" class:rising={b.close >= b.open}>
                <line
                  x1={points[i].x}
                  x2={points[i].x}
                  y1={yPrice(b.high)}
                  y2={yPrice(b.low)}
                />
                <rect
                  x={points[i].x - barWidth / 2}
                  width={barWidth}
                  y={yPrice(Math.max(b.open, b.close))}
                  height={Math.max(
                    1,
                    Math.abs(yPrice(b.open) - yPrice(b.close)),
                  )}
                />
              </g>
            {/if}{/each}
        {:else}
          <path
            class="area"
            d={line +
              " L" +
              points[points.length - 1].x +
              ",154 L" +
              points[0].x +
              ",154 Z"}
          />
          <path d={line} />
        {/if}
        {#if points[active]}<line
            class="guide"
            x1={points[active].x}
            x2={points[active].x}
            y1="12"
            y2="154"
          />{/if}{#each points as point, i}<circle
            cx={point.x}
            cy={point.y}
            r={!candles && i === active ? 4 : 0}
            ><title>{series[i].date} · {price(series[i].close, currency)}</title
            ></circle
          >{/each}
        {#if hasAnyVolume}
          <line x1="12" x2="492" y1="176" y2="176" />
          <text x="12" y="174"
            >거래량{volumeUnit ? "(" + volumeUnit + ")" : ""}</text
          >
          <text x="500" y="190"
            >{Intl.NumberFormat("ko-KR", {
              notation: "compact",
              maximumFractionDigits: 1,
            }).format(volumeMax)}</text
          >
          <text x="500" y="217">0</text>
          {#each series as b, i}{#if hasVolume(b.volume)}
              {@const height = volumeMax
                ? (37 * (b.volume ?? 0)) / volumeMax
                : 0}
              <rect
                class="volume-bar"
                class:selected-volume={i === active}
                x={points[i].x - barWidth / 2}
                width={barWidth}
                y={218 - height}
                {height}
              />
            {/if}{/each}
        {/if}
        <text x="12" y={hasAnyVolume ? 244 : 178}>{series[0].date}</text
        >{#if series.length > 1}<text
            x="487"
            y={hasAnyVolume ? 244 : 178}
            text-anchor="end">{series[series.length - 1].date}</text
          >{/if}
      </svg>
      {#if series.length > 1}<input
          type="range"
          class="pointer"
          min="0"
          max={series.length - 1}
          value={active}
          on:pointermove={inspectPrice}
          aria-label="거래일 종가 조회"
          aria-valuetext={series[active].date +
            " " +
            price(series[active].close, currency)}
          on:input={(e) => (selection = Number(e.currentTarget.value))}
        />{/if}
    </div>
    {#if !hasAnyVolume}<p class="volume-note">
        동결된 거래량 기록이 없습니다.
      </p>{/if}
    {#if candles}<p class="candle-key">
        청록 양봉 · 산호색 음봉 · 꼬리는 고가와 저가
      </p>{/if}
    <details>
      <summary>거래일별 시세 · {series.length}건</summary>
      <div class="table">
        <table>
          <thead
            ><tr
              ><th>거래일</th><th>시가</th><th>고가</th><th>저가</th><th
                >종가</th
              ><th>거래량</th></tr
            ></thead
          ><tbody
            >{#each [...series].reverse() as b}<tr
                ><td>{b.date}</td
                >{#each [b.open, b.high, b.low, b.close] as v}<td
                    >{price(v, currency)}</td
                  >{/each}<td
                  >{b.volume?.toLocaleString("ko-KR") ?? "미기록"}</td
                ></tr
              >{/each}</tbody
          >
        </table>
      </div>
    </details>
  {:else}<p>동결한 거래일 종가가 없어 차트를 표시할 수 없습니다.</p>{/if}
</section>

<style>
  .chart {
    background: var(--fl-chart-bg, #131415);
    color: var(--fl-ink);
    padding: clamp(15px, 2vw, 23px);
    border-radius: var(--fl-radius,16px);
    height: 100%;
    box-sizing: border-box;
    font-variant-numeric: tabular-nums;
  }
  .quote .unit {
    font-size: 0.4em;
    margin-left: 0.13em;
    color: var(--fl-muted);
    letter-spacing: 0;
  }
  .volume-bar.selected-volume {
    fill: var(--fl-accent);
  }
  .chart-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }
  .bar-values {
    display: flex;
    gap: 4px 10px;
    flex-wrap: wrap;
    color: var(--fl-muted);
    font-size: 0.76rem;
    margin-bottom: 6px;
  }
  .bar-values b {
    color: var(--fl-ink);
    font-weight: 550;
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .candle line {
    stroke: var(--fl-down, #ff9a85);
  }
  .candle rect {
    fill: var(--fl-down, #ff9a85);
  }
  .candle.rising line {
    stroke: var(--fl-positive);
  }
  .candle.rising rect {
    fill: var(--fl-positive);
  }
  .volume-bar {
    opacity: 1;
    fill: var(--fl-chart-volume, #79978d);
  }
  .candle-key,
  .volume-note {
    padding: 4px 0;
  }
  .chart-controls > div {
    display: flex;
    align-items: center;
    gap: 1px;
    padding: 3px;
    border-radius: 999px;
    background: var(--fl-surface-subtle);
  }
  .chart button:focus-visible {
    outline: 2px solid var(--fl-chart-line, #d5f65e);
    outline-offset: 2px;
  }
  .chart header,
  .quote {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }
  .chart header {
    align-items: center;
    justify-content: space-between;
  }
  h3,
  p {
    margin: 0;
  }
  h3 {
    font-size: 1.05rem;
    color: var(--fl-ink);
  }
  .quote {
    margin: 20px 0 4px;
  }
  .quote strong {
    font-size: clamp(2.2rem, 4.5vw, 4rem);
    line-height: 1.12;
    letter-spacing: -0.04em;
    color: var(--fl-ink);
  }
  .quote small,
  .chart p,
  summary {
    color: var(--fl-muted);
    font-size: 0.78rem;
  }
  button {
    border: 0;
    background: none;
    color: var(--fl-muted);
    font: 600 0.78rem var(--fl-font, sans-serif);
    border-radius: 999px;
    min-width: 32px;
    min-height: 30px;
    cursor: pointer;
  }
  button[aria-pressed="true"] {
    background: var(--fl-selected-bg, var(--fl-accent));
    color: var(--fl-selected-ink, var(--fl-on-accent, white));
  }
  @media (forced-colors: active) {
    :global(.gant-v4) .chart-controls button[aria-pressed="true"] {
      forced-color-adjust: none;
      background: Highlight;
      color: HighlightText;
    }
    :global(.gant-v4) .chart-controls button:focus-visible {
      outline-color: ButtonText;
    }
  }
  .interactive {
    position: relative;
  }
  svg {
    display: block;
    width: 100%;
    height: auto;
    color: var(--fl-muted);
  }
  svg path {
    fill: none;
    stroke: var(--fl-chart-line, #d5f65e);
    stroke-width: 2.8;
    stroke-linejoin: round;
  }
  svg .area {
    fill: color-mix(in srgb,var(--fl-chart-line) 11%, transparent);
    stroke: none;
  }
  :global(.gant-v4) svg .area {
    fill: color-mix(in srgb, var(--fl-ink) 6%, transparent);
  }
  circle {
    fill: var(--fl-chart-line, #d5f65e);
  }
  line {
    stroke: var(--fl-line);
  }
  line.guide {
    stroke: var(--fl-accent);
    stroke-dasharray: 3 4;
  }
  text {
    fill: var(--fl-muted);
    font: 12px system-ui;
  }
  .pointer {
    position: absolute;
    left: 2%;
    width: 84%;
    top: 4%;
    height: 82%;
    margin: 0;
    opacity: 0;
    cursor: crosshair;
  }
  .interactive:focus-within {
    outline: 2px solid var(--fl-chart-line, #d5f65e);
    border-radius: 5px;
  }
  .table {
    overflow-x: auto;
  }
  th,
  td {
    padding: 6px;
    white-space: nowrap;
    color: var(--fl-ink);
    border-bottom: 1px solid var(--fl-line);
    font-size: 0.8rem;
  }
  th {
    text-align: left;
  }
  summary {
    cursor: pointer;
    min-height: 28px;
    padding-top: 5px;
  }
  @media (max-width: 620px) {
    button {
      min-width: 36px;
      min-height: 36px;
    }
    text {
      font-size: 22px;
    }
    .quote {
      margin-top: 5px;
    }
  }
</style>
