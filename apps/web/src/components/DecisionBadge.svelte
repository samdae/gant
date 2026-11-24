<script lang="ts">
  export let value: string;
  const labels = new Map([
    ["BUY", "매수"], ["매수", "매수"],
    ["SELL", "매도"], ["매도", "매도"],
    ["HOLD", "관망"], ["관망", "관망"], ["보유", "관망"],
  ]);
  $: label = labels.get((value ?? "").trim().toUpperCase()) ?? "미기록";
</script>

<span class="signal" class:buy={label === "매수"} class:sell={label === "매도"} class:hold={label === "관망"}>{label}</span>

<style>
  .signal {
    display: inline-flex;
    align-items: center;
    padding: 0.17rem 0.5rem;
    border-radius: 5px;
    color: #475569;
    background: #edf1f5;
    font-size: 0.75rem;
    font-weight: 700;
    line-height: 1.5;
    white-space: nowrap;
    vertical-align: middle;
  }
  .buy { color: #9b2632; background: #fcebed; }
  .sell { color: #214f9e; background: #eaf1ff; }
  .hold { color: #765015; background: #fcf1d9; }
</style>
