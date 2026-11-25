<script lang="ts">
  import { isForecastLab } from "../lib/workspace";
  export let label: string;
</script>

{#if isForecastLab}
  <span class="pending" role="status"><span class="indicator" aria-hidden="true"></span><span class="sr-only">{label}</span></span>
{:else}{label}{/if}

<style>
  .pending { display:inline-flex; align-items:center; gap:.6em; color:inherit; line-height:1.45; }
  .sr-only { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap; }
  .indicator { box-sizing:border-box; width:1em; height:1em; flex:0 0 1em; border:2px solid color-mix(in srgb, currentColor 25%, transparent); border-top-color:currentColor; border-radius:50%; animation:turn .85s linear infinite; }
  @keyframes turn { to {transform:rotate(360deg);} }
  @media(prefers-reduced-motion:reduce){.indicator { animation:none; }}
</style>
