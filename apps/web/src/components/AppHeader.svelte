<script lang="ts">
  import { link } from "svelte-spa-router";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";

  const currencies: CurrencyFilter[] = ["ALL", "KRW", "USD"];

  const setCurrency = (c: CurrencyFilter) => { currencyFilter.set(c); };
</script>

<header class="app-header">
  <a href="#/" class="logo" use:link>GANT</a>

  <div class="currency-selector">
    {#each currencies as c}
      <button
        class="currency-btn"
        class:active={$currencyFilter === c}
        on:click={() => setCurrency(c)}
      >{c}</button>
    {/each}
  </div>
</header>

<style>
  .currency-selector {
    display: flex;
    gap: 2px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
  }
  .currency-btn {
    padding: 4px 12px;
    font-size: 0.7rem;
    font-weight: 600;
    border: 1px solid transparent;
    border-radius: 6px;
    cursor: pointer;
    background: transparent;
    color: var(--text-dim);
    transition: all 0.15s ease;
  }
  .currency-btn:hover:not(.active) {
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.04);
  }
  .currency-btn.active {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text);
    border-color: var(--border);
  }
</style>
