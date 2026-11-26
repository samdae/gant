<script lang="ts">
  import { renderNarrative } from "../lib/utils/researchMarkdown";
  import {
    methodName,
    stateName,
    price,
    probability,
    timeLabel,
    percentChange,
    type ResearchCase,
  } from "../lib/researchEvidence";
  import ResearchMemory from "./ResearchMemory.svelte";
  import InstrumentLabel from "./InstrumentLabel.svelte";
  export let data: ResearchCase;
  const panels: Record<string, HTMLDetailsElement> = {};
  export function openMethod(key: string) {
    const panel = panels[key];
    if (!panel) return;
    panel.open = true;
    panel.querySelector("summary")?.focus();
    panel.scrollIntoView({ block: "start" });
  }
  const basisLabels: Record<string, string> = {
    same_ticker: "같은 종목",
    equity_peer: "동종주 동조",
    etf_exposure: "같은 기초자산 ETF",
  };
  const roles: Record<string, string> = {
    create_bull_researcher: "강세 분석가",
    create_bear_researcher: "약세 분석가",
    create_research_manager: "투자 토론 심판",
    create_trader: "트레이더",
    create_aggressive_debator: "공격적 위험 분석가",
    create_conservative_debator: "보수적 위험 분석가",
    create_neutral_debator: "중립 위험 분석가",
    create_risk_manager: "최종 위험 심판",
  };
  $: methods = [
    "baseline",
    "single",
    "debate",
    "memory",
    ...(data.snapshot?.retrieval_policy === "sector-v1"
      ? ["memory_sector"]
      : []),
  ];
  $: o = data.outcome;
  $: bars = o?.evidence?.evidence?.bars || o?.evidence?.bars || [];
  const reasons: Record<string, string> = {
    same_memory: "기존 방식과 같은 기억을 선택했습니다.",
    no_eligible_sector_memory: "분류 기준에 맞는 과거 기억이 없습니다.",
  };
</script>

<section class="sheet models">
  <h3>방법별 예측과 판단 근거</h3>
  {#each methods as key}
    {@const arm = data.arms?.find((a) => a.method === key)}
    {@const selected =
      data.selected_memories?.[key] ||
      (key === "memory" ? data.selected_memory : null)}
    {@const select = arm?.audit?.sector_selection_v1}
    <details class="model" bind:this={panels[key]}>
      <summary
        ><strong>{methodName(key)}</strong>
        {#if arm?.status === "published" && typeof arm.probability === "number" && arm.probability >= 0 && arm.probability <= 1}
          <i class="scale" aria-hidden="true"
            ><i style:width={arm.probability * 100 + "%"}></i></i
          >
        {/if}<span
          >{arm?.status === "published"
            ? probability(arm.probability)
            : arm
              ? stateName(arm.status)
              : "발행 기록 없음"}</span
        ></summary
      >
      {#if arm?.status === "published"}
        <p class="meta">
          {arm.model === "deterministic"
            ? "통계 기준선"
            : arm.model || "모델 미기록"}{#if arm.version}
            · {arm.version}{/if} · {timeLabel(arm.published_at)} 발행 {arm.brier !=
          null
            ? "· Brier " + arm.brier.toFixed(3)
            : ""}
        </p>
        <div class="narrative">
          {@html renderNarrative(arm.rationale, "기록된 판단 근거가 없습니다.")}
        </div>
        {#if arm.audit?.debate?.length}<h4>
            역할별 토론 · {arm.audit.debate.length}개 발언
          </h4>
          {#each arm.audit.debate as turn}<details class="turn">
              <summary>{roles[turn.role] || "토론 참여자"}</summary>
              <div class="narrative">
                {@html renderNarrative(turn.output, "공개된 발언이 없습니다.")}
              </div>
            </details>{/each}{/if}
      {:else}<p class="meta">
          {(arm?.error && reasons[arm.error]) ||
            (arm?.status === "skipped"
              ? "이 방법의 발행을 건너뛰었습니다."
              : "발행된 확률과 서술이 없습니다.")}
        </p>{/if}
      {#if selected}<ResearchMemory
          memory={selected}
          label="선택한 과거 기억"
        />{/if}
      {#if select}<p class="meta">
          선택 기준 · {basisLabels[select.basis || ""] ||
            "미기록"}{#if select.selected_ticker}
            · <InstrumentLabel
              ticker={select.selected_ticker}
              inline
            />{/if}{#if select.peer_ticker}
            · 동조 확인 <InstrumentLabel
              ticker={select.peer_ticker}
              inline
            />{/if}
        </p>
        {#if select.peer_reference}<p class="meta">
            {select.peer_reference === "watchlist_median"
              ? "다른 업종 관찰 종목 " +
                (select.reference_count ?? "미기록") +
                "개 중앙값 대비"
              : "시장 기준 대비"}
          </p>{/if}
        {#if select.source_window_return != null && select.peer_window_return != null}<p
            class="meta"
          >
            이전 사례 수익률 {percentChange(select.source_window_return)} · 확인
            종목 {percentChange(select.peer_window_return)}
          </p>{/if}{/if}
      {#if arm?.audit?.memory_selection_v1?.uplift_support != null}<p
          class="meta"
        >
          선택 시 이전 비교 {arm.audit.memory_selection_v1.uplift_support}건 ·
          보정 개선량 {arm.audit.memory_selection_v1.shrunk_uplift?.toFixed(
            3,
          ) ?? "미기록"}
        </p>{/if}
    </details>
  {/each}
</section>
<section class="sheet">
  <h3>만기 관측과 기억</h3>
  {#if o?.status === "scored"}<p>
      첫날 시가 {price(o.entry_open, data.snapshot?.currency)} → 다섯째 종가 {price(
        o.exit_close,
        data.snapshot?.currency,
      )} · {o.actual === 1 ? "상승" : o.actual === 0 ? "보합·하락" : "미확인"}
    </p>
    <p class="meta">채점 {timeLabel(o.observed_at)}</p>
    {#if bars.length}<details class="turn">
        <summary>평가 거래일별 가격 · {bars.length}건</summary
        >{#each bars as b}<p>
            {b.date} · 시가 {price(b.open, data.snapshot?.currency)} · 종가 {price(
              b.close,
              data.snapshot?.currency,
            )}
          </p>{/each}
      </details>{/if}
  {:else}<p class="meta">
      {o?.status === "excluded"
        ? "평가를 제외한 사례입니다."
        : "다섯 거래일의 종가가 확인되고 채점되면 결과가 표시됩니다."}
    </p>{/if}
  {#if data.reference}<details class="turn">
      <summary>같은 기간의 기존 운영 예측</summary>
      <p>
        {data.reference.model || "모델 미기록"} · 상승 확률 {probability(
          data.reference.probability,
        )}
      </p>
      <p class="meta">
        기존 발행 {timeLabel(data.reference.source_published_at)} · 연구실 관측 {timeLabel(
          data.reference.captured_at,
        )}
      </p>
    </details>{/if}
  {#if data.memory}<ResearchMemory
      memory={data.memory}
      label="이 사례에서 생성한 연구용 기억"
    />{/if}
</section>

<style>
  .sheet {
    padding: clamp(16px, 2vw, 26px) 0;
    border-top: 1px solid var(--fl-line);
  }
  .sheet h3 {
    margin: 0 0 0.6rem;
    font-size: 1.18rem;
  }
  .sheet h4 {
    font-size: 0.95rem;
  }
  .sheet p {
    margin: 0.5rem 0;
  }
  .model {
    border-bottom: 1px solid var(--fl-line);
    padding: 10px 0;
  }
  .model > summary {
    display: flex;
    align-items: baseline;
    gap: 7px;
    cursor: pointer;
  }
  .model > summary:before {
    content: "▸";
    font-size: 0.8rem;
    color: var(--fl-forecast);
  }
  .model[open] > summary:before {
    content: "▾";
  }
  .scale {
    display: flex;
    width: clamp(35px, 13vw, 150px);
    margin-left: auto;
    align-self: center;
    height: 5px;
    background: var(--fl-line);
  }
  .scale i {
    background: var(--fl-forecast);
  }
  .model > summary .scale + span {
    margin-left: 0;
    min-width: 3.5em;
    text-align: right;
  }
  .model > summary span {
    margin-left: auto;
    font-weight: bold;
    color: var(--fl-forecast);
  }
  .turn {
    margin: 8px 0;
    padding: 8px 12px;
    border-left: 2px solid var(--fl-line);
  }
  .turn summary {
    cursor: pointer;
  }
  .meta {
    color: var(--fl-muted);
    font-size: 0.82rem;
  }
  .narrative :global(a) {
    color: var(--fl-accent);
  }
  .narrative {
    font-size: 0.94rem;
    line-height: 1.75;
    max-width: 72ch;
    overflow-wrap: anywhere;
  }
  .narrative :global(p) {
    margin: 0.5em 0;
  }
  .narrative :global(table) {
    display: block;
    overflow-x: auto;
  }
  .narrative :global(pre) {
    white-space: pre-wrap;
  }
</style>
