<script lang="ts">
  export let size = 30;
</script>

<span class="mark" style:width={size + "px"} style:height={size + "px"} aria-hidden="true">
  <svg viewBox="0 0 40 40" fill="none">
    <path d="M5 19 17 6h17l-4 5H19L10 21v7h8l6-7h-7l4-5h12l-1 7-11 11H5z" fill="currentColor" />
  </svg>
</span>

<style>
  .mark {
    display: inline-grid;
    place-items: center;
    flex: none;
    border-radius: 30%;
    color: #f3fff6;
    background: linear-gradient(145deg, #418f87 1%, #176863 46%, #114641 100%);
    box-shadow: inset 0 1px 1px #a0d6c7, inset 0 -1px 1px #104843;
  }
  svg { width: 79%; height: 79%; }
</style>
