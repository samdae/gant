<script lang="ts">
  export let value: string;
  const labels = new Map([
    ["BUY", "매수"],
    ["매수", "매수"],
    ["SELL", "매도"],
    ["매도", "매도"],
    ["HOLD", "관망"],
    ["관망", "관망"],
    ["보유", "관망"],
  ]);
  $: label = labels.get((value ?? "").trim().toUpperCase()) ?? "미기록";
</script>

<span
  class="signal"
  class:buy={label === "매수"}
  class:sell={label === "매도"}
  class:hold={label === "관망"}>{label}</span
>

<style>
  .signal {
    display: inline-flex;
    align-items: center;
    padding: 0.17rem 0.5rem;
    border-radius: 5px;
    color: var(--fl-muted, #b5b4ad);
    background: var(--fl-surface-subtle, #27282b);
    font-size: 0.75rem;
    font-weight: 700;
    line-height: 1.5;
    white-space: nowrap;
    vertical-align: middle;
  }
  .signal::before {
    content: "";
    display: inline-block;
    width: 0.45em;
    height: 0.45em;
    margin-right: 0.38em;
    background: currentColor;
  }
  .buy {
    color: var(--fl-down, #ff9a85);
    background: #372724;
  }
  .buy::before {
    clip-path: polygon(50% 0, 100% 100%, 0 100%);
  }
  .sell {
    color: #acd0df;
    background: #222f33;
  }
  .sell::before {
    clip-path: polygon(0 0, 100% 0, 50% 100%);
  }
  .hold {
    color: var(--fl-muted, #b5b4ad);
    background: #303031;
  }
  .hold::before {
    height: 2px;
  }
</style>
