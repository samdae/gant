<script lang="ts">
  import { isForecastLab } from "../lib/workspace";
  import { trackPending } from "../stores/pendingReads";
  export let label: string;
</script>

{#if isForecastLab}
  <span class="pending" role="status" use:trackPending>{label}</span>
{:else}{label}{/if}

<style>
  .pending { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap; pointer-events:none; }
</style>
