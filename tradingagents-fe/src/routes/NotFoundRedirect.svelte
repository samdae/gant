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
      <h3>페이지를 찾을 수 없습니다</h3>
      <p style="color:var(--text-dim);margin-top:8px">대시보드로 이동합니다.</p>
    </div>
  </div>
</section>
