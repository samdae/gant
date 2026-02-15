<script lang="ts">
  import { onMount } from "svelte";

  onMount(() => {
    if (window.location.hash !== "#/") {
      window.location.hash = "#/";
    }
  });
</script>

<section class="page">
  <div class="page-container">
    <div class="card" style="padding:24px">
      <h3>Page not found</h3>
      <p style="color:var(--text-dim);margin-top:8px">Redirecting to the dashboard.</p>
    </div>
  </div>
</section>
