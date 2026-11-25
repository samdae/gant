<script lang="ts">
  import InstrumentLabel from "./InstrumentLabel.svelte";
  import {
    articleUrl,
    marketName,
    methodName,
    price,
    probability,
    stateName,
    timeLabel,
    type ResearchCase,
  } from "../lib/researchEvidence";
  export let data: ResearchCase;
  $: snap = data.snapshot || {};
  $: arms = data.arms || [];
  $: single = arms.find(
    (a) => a.method === "single" && a.status === "published",
  );
  $: h = data.hypothesis;
  $: news = data.issues;
  $: currency = snap.currency || h?.currency;
  $: close = h?.reference_close ?? snap.bars?.[snap.bars.length - 1]?.close;
  $: result = data.outcome;
  let expandedCase: number | null = null;
  $: showAllNews = expandedCase === data.id;
  $: hasForecast = arms.some((arm) => arm.status === "published");
  $: awaitingResult = data.status === "excluded" || result?.status === "excluded"
    ? "평가 제외"
    : hasForecast
      ? (Date.parse(snap.exit_close_at || data.exit_close_at || "") <= Date.now() ? "채점 대기" : "만기 대기")
      : stateName(data.status);
  $: issueMessage =
    {
      uncollected: "근거 동결 시점까지 수집 기록이 없습니다.",
      empty: "수집했지만 시점 조건을 충족한 이슈가 없습니다.",
      failed: "당시 최근 수집에 실패했습니다. 이전에 확보한 자료만 표시합니다.",
      available: "",
    }[news?.status || ""] ?? "이 사례에는 이슈 보관 기록이 없습니다.";
</script>

<article class="evidence" aria-label="선택 사례의 연구 근거">
  <header class="company">
    <div class="context">
      {marketName(data.market)} 시장 <span>·</span> 관측 기준일 {data.data_session}
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
  </header>

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
    </dl>
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
  <section class="sheet">
    <h3>당시 확인된 이슈</h3>
    {#if news}<p class="muted">
        기준 {timeLabel(news.as_of)} · 최근 30일 · {news.source ||
          "출처 미기록"}
      </p>{/if}
    {#if news?.collected_at}<p class="muted">
        최근 수집 {timeLabel(news.collected_at)}
      </p>{/if}
    {#if issueMessage}<p class="empty">{issueMessage}</p>{/if}
    {#each (showAllNews ? news?.items : news?.items.slice(0, 3)) || [] as item}
      <div class="news">
        <strong
          >{#if articleUrl(item.url)}<a
              href={articleUrl(item.url)}
              target="_blank"
              rel="noopener noreferrer">{item.title} ↗</a
            >{:else}{item.title}{/if}</strong
        >
        <small
          >{item.publisher || "매체 미기록"} · 공개 {item.published_precision ===
            "day" && item.published_day
            ? item.published_day + " (시간 미상)"
            : timeLabel(item.published_at)} · 최초 관측 {timeLabel(
            item.first_seen_at,
          )}</small
        >
      </div>
    {/each}
    {#if news && news.items.length > 3}
      <button class="news-toggle" aria-expanded={showAllNews} on:click={() => expandedCase = showAllNews ? null : data.id}>
        {showAllNews ? "이슈 접기" : "나머지 이슈 "+(news.items.length-3)+"건 보기"}
      </button>
    {/if}
    {#if news?.items?.length}<p class="muted foot">
        발행 전 열람 가능했던 자료입니다. 확률 계산에는 사용하지 않았습니다.
      </p>{/if}
  </section>
  <section class="sheet">
    <h3>방법별 예측</h3>
    {#each arms as arm}<div class="method">
        <div>
          <strong>{methodName(arm.method)}</strong><small
            >{arm.status === "published"
              ? timeLabel(arm.published_at)
              : stateName(arm.status)}{arm.brier != null
              ? " · Brier " + arm.brier.toFixed(3)
              : ""}</small
          >
        </div>
        <span
          >{arm.status === "published"
            ? probability(arm.probability)
            : "미발행"}</span
        >
      </div>
    {:else}<p class="empty">기록된 방법별 예측이 없습니다.</p>{/each}
    <a class="more" href={"/research/?case=" + data.id}
      >가격 차트·분석 전문 보기 ↗</a
    >
  </section>
</article>

<style>
  .evidence {
    min-width: 0;
    color: #172c36;
  }
  .company,
  .sheet {
    background: #fff;
    border: 1px solid #d8e1e2;
    padding: clamp(17px, 2.4vw, 30px);
  }
  .company {
    border-top: 4px solid #1b6d60;
    border-radius: 8px 8px 0 0;
  }
  .sheet {
    border-top: 0;
  }
  .sheet:last-child {
    border-radius: 0 0 8px 8px;
  }
  h2,
  h3,
  h4,
  p,
  dl,
  dd {
    margin: 0;
  }
  h2 {
    font-size: clamp(1.65rem, 3vw, 2.35rem);
    letter-spacing: -0.045em;
    margin: 0.35rem 0 1rem;
    overflow-wrap: anywhere;
  }
  h3 {
    font-size: 1.1rem;
    letter-spacing: -0.035em;
  }
  h4 {
    font-size: 0.95rem;
    margin: 1.3rem 0 0.3rem;
  }
  .context,
  small,
  .muted,
  dt,
  .headline span {
    color: #526675;
    font-size: 0.82rem;
  }
  .context span {
    padding: 0 0.2rem;
  }
  .headline,
  .period,
  .facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px 24px;
  }
  .headline {
    padding: 15px 0;
    border-block: 1px solid #d8e1e2;
  }
  .headline > div,
  .headline strong,
  small {
    display: block;
  }
  .headline strong {
    font-size: clamp(1.4rem, 3vw, 2.25rem);
    color: #145e51;
    line-height: 1.3;
  }
  .headline .outcome {
    color: #263c49;
  }
  .period {
    margin-top: 15px;
  }
  dd {
    font-size: 0.89rem;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .facts {
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 125px), 1fr));
    margin-top: 14px;
  }
  .condition,
  .method,
  .news {
    padding: 12px 0;
    border-bottom: 1px solid #e2e8e8;
  }
  .condition,
  .method {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
  }
  .condition p {
    margin-top: 3px;
  }
  .condition strong,
  .method strong,
  .news strong {
    font-size: 0.93rem;
  }
  .status {
    color: #304958;
    background: #edf2f2;
    border-radius: 4px;
    padding: 2px 7px;
    white-space: nowrap;
    font-size: 0.78rem;
  }
  .muted,
  .empty {
    margin-top: 8px;
  }
  .empty {
    color: #516675;
    line-height: 1.6;
    font-size: 0.88rem;
  }
  .foot {
    font-size: 0.78rem;
  }
  .news a,
  .more {
    color: #145e51;
    text-underline-offset: 3px;
  }
  .more {
    display: inline-block;
    margin-top: 14px;
    font-size: 0.85rem;
    text-decoration: underline;
  }
  @media (max-width: 450px) {
    .period {
      grid-template-columns: 1fr;
    }
    .headline {
      gap: 12px;
    }
    .facts {
      gap: 12px;
    }
    .method,
    .condition {
      align-items: flex-start;
    }
  }
  .news-toggle { margin-top:12px; padding:6px 10px; background:white; border:1px solid #b9c9c9; border-radius:5px; color:#145e51; font:inherit; font-size:.84rem; }
</style>
