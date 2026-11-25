<script lang="ts">
  import { instrumentName, tickerNames } from "../stores/tickerNames";
  import catalog from "../../../../packages/tradingagents/forecast_lab/web/instrument-names.json";
  import ResearchPriceChart from "./ResearchPriceChart.svelte";
  import ResearchIssueFeed from "./ResearchIssueFeed.svelte";
  import ResearchJudgments from "./ResearchJudgments.svelte";
  import InstrumentLabel from "./InstrumentLabel.svelte";
  import {
    percentChange,
    classificationLabel,
    caseSources,
    marketName,
    methodName,
    price,
    probability,
    stateName,
    timeLabel,
    type ResearchCase,
  } from "../lib/researchEvidence";
  const exchangeLabels: Record<string, string> = {
    XKRX: "한국거래소",
    XNYS: "미국 정규장",
  };
  export let data: ResearchCase;
  let sourcesHeading: HTMLHeadingElement;
  let judgments: ResearchJudgments;
  const catalogNames: Record<string, string> = catalog;
  $: displayName = instrumentName(data.ticker, $tickerNames);
  $: catalogParts =
    displayName && displayName === catalogNames[data.ticker]
      ? displayName.match(/^(.+)\(([^()]+)\)$/)
      : null;
  $: snap = data.snapshot || {};
  $: arms = data.arms || [];
  $: single = arms.find(
    (a) => a.method === "single" && a.status === "published",
  );
  $: methodKeys = [
    "baseline",
    "single",
    "debate",
    "memory",
    ...(snap.retrieval_policy === "sector-v1" ? ["memory_sector"] : []),
  ];
  $: publishedValues = methodKeys.flatMap((key) => {
    const arm = arms.find((item) => item.method === key);
    const value = arm?.probability;
    return arm?.status === "published" &&
      typeof value === "number" &&
      value >= 0 &&
      value <= 1
      ? [value]
      : [];
  });
  $: spreadRange =
    publishedValues.length >= 2
      ? {
          low: Math.min(...publishedValues),
          high: Math.max(...publishedValues),
        }
      : null;
  $: unpublishedMethods = methodKeys.filter(
    (key) =>
      !arms.some(
        (a) =>
          a.method === key &&
          a.status === "published" &&
          typeof a.probability === "number" &&
          a.probability >= 0 &&
          a.probability <= 1,
      ),
  );
  $: h = data.hypothesis;
  $: news = data.issues;
  $: sources = caseSources(news, data.last30days);
  $: currency = snap.currency || h?.currency;
  $: close = h?.reference_close ?? snap.bars?.[snap.bars.length - 1]?.close;
  $: result = data.outcome;
  $: hasForecast = arms.some((arm) => arm.status === "published");
  $: awaitingResult =
    data.status === "excluded" || result?.status === "excluded"
      ? "평가 제외"
      : hasForecast
        ? Date.parse(snap.exit_close_at || data.exit_close_at || "") <=
          Date.now()
          ? "채점 대기"
          : "만기 대기"
        : stateName(data.status);
</script>

<article class="evidence" aria-label="선택 사례의 연구 근거">
  <div class="analysis-board">
    <header class="company">
      <div class="company-row">
        <h2>{catalogParts?.[1] || displayName || data.ticker}</h2>
        <slot />
      </div>
      <div class="context">
        {#if displayName}{data.ticker} ·
        {/if}{#if catalogParts}{catalogParts[2]} ·
        {/if}{marketName(data.market)} 시장 · 관측 기준일 {data.data_session}
      </div>
      <div class="headline">
        <div>
          <span>단일 모델 상승 확률</span><strong
            >{probability(single?.probability)}</strong
          >
        </div>
        <div>
          <span>5거래일 검증 결과</span>
          <strong class="outcome"
            >{result?.status === "scored" && result.actual === 1
              ? "상승"
              : result?.status === "scored" && result.actual === 0
                ? "보합·하락"
                : awaitingResult}</strong
          >
          {#if result?.status === "scored"}<small
              >시가 {price(result.entry_open, currency)} → 종가 {price(
                result.exit_close,
                currency,
              )}</small
            >{/if}
        </div>
      </div>
      {#if data.last30days || news}
        <button class="sources-link" on:click={() => sourcesHeading.focus()}>
          당시 출처 보기 · last30days {sources.archives
            ? sources.archives.items.length + "건"
            : "기록 없음"} · {news?.provenance === "v3_archive_as_of" ? "뉴스" : "동결 목록"} {news
            ? news.items.length + "건"
            : "기록 없음"}
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"
            ><path
              d="M8 2v11m-4-4 4 4 4-4"
              fill="none"
              stroke="currentColor"
              stroke-width="1.6"
            /></svg
          >
        </button>
      {/if}
    </header>

    <div class="spread">
      <div class="plot">
        <ResearchPriceChart
          bars={snap.bars || []}
          {currency}
          volumeUnit={["equity", "etf"].includes(
            snap.classification?.asset_class || "",
          )
            ? "주"
            : ""}
        />
      </div>
      <section class="comparison">
        <h3>모델별 상승 확률</h3>
        {#if spreadRange}
          <p class="range-summary">
            <span>발행 확률 범위</span>
            <strong
              >{probability(spreadRange.low)}–{probability(
                spreadRange.high,
              )}</strong
            >
            <span
              >차이 {((spreadRange.high - spreadRange.low) * 100).toFixed(
                1,
              )}%p</span
            >
          </p>
        {/if}
        <div class="axis" aria-hidden="true">
          <div><span>0%</span><span>50%</span><span>100%</span></div>
        </div>
        {#each methodKeys as key}
          {@const arm = arms.find((item) => item.method === key)}
          {#if arm?.status === "published" && typeof arm.probability === "number" && arm.probability >= 0 && arm.probability <= 1}
            <button
              class="compare-row"
              on:click={() => judgments.openMethod(key)}
              aria-label={methodName(key) +
                " " +
                probability(arm.probability) +
                " 판단 근거 보기"}
            >
              <span>{methodName(key)}</span>
              <span class="track"
                ><i style:left={arm.probability * 100 + "%"}></i></span
              >
              <b>{probability(arm.probability)}</b>
              <svg aria-hidden="true" viewBox="0 0 16 16" width="13" height="13"
                ><path
                  d="m6 4 4 4-4 4"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                /></svg
              >
            </button>
          {/if}
        {/each}
        {#if unpublishedMethods.length}
          <div class="unpublished">
            {#each unpublishedMethods as key}
              <button on:click={() => judgments.openMethod(key)}
                >{methodName(key)} · {stateName(
                  arms.find((a) => a.method === key)?.status || "unpublished",
                )}</button
              >
            {/each}
          </div>
        {/if}
        <div class="timeline">
          <header>
            <h4>검증 일정</h4>
            <span
              >{result?.status === "scored"
                ? "채점 완료"
                : awaitingResult}</span
            >
          </header>
          <dl>
            <div>
              <dt>첫 거래일 개장</dt>
              <dd>{timeLabel(snap.entry_open_at || data.entry_open_at)}</dd>
            </div>
            <div>
              <dt>다섯째 거래일 마감</dt>
              <dd>{timeLabel(snap.exit_close_at || data.exit_close_at)}</dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  </div>
  <section class="sources">
    <header class="journal-heading">
      <h3 bind:this={sourcesHeading} tabindex="-1">당시 확인된 30일 출처</h3>
      <p class="muted">
        {#if news?.provenance === "v3_archive_as_of" || data.last30days?.provenance === "v3_archive_as_of"}
          같은 종목에 대해 당시 별도로 수집된 참고 자료입니다. 원래 예측의 입력으로 사용됐다는 기록은 없습니다.
        {:else}
          예측 근거를 동결하기 전에 확인한 자료입니다. 모델 확률 입력에는 포함되지 않았습니다.
        {/if}
      </p>
    </header>
    {#key data.id}
      <ResearchIssueFeed
        title="last30days · 기사와 커뮤니티"
        feed={sources.archives}
        lead
      />
      <ResearchIssueFeed title={news?.provenance === "v3_archive_as_of" ? "뉴스" : "RSS · 동결 이슈"} feed={sources.rss} />
      {#if sources.unmatched}<ResearchIssueFeed
          title={news?.provenance === "v3_archive_as_of" ? "기타 참고 자료" : "수집 경로 미확인 · 동결 이슈"}
          feed={sources.unmatched}
        />{/if}
    {/key}
  </section>
  <section class="sheet">
    <h3>발행 당시의 가격 근거</h3>
    <details class="market">
      <summary>발행 시각과 검증 일정</summary>
      <dl class="period">
        <div>
          <dt>단일 모델 발행</dt>
          <dd>{timeLabel(single?.published_at)}</dd>
        </div>
        <div>
          <dt>첫 거래일 개장</dt>
          <dd>{timeLabel(snap.entry_open_at || data.entry_open_at)}</dd>
        </div>
        <div>
          <dt>다섯째 거래일 마감</dt>
          <dd>{timeLabel(snap.exit_close_at || data.exit_close_at)}</dd>
        </div>
      </dl>
    </details>
    <dl class="facts">
      {#if data.experiment_version}<div>
          <dt>실험 버전</dt>
          <dd>{data.experiment_version}</dd>
        </div>{/if}
      <div>
        <dt>기준일 종가</dt>
        <dd>{price(close, currency)}</dd>
      </div>
      <div>
        <dt>근거 동결</dt>
        <dd>{timeLabel(h?.observed_at || snap.observed_at)}</dd>
      </div>
      <div>
        <dt>가격 출처</dt>
        <dd>{h?.source || snap.source || "미기록"}</dd>
      </div>
      <div>
        <dt>거래소 · 통화</dt>
        <dd>
          {exchangeLabels[snap.exchange || ""] || "거래소 미기록"} · {currency ||
            "미기록"}
        </dd>
      </div>
      {#if snap.classification}<div>
          <dt>동결 당시 종목 분류</dt>
          <dd>{classificationLabel(snap.classification)}</dd>
        </div>{/if}
    </dl>
    {#if snap.benchmark?.ticker || snap.features}
      <details class="market">
        <summary>시장 기준과 상대 추세</summary>
        {#if snap.benchmark?.ticker}<p>
            시장 기준 <InstrumentLabel ticker={snap.benchmark.ticker} inline /> ·
            {snap.benchmark.status === "available" ? "자료 확인" : "자료 부족"}
          </p>{/if}
        <dl class="facts">
          {#each [["20거래일 가격 변화", "trend_20d"], ["일간 변동성", "volatility_20d"], ["시장 대비 20거래일 변화", "relative_trend_20d"], ["시장 기준 가격 변화", "benchmark_trend_20d"]] as item}<div
            >
              <dt>{item[0]}</dt>
              <dd>{percentChange(snap.features?.[item[1]])}</dd>
            </div>{/each}
        </dl>
        {#if snap.benchmark?.bars?.length}<ResearchPriceChart
            bars={snap.benchmark.bars}
            {currency}
          />{/if}
      </details>
    {/if}
    <h4>가설과 재검토 조건</h4>
    {#if h?.conditions?.length}
      <p class="muted">
        최근 5거래일의 고가·저가로 동결한 연구 규칙입니다. 상승 확률의 채점과
        별도로 검증합니다.
      </p>
      {#if h.reference_window_start || h.window_start}
        <dl class="facts">
          {#if h.reference_window_start}<div>
              <dt>기준 가격 구간</dt>
              <dd>{h.reference_window_start} ~ {h.data_session}</dd>
            </div>{/if}
          {#if h.window_start && h.window_end}<div>
              <dt>조건 관측 구간</dt>
              <dd>{h.window_start} ~ {h.window_end}</dd>
            </div>{/if}
        </dl>
      {/if}
      {#each h.conditions as c}
        <div class="condition">
          <div>
            <strong
              >{c.id === "breakout"
                ? "돌파 가설"
                : c.id === "review"
                  ? "재검토 조건"
                  : "가격 조건"}</strong
            >
            <p>
              {c.metric === "exit_close"
                ? "다섯째 거래일 종가"
                : c.metric === "min_close"
                  ? "다섯 거래일 중 최저 종가"
                  : "관측 가격"}
              {price(c.threshold, h.currency)}
              {c.operator === "gt"
                ? "초과"
                : c.operator === "lt"
                  ? "미만"
                  : "기준"}
            </p>
            {#if c.observed_value != null}<small
                >실제 {price(c.observed_value, h.currency)} · {c.observed_session ||
                  "관측일 미기록"}</small
              >{/if}
          </div>
          <span class="status"
            >{c.status === "pending" ? "평가 대기" : stateName(c.status)}</span
          >
        </div>
      {/each}
    {:else}<p class="empty">
        이 사례에는 발행 시점에 동결한 가격 조건이 없습니다.
      </p>{/if}
  </section>
  <section class="judgments" tabindex="-1" aria-label="모델별 판단 근거">
    <ResearchJudgments bind:this={judgments} {data} />
  </section>
</article>

<style>
  .evidence {
    color: var(--fl-ink, #f4f2e9);
    font-variant-numeric: tabular-nums;
    min-width: 0;
  }
  h2,
  h3,
  h4,
  p,
  dl,
  dd {
    margin: 0;
  }
  .analysis-board {
    background: var(--fl-surface, #202124);
    border-block: 1px solid var(--fl-line, #3b3d41);
  }
  .company {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 4px clamp(18px, 3vw, 48px);
    align-items: center;
    padding: clamp(16px, 2.4vw, 32px);
    border-bottom: 1px solid var(--fl-line);
  }
  .company-row {
    display: contents;
  }
  .company h2 {
    grid-column: 1;
    grid-row: 1;
    min-width: 0;
    overflow-wrap: anywhere;
    font: 760 clamp(2rem, 3.8vw, 3.65rem) / 1.08 var(--fl-font, sans-serif);
    letter-spacing: -0.04em;
  }
  .company-row :global(.choose) {
    grid-column: 3;
    grid-row: 1 / 3;
  }
  .context {
    grid-column: 1;
    grid-row: 2;
    font-size: 0.8rem;
    color: var(--fl-muted);
  }
  .headline {
    grid-column: 2;
    grid-row: 1 / 3;
    display: flex;
    align-items: baseline;
    gap: 22px;
  }
  .headline > div {
    display: grid;
    gap: 4px;
  }
  .headline span,
  dt,
  small,
  .muted,
  .empty {
    color: var(--fl-muted);
    font-size: 0.82rem;
  }
  .headline strong {
    color: var(--fl-forecast, #c3a9ff);
    font-size: clamp(1.42rem, 2.2vw, 2rem);
    line-height: 1.15;
  }
  .headline .outcome {
    color: var(--fl-ink);
    font-size: 1.05rem;
  }
  .period,
  .period > div,
  .facts {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 6px 18px;
  }
  .period {
    padding-block: 8px;
  }
  .period dd {
    font-size: 0.82rem;
  }
  .spread {
    display: grid;
    grid-template-columns: minmax(0, 1.64fr) minmax(240px, 1fr);
  }
  .plot,
  .comparison,
  .sources,
  .sheet,
  .judgments {
    min-width: 0;
  }
  .comparison {
    display: flex;
    flex-direction: column;
    padding: clamp(16px, 2.2vw, 30px);
    border-left: 1px solid var(--fl-line);
    --columns: minmax(4.2em, 1fr) minmax(50px, 1.3fr) 3.7em 13px;
  }
  h3 {
    font-size: clamp(1.13rem, 1.55vw, 1.42rem);
    letter-spacing: -0.025em;
  }
  .comparison h3 {
    display: flex;
    align-items: center;
    gap: 9px;
  }
  .comparison h3:before {
    content: "";
    height: 0.83em;
    width: 4px;
    background: var(--fl-forecast);
  }
  .range-summary {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 5px 9px;
    padding-top: 10px;
    color: var(--fl-muted);
    font-size: 0.78rem;
  }
  .range-summary strong {
    color: var(--fl-forecast);
    font-size: 1rem;
  }
  .axis,
  .compare-row {
    display: grid;
    grid-template-columns: var(--columns);
    gap: 8px;
    align-items: center;
  }
  .axis {
    margin: 22px 5px 6px;
    color: var(--fl-muted);
    font-size: 0.74rem;
  }
  .axis div {
    grid-column: 2;
    display: flex;
    justify-content: space-between;
  }
  .compare-row {
    width: 100%;
    padding: 13px 5px;
    min-height: 44px;
    text-align: left;
    font: 620 0.85rem var(--fl-font, sans-serif);
    color: var(--fl-ink);
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--fl-line);
    cursor: pointer;
  }
  .compare-row b {
    font-size: 1rem;
    color: var(--fl-forecast);
    text-align: right;
  }
  .compare-row:hover,
  .compare-row:focus-visible {
    background: #312c39;
  }
  .compare-row:focus-visible,
  .unpublished button:focus-visible {
    outline: 2px solid var(--fl-forecast);
  }
  .track {
    position: relative;
    height: 3px;
    background: #48434e;
  }
  .track:before {
    content: "";
    position: absolute;
    left: 50%;
    top: -6px;
    height: 15px;
    border-left: 1px dashed #a69bb5;
  }
  .track i {
    position: absolute;
    top: 50%;
    height: 10px;
    width: 10px;
    background: var(--fl-forecast);
    transform: translate(-50%, -50%) rotate(45deg);
  }
  .unpublished {
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
    padding-top: 8px;
  }
  .unpublished button,
  .sources-link {
    background: transparent;
    border: none;
    font: inherit;
    cursor: pointer;
  }
  .unpublished button {
    padding: 6px 0;
    font-size: 0.78rem;
    color: var(--fl-muted);
  }
  .unpublished button:hover,
  .sources-link:hover {
    text-decoration: underline;
  }
  .timeline {
    margin-top: auto;
    padding-top: 20px;
  }
  .timeline header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--fl-line);
  }
  .timeline h4 {
    font-size: 0.92rem;
  }
  .timeline header span {
    color: var(--fl-muted);
    font-size: 0.77rem;
  }
  .timeline dl {
    margin: 10px 0 0 4px;
  }
  .timeline dl div {
    position: relative;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 4px 12px;
    padding: 4px 0 5px 14px;
    border-left: 1px solid #77777a;
  }
  .timeline dl div:last-child {
    border-color: transparent;
  }
  .timeline dl div:before {
    content: "";
    position: absolute;
    left: -4px;
    top: 10px;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #a4a49d;
  }
  .timeline dd {
    font-size: 0.82rem;
    font-weight: 570;
  }
  .sources-link {
    display: none;
    text-align: left;
    color: var(--fl-accent);
    padding: 6px 0;
    font-size: 0.82rem;
  }
  .sources {
    display: grid;
    grid-template-columns: minmax(160px, 0.78fr) repeat(2, minmax(0, 1.2fr));
    gap: 0 clamp(16px, 2vw, 30px);
    padding: 24px 0;
    border-bottom: 1px solid var(--fl-line);
  }
  .journal-heading {
    grid-row: span 2;
  }
  .journal-heading .muted {
    max-width: 28ch;
    line-height: 1.55;
    margin-top: 9px;
  }
  .sheet,
  .judgments {
    padding: 24px 0;
    border-bottom: 1px solid var(--fl-line);
  }
  .facts {
    gap: 12px 34px;
    margin: 14px 0;
  }
  .facts dd {
    margin-top: 3px;
    font-weight: 600;
    font-size: 0.93rem;
  }
  .market {
    padding: 10px 0;
  }
  .market summary {
    cursor: pointer;
  }
  .sheet h4 {
    margin: 14px 0 5px;
  }
  .condition {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    border-top: 1px solid var(--fl-line);
    padding: 12px 0;
  }
  .condition p,
  .market p {
    font-size: 0.9rem;
  }
  .status {
    font-size: 0.8rem;
    color: var(--fl-forecast);
    white-space: nowrap;
  }
  @media (max-width: 920px) {
    .headline {
      gap: 12px;
    }
    .company {
      column-gap: 16px;
    }
    .sources {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .journal-heading {
      grid-row: auto;
      grid-column: 1/-1;
      margin-bottom: 12px;
    }
    .journal-heading .muted {
      max-width: none;
    }
  }
  @media (max-width: 760px) {
    .company {
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 5px 8px;
      padding: 16px 12px 8px;
    }
    .company-row :global(.choose) {
      grid-column: 2;
      grid-row: 1;
    }
    .context {
      grid-column: 1/-1;
    }
    .headline {
      grid-column: 1/-1;
      grid-row: 3;
      flex-wrap: wrap;
      gap: 5px 15px;
      margin-top: 4px;
    }
    .headline > div {
      display: flex;
      align-items: baseline;
      gap: 5px;
    }
    .headline small,
    .timeline {
      display: none;
    }
    .headline span {
      font-size: 0.77rem;
    }
    .sources-link {
      grid-column: 1/-1;
      display: block;
    }
    .spread,
    .sources {
      grid-template-columns: 1fr;
    }
    .comparison {
      border-left: 0;
      border-top: 1px solid var(--fl-line);
      padding: 16px 12px;
    }
    .sources {
      padding: 20px 0 8px;
    }
    .journal-heading {
      margin-bottom: 0;
    }
    .journal-heading .muted {
      margin: 4px 0 7px;
    }
    .sheet,
    .judgments {
      padding: 20px 0;
    }
  }
</style>
