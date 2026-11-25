<script lang="ts">
  import { location } from "svelte-spa-router";
  import { isPublicViewer } from "../lib/workspace";
  import { sections, currentPage } from "../lib/workspaceNavigation";

  export let dismiss: () => void;
  $: active = currentPage($location).page.route;
</script>

<header class="drawer-head">
  <strong>전체 메뉴</strong><button
    type="button"
    on:click={dismiss}
    aria-label="메뉴 닫기">닫기</button
  >
</header>
<nav aria-label="전체 메뉴">
  {#each sections as section}
    <section>
      <h2>{section.name}</h2>
      {#each section.pages.filter((page) => !isPublicViewer || page.route !== "/auth") as page}
        <a
          href={"#" + page.route}
          on:click={dismiss}
          aria-current={active === page.route ? "page" : undefined}
          >{page.label}</a
        >
      {/each}
    </section>
  {/each}
</nav>

<style>
  .drawer-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 15px 22px;
    border-bottom: 2px solid var(--fl-ink);
    font-size: 19px;
  }
  button {
    font: inherit;
    font-size: 13px;
    padding: 8px 12px;
    border: 1px solid var(--fl-line);
    background: white;
    color: var(--fl-ink);
  }
  nav {
    padding: 4px 22px 20px;
  }
  section {
    display: flex;
    gap: 8px 18px;
    flex-wrap: wrap;
    padding: 13px 0;
    border-bottom: 1px solid var(--fl-line);
  }
  h2 {
    font-size: 13px;
    color: var(--fl-accent);
    margin: 0;
    width: 100%;
  }
  a {
    display: inline-flex;
    align-items: center;
    min-height: 36px;
    color: var(--fl-ink);
    font-size: 15px;
  }
  a[aria-current] {
    font-weight: 800;
    text-decoration: underline;
  }
  nav a,
  .drawer-head button {
    min-height: 44px;
  }
</style>
