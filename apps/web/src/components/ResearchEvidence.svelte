<script lang="ts">
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
  const exchangeLabels: Record<string,string> = { XKRX: "한국거래소", XNYS: "미국 정규장" };
  export let data: ResearchCase;
  let sourcesHeading: HTMLHeadingElement;
  $: snap = data.snapshot || {};
  $: arms = data.arms || [];
  $: single = arms.find(
    (a) => a.method === "single" && a.status === "published",
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
  <header class="company">
    <div class="context">
      {marketName(data.market)} 시장 <span>·</span> 관측 기준일 {data.data_session}{#if data.experiment_version} <span>·</span> 실험 {data.experiment_version}{/if}
    </div>
    <h2><InstrumentLabel ticker={data.ticker} inline /></h2>
    <div class="headline">
      <div>
        <span>단일 모델 상승 확률</span><strong
          >{probability(single?.probability)}</strong
        >
        {#if single?.published_at}<small
            >{timeLabel(single.published_at)} 발행</small
          >{/if}
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
    <dl class="period">
      <div>
        <dt>첫 거래일 개장</dt>
        <dd>{timeLabel(snap.entry_open_at || data.entry_open_at)}</dd>
      </div>
      <div>
        <dt>다섯째 거래일 마감</dt>
        <dd>{timeLabel(snap.exit_close_at || data.exit_close_at)}</dd>
      </div>
    </dl>
    {#if data.last30days || news}
      <button class="sources-link" on:click={() => sourcesHeading.focus()}>
        당시 출처 보기 · last30days {sources.archives ? sources.archives.items.length + "건" : "기록 없음"} · 동결 목록 {news ? news.items.length + "건" : "기록 없음"} ↓
      </button>
    {/if}
  </header>

  <div class="spread">
    <div class="plot">
      <ResearchPriceChart bars={snap.bars || []} {currency} />
    </div>
    <section class="sources">
      <h3 bind:this={sourcesHeading} tabindex="-1">당시 확인된 30일 출처</h3>
      <p class="muted">
        예측 근거를 동결하기 전에 확인한 자료입니다. 모델 확률 입력에는 포함되지
        않았습니다.
      </p>
      {#key data.id}
        <ResearchIssueFeed
          title="last30days · 기사와 커뮤니티"
          feed={sources.archives}
          lead
        />
        <ResearchIssueFeed title="RSS · 동결 이슈" feed={sources.rss} />
        {#if sources.unmatched}<ResearchIssueFeed title="수집 경로 미확인 · 동결 이슈" feed={sources.unmatched} />{/if}
      {/key}
    </section>
  </div>
  <section class="sheet">
    <h3>발행 당시의 가격 근거</h3>
    <dl class="facts">
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
          {exchangeLabels[snap.exchange || ""] ||
            "거래소 미기록"} · {currency || "미기록"}
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
  <ResearchJudgments {data} />
</article>

<style>
  .evidence {
    min-width: 0;
    color: #282522;
  }
  .company {
    border-top: 3px solid #852641;
    padding: clamp(15px, 2vw, 26px) 0 15px;
  }
  .context,
  .muted,
  dt,
  small,
  .headline span {
    color: #675f59;
    font-size: 0.82rem;
  }
  .context span {
    margin: 0 5px;
  }
  h2,
  h3,
  h4,
  p,
  dl,
  dd {
    margin: 0;
  }
  .sources-link { display:none; }
  .company h2 :global(.symbol) { font-size:.48em; color:#675f59; letter-spacing:0; }
  .company h2 {
    font-family: Georgia, "Malgun Gothic", serif;
    font-size: clamp(1.8rem, 3.8vw, 3.5rem);
    line-height: 1.15;
    letter-spacing: -0.045em;
    margin: 8px 0 14px;
  }
  .headline,
  .period,
  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 10px clamp(16px, 3vw, 45px);
  }
  .headline {
    align-items: start;
  }
  .headline > div {
    display: grid;
    gap: 1px;
  }
  .headline strong {
    font-size: clamp(1.45rem, 2.5vw, 2.15rem);
    color: #852641;
    line-height: 1.25;
  }
  .headline .outcome {
    color: #38332e;
    font-size: clamp(1.3rem, 2vw, 1.75rem);
  }
  .period {
    margin-top: 12px;
  }
  .period > div {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 4px 8px;
  }
  .period dd,
  .facts dd {
    font-size: 0.86rem;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .spread {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(230px, 0.9fr);
    background: #fff;
    border-block: 1px solid #d8d1c8;
    margin: 3px 0 15px;
  }
  .plot,
  .sources,
  .sheet {
    padding: clamp(14px, 2vw, 24px);
  }
  .plot {
    padding-left: 0;
  }
  .sources {
    border-left: 1px solid #dfd9d1;
  }
  .sources h3,
  .sheet h3 {
    font-size: 1.12rem;
    letter-spacing: -0.02em;
  }
  .sources > .muted {
    margin: 5px 0 9px;
    font-size: 0.77rem;
  }
  .sheet {
    padding-inline: 0;
    border-top: 1px solid #dcd6ce;
  }
  .facts {
    margin: 12px 0;
  }
  .facts > div {
    min-width: 110px;
    max-width: 100%;
  }
  .sheet h4 {
    margin: 13px 0 3px;
  }
  .condition {
    padding: 12px 0;
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: 8px;
    border-bottom: 1px solid #e7e0da;
  }
  .condition p,
  .empty,
  .market p {
    font-size: 0.9rem;
  }
  .status {
    white-space: nowrap;
    color: #713247;
    background: #f4e9ec;
    padding: 2px 7px;
    font-size: 0.8rem;
  }
  .empty,
  .muted,
  .market summary {
    line-height: 1.55;
  }
  .empty,
  .market summary {
    color: #655d56;
  }
  .market summary {
    cursor: pointer;
    font-size: 0.85rem;
  }
  .market {
    padding: 8px 0;
  }
  @media (max-width: 790px) {
    .sources-link { display:block; border:0; background:transparent; padding:6px 0; min-height:36px; color:#762641; font:inherit; font-size:.82rem; text-align:left; text-decoration:underline; text-underline-offset:3px; cursor:pointer; }
    .spread {
      grid-template-columns: 1fr;
    }
    .plot,
    .sources {
      padding: 14px 0;
    }
    .sources {
      border: 0;
      border-top: 1px solid #dfd9d1;
    }
  }
</style>
