<script lang="ts">
  import { renderNarrative } from "../lib/utils/researchMarkdown";
  import {
    type Memory,
    percentChange,
    price,
    probability,
    timeLabel,
  } from "../lib/researchEvidence";
  import InstrumentLabel from "./InstrumentLabel.svelte";
  export let memory: Memory;
  export let label: string;
  $: currency = memory.market === "kr" ? "KRW" : memory.market === "us" ? "USD" : undefined;
</script>

<details class="memory">
  <summary>{label}</summary>
  <p>
    <InstrumentLabel ticker={memory.ticker} inline /> · {memory.data_session ||
      "기준일 미기록"}
  </p>
  <dl>
    {#each [["당시 상승 확률", probability(memory.probability)], ["실제 결과", memory.actual === 1 ? "상승" : memory.actual === 0 ? "보합·하락" : "미기록"], ["진입 시가", price(memory.entry_open, currency)], ["만기 종가", price(memory.exit_close, currency)], ["당시 Brier", memory.brier?.toFixed(3) ?? "미기록"], ["20거래일 가격 변화", percentChange(memory.features?.trend_20d)], ["일간 변동성", percentChange(memory.features?.volatility_20d)], ["기억 등록", timeLabel(memory.created_at)]] as pair}<div
      >
        <dt>{pair[0]}</dt>
        <dd>{pair[1]}</dd>
      </div>{/each}
  </dl>
  {#if memory.rationale}<div class="narrative">
      {@html renderNarrative(memory.rationale, "기록된 서술이 없습니다.")}
    </div>{/if}
</details>

<style>
  .memory {
    margin-top: 12px;
    border-left: 2px solid #ccbfb5;
    padding: 5px 12px;
  }
  .memory summary {
    cursor: pointer;
    color: #653345;
    font-weight: 650;
  }
  .memory dl {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 22px;
  }
  .memory p,
  .memory dl {
    margin: 8px 0;
  }
  .memory dt,
  .memory dd {
    font-size: 0.82rem;
  }
  .memory dt {
    color: #655d56;
  }
  .memory dd {
    margin: 0;
  }
  .narrative {
    max-width: 72ch;
    overflow-wrap: anywhere;
  }
</style>
