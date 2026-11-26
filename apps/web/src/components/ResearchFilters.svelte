<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import DateRangePicker from "./DateRangePicker.svelte";
  import SelectMenu from "./SelectMenu.svelte";
  import { marketOptions, type DateRange } from "../lib/researchDates";
  export let market = "",
    from = "",
    to = "";
  const dispatch = createEventDispatcher<{
    market: string;
    range: DateRange;
  }>();
</script>

<div class="filters">
  <div
    class="filter-grid"
    class:has-range={Boolean(from || to)}
    class:long-range={from && to && from !== to}
  >
    <div class="field">
      <span>시장</span><SelectMenu
        ariaLabel="시장"
        options={marketOptions}
        value={market}
        on:change={(e) => dispatch("market", e.detail)}
      />
    </div>
    <div class="field">
      <span>관측 기간</span><DateRangePicker
        {from}
        {to}
        on:change={(e) => dispatch("range", e.detail)}
      />
    </div>
  </div>
</div>

<style>
  .filters {
    container-type: inline-size;
    max-width: 100%;
    width: 100%;
    margin-block: 12px;
  }
  .filter-grid {
    display: grid;
    grid-template-columns: minmax(116px, 126px) minmax(0, 1fr);
    gap: var(--fl-control-gap, 8px);
    max-width: 400px;
    align-items: end;
  }
  .field {
    min-width: 0;
    display: grid;
    gap: 4px;
  }
  .field > span {
    font-size: 0.78rem;
    color: var(--fl-muted);
  }
  .field :global(.select-menu),
  .field :global(.range-trigger) {
    width: 100%;
    min-width: 0;
  }
  @container (max-width:330px) {
    .long-range {
      grid-template-columns: 1fr;
    }
  }
  @container (max-width:300px) {
    .has-range {
      grid-template-columns: 1fr;
    }
  }
  @container (max-width:230px) {
    .filter-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
