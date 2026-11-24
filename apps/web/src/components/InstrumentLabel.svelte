<script lang="ts">
  import { instrumentName, tickerNames } from "../stores/tickerNames";

  export let ticker: string;
  export let name: string | null | undefined = undefined;
  export let inline = false;

  $: symbol = ticker.trim().toUpperCase();
  $: company = instrumentName(symbol, $tickerNames, name);
</script>

<span class="instrument" class:inline>
  <span class="name">{company || symbol}</span>
  {#if company}<span class="symbol">{symbol}</span>{/if}
</span>

<style>
  .instrument {
    display: inline-flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.12em;
    min-width: 0;
    max-width: 100%;
    line-height: 1.35;
    text-align: start;
    vertical-align: middle;
  }
  .instrument.inline { flex-direction: row; flex-wrap: wrap; align-items: baseline; gap: 0.08em 0.4em; }
  .name { font-weight: 650; overflow-wrap: anywhere; }
  .symbol { font-size: 0.82em; font-weight: 500; color: var(--fl-muted, var(--text-secondary)); overflow-wrap: anywhere; }
</style>
