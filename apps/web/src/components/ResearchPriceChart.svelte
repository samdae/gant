<script lang="ts">
  import { percentChange, price, type Bar } from "../lib/researchEvidence";
  export let bars: Bar[] = [];
  export let currency: string | undefined;
  let sessions = 0;
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
  $: values = series.map((b) => b.close);
  $: lo = Math.min(...values);
  $: hi = Math.max(...values);
  $: pad = Number.isFinite(lo) ? Math.max((hi - lo) * 0.12, hi * 0.002) : 0;
  $: min = lo - pad;
  $: max = hi + pad;
  $: from = Date.parse(series[0]?.date);
  $: to = Date.parse(series[series.length - 1]?.date);
  $: points = series.map((b) => ({
    x: to > from ? 12 + (475 * (Date.parse(b.date) - from)) / (to - from) : 249,
    y: 12 + (142 * (max - b.close)) / (max - min),
  }));
  $: line = points
    .map((p, i) => (i ? "L" : "M") + p.x.toFixed(1) + "," + p.y.toFixed(1))
    .join(" ");
</script>

<section class="chart" aria-label="동결된 가격 차트">
  <header>
    <h3>발행 전 종가 추이</h3>
    <div aria-label="차트 기간">
      {#each [5, 20, 0] as n}<button
          aria-pressed={sessions === n}
          on:click={() => (sessions = n)}>{n ? n + "일" : "전체"}</button
        >{/each}
    </div>
  </header>
  {#if series.length}
    <div class="quote">
      <strong>{price(series[series.length - 1].close, currency)}</strong><small
        >{series[series.length - 1].date} 종가 · {currency ||
          "통화 미기록"}{#if series.length > 1} · 기간 {percentChange(series[series.length - 1].close / series[0].close - 1)}{/if}</small
      >
    </div>
    <svg
      viewBox="0 0 570 184"
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
            maximumFractionDigits: 2,
          })}</text
        >{/each}
      <path d={line} />{#each points as point, i}<circle
          cx={point.x}
          cy={point.y}
          r={i === points.length - 1 ? 3 : 1.5}
          ><title>{series[i].date} · {price(series[i].close, currency)}</title
          ></circle
        >{/each}
      <text x="12" y="178">{series[0].date}</text>{#if series.length > 1}<text
          x="487"
          y="178"
          text-anchor="end">{series[series.length - 1].date}</text
        >{/if}
    </svg>
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
    min-width: 0;
  }
  .chart header,
  .quote {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  h3,
  p {
    margin: 0;
  }
  h3 {
    font-size: 1.05rem;
  }
  .quote {
    justify-content: flex-start;
    margin: 10px 0 6px;
  }
  .quote strong {
    font-size: 1.4rem;
  }
  .quote small,
  summary,
  p {
    color: #625c5b;
    font-size: 0.79rem;
  }
  button {
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    color: #5b5351;
    font: inherit;
    font-size: 0.78rem;
    padding: 3px 6px;
    cursor: pointer;
  }
  button[aria-pressed="true"] {
    border-color: #852641;
    color: #852641;
    font-weight: 700;
  }
  svg {
    display: block;
    width: 100%;
    min-height: 126px;
    margin-bottom: 9px;
  }
  svg path {
    fill: none;
    stroke: #852641;
    stroke-width: 2.5;
    stroke-linejoin: round;
  }
  circle {
    fill: #852641;
  }
  line {
    stroke: #dfdbd6;
    stroke-width: 1;
  }
  text {
    fill: #615854;
    font: 12px system-ui;
  }
  @media(max-width:620px) { button { min-width:38px; min-height:36px; } text { font-size:16px; } summary { padding-block:6px; } }
  .table {
    overflow-x: auto;
  }
  th,
  td {
    white-space: nowrap;
    padding: 5px 8px;
    font-size: 0.78rem;
    border-bottom: 1px solid #ebe6df;
  }
  th {
    text-align: left;
  }
  summary {
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
</style>
