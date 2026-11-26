<script lang="ts">
  import { replace } from "svelte-spa-router";
  import { homeRoute } from "../lib/workspaceNavigation";
  import { isForecastLab } from "../lib/workspace";
  import { onMount } from "svelte";

  onMount(() => {
    if (isForecastLab) {
      replace(homeRoute);
      return;
    }
    if (window.location.hash !== "#/") {
      window.location.hash = "#/";
    }
  });
</script>

{#if isForecastLab}<p role="status">
    리포트로 이동 중입니다.
  </p>{:else}<section class="page">
    <div class="page-container">
      <div class="card" style="padding:24px">
        <h3>Page not found</h3>
        <p style="color:var(--text-dim);margin-top:8px">
          Redirecting to the dashboard.
        </p>
      </div>
    </div>
  </section>{/if}
