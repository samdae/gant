<script lang="ts">
  import { location } from "svelte-spa-router";
  import { isPublicViewer } from "../lib/workspace";
  import { sections, currentPage } from "../lib/workspaceNavigation";
  import GantMark from "./GantMark.svelte";
  import WorkspaceIcon from "./WorkspaceIcon.svelte";
  export let drawer = false;
  export let dismiss: (() => void) | undefined = undefined;
  export let onNavigate: (() => void) | undefined = undefined;
  $: active = currentPage($location).page.route;
</script>

<div class="rail-body" class:as-drawer={drawer}>
  <header class="rail-brand">
    <a
      href="#/dashboard"
      on:click={onNavigate}
      aria-label="GANT 대시보드"><GantMark size={31} /><b>GANT</b></a
    >
    {#if drawer}<button aria-label="메뉴 닫기" type="button" on:click={dismiss}
        ><WorkspaceIcon name="close" /></button
      >{/if}
  </header>
  <nav aria-label={drawer ? "전체 메뉴" : "주 탐색"}>
    {#each sections as section}
      <section>
        <h2>{section.name}</h2>
        {#each section.pages.filter((page) => !isPublicViewer || page.route !== "/auth") as page}
          <a
            href={"#" + page.route}
            aria-current={active === page.route ? "page" : undefined}
            on:click={onNavigate}
          >
            <WorkspaceIcon name={page.route.slice(1)} /><span>{page.label}</span
            >
          </a>
        {/each}
      </section>
    {/each}
  </nav>
</div>

<style>
  .rail-body {
    display: flex;
    flex-direction: column;
    height: 100%;
    color: var(--fl-ink);
    background: var(--fl-nav);
  }
  .rail-brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 76px;
    padding: 0 22px;
    flex: none;
  }
  .rail-brand a {
    display: flex;
    align-items: center;
    gap: 9px;
    color: var(--fl-ink);
    text-decoration: none;
  }
  .rail-brand b {
    font: 750 23px/1 var(--fl-font);
    letter-spacing: -1.5px;
    transform: skewX(-7deg);
  }
  .rail-brand button {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border: 0;
    background: none;
    color: var(--fl-muted);
    cursor: pointer;
  }
  nav {
    overflow: auto;
    flex: 1;
    scrollbar-width: thin;
    padding: 3px 12px 18px;
  }
  section + section {
    margin-top: 14px;
  }
  h2 {
    font: 650 11px/1.5 var(--fl-font);
    color: var(--fl-muted);
    margin: 0 10px 4px;
  }
  nav a {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 34px;
    padding: 4px 10px;
    border-radius: 7px;
    color: var(--fl-ink);
    font: 550 14px/1.3 var(--fl-font);
    text-decoration: none;
  }
  nav a:hover {
    background: var(--fl-surface-subtle);
  }
  nav a[aria-current] {
    color: var(--fl-accent);
    background: var(--fl-accent-soft);
    box-shadow: inset 2px 0 var(--fl-accent);
    font-weight: 720;
  }
  nav a:focus-visible,
  .rail-brand :is(a, button):focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: -2px;
  }
  .as-drawer nav {
    touch-action: pan-y;
    overscroll-behavior: contain;
  }
  .as-drawer nav a {
    min-height: 44px;
  }
  .as-drawer .rail-brand {
    min-height: 60px;
  }
</style>
