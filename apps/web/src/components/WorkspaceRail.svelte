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
      aria-label="GANT 대시보드"><GantMark size={36} /><b>GANT</b></a
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
    min-height: 0;
    color: var(--fl-nav-ink);
  }
  .rail-brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 17px 15px;
    flex: none;
  }
  .rail-brand a {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-height: 44px;
    color: var(--fl-nav-ink);
    text-decoration: none;
  }
  .rail-brand b { font: 760 22px/1 var(--fl-font); letter-spacing: -.04em; }
  .rail-brand button {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border: 0;
    border-radius: 50%;
    color: var(--fl-muted);
    background: var(--fl-surface);
    cursor: pointer;
  }
  nav { overflow-y: auto; flex: 1; min-height: 0; scrollbar-width: thin; padding: 0 12px 18px; }
  section + section { margin-top: 13px; }
  h2 {
    margin: 0 12px 4px;
    font: 650 .71rem/1.5 var(--fl-font);
    color: var(--fl-nav-muted);
  }
  nav a {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: 35px;
    padding: 5px 12px;
    border-radius: 12px;
    color: var(--fl-nav-ink);
    font: 560 .865rem/1.35 var(--fl-font);
    text-decoration: none;
  }
  nav a :global(svg) { flex: none; color: var(--fl-nav-muted); }
  @media (hover: hover) { nav a:hover { background: rgb(255 255 255 / 60%); } }
  @media (hover: hover) { :global(.gant-v4) nav a:hover { background: var(--fl-selected-bg); } }
  nav a[aria-current] {
    color: var(--fl-accent-hover);
    background: var(--fl-accent-soft);
    font-weight: 720;
  }
  nav a[aria-current] :global(svg) { color: var(--fl-accent); stroke-width: 2; }
  nav a:focus-visible, .rail-brand :is(a,button):focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: -2px;
  }
  .as-drawer nav { touch-action: pan-y; overscroll-behavior: contain; }
  .as-drawer nav a { min-height: 44px; }
  .as-drawer .rail-brand { padding: 12px 16px 10px; }
  @media (max-height: 760px) and (min-width: 901px) {
    .rail-brand { padding-block: 9px; }
    section + section { margin-top: 7px; }
    nav a { min-height: 31px; }
  }
</style>
