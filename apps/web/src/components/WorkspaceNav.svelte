<script lang="ts">
  import { onMount, tick } from "svelte";
  import { location } from "svelte-spa-router";
  import WorkspaceRail from "./WorkspaceRail.svelte";
  import { currentPage } from "../lib/workspaceNavigation";

  let drawer: HTMLDialogElement;
  let opener: HTMLButtonElement;
  let open = false;
  let lastRoute = "";
  $: context = currentPage($location);
  $: if ($location !== lastRoute) {
    lastRoute = $location;
    if (open) closeDrawer(true);
  }

  function openDrawer() {
    if (drawer.open) return;
    drawer.showModal();
    open = true;
  }
  async function closeDrawer(navigated = false) {
    drawer?.close();
    open = false;
    if (navigated) {
      await tick();
      const content = document.getElementById("workspace-content");
      content?.focus({ preventScroll: true });
    } else opener?.focus({ preventScroll: true });
  }
  onMount(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    const dismissOnResize = () => {
      if (desktop.matches && drawer.open) closeDrawer(true);
    };
    desktop.addEventListener("change", dismissOnResize);
    return () => desktop.removeEventListener("change", dismissOnResize);
  });
</script>

<aside class="desktop-rail"><WorkspaceRail /></aside>
<div class="workspace-top">
  <button
    class="menu-toggle"
    type="button"
    bind:this={opener}
    aria-label="전체 메뉴 열기"
    aria-controls="workspace-drawer"
    aria-expanded={open}
    on:click={openDrawer}
  >
    <svg viewBox="0 0 24 24" aria-hidden="true"
      ><path d="M3 6h18M3 12h18M3 18h18" /></svg
    >
  </button>
  <nav class="crumb" aria-label="현재 위치">
    <span class="ancestor">{context.section}</span><span
      class="separator"
      aria-hidden="true">/</span
    >
    {#if context.detail}
      <a href={"#" + context.page.route}>{context.page.label}</a>
      <span aria-hidden="true">/</span><strong aria-current="page"
        >{context.detail.toUpperCase()}</strong
      >
    {:else}
      <strong aria-current="page">{context.page.label}</strong>
    {/if}
  </nav>
  <div class="actions"><slot /></div>
</div>
<dialog
  id="workspace-drawer"
  aria-label="작업 공간 메뉴"
  bind:this={drawer}
  on:close={() => (open = false)}
>
  <button
    class="backdrop-dismiss"
    type="button"
    tabindex="-1"
    aria-label="메뉴 배경 닫기"
    on:click={() => closeDrawer()}
  ></button>
  <div class="drawer-panel">
    <WorkspaceRail
      onNavigate={() => closeDrawer(true)}
      dismiss={() => closeDrawer()}
    />
  </div>
</dialog>

<style>
  .desktop-rail {
    position: fixed;
    z-index: 110;
    inset: 0 auto 0 0;
    width: var(--rail-width);
    overflow-y: auto;
    background: var(--fl-nav);
    scrollbar-width: thin;
    scrollbar-color: #405474 var(--fl-nav);
  }
  .workspace-top {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0 clamp(20px, 3.5vw, 48px);
    min-height: 64px;
    border-bottom: 1px solid var(--fl-line);
    background: var(--fl-surface);
    color: var(--fl-ink);
  }
  .crumb {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    min-width: 0;
    white-space: nowrap;
    color: var(--fl-muted);
  }
  .crumb strong {
    overflow: hidden;
    text-overflow: ellipsis;
    color: var(--fl-ink);
    font-weight: 650;
  }
  .crumb span[aria-hidden] {
    color: #aab6c8;
  }
  .crumb a:hover {
    text-decoration: underline;
  }
  .actions {
    margin-left: auto;
    display: flex;
    align-items: center;
    min-width: 0;
  }
  .menu-toggle {
    display: none;
    width: 40px;
    height: 40px;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--fl-line);
    border-radius: 9px;
    background: white;
    color: var(--fl-ink);
    flex: none;
  }
  .menu-toggle svg {
    width: 19px;
    height: 19px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.7;
    stroke-linecap: round;
  }
  .menu-toggle:focus-visible,
  .crumb a:focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: 3px;
  }
  dialog {
    border: 0;
    padding: 0;
    margin: 0;
    width: 100vw;
    max-width: none;
    height: 100dvh;
    max-height: none;
    background: transparent;
    color: inherit;
  }
  dialog::backdrop {
    background: rgb(8 20 37 / 52%);
  }
  .backdrop-dismiss {
    position: absolute;
    inset: 0;
    border: 0;
    background: transparent;
  }
  .drawer-panel {
    position: relative;
    width: min(290px, 85vw);
    height: 100%;
    overflow-y: auto;
    background: var(--fl-nav);
  }
  @media (max-width: 900px) {
    .desktop-rail {
      display: none;
    }
    .menu-toggle {
      display: flex;
    }
    .workspace-top {
      min-height: 58px;
      gap: 10px;
      padding: 5px 14px;
    }
  }
  @media (max-width: 550px) {
    .ancestor,
    .separator {
      display: none;
    }
    .crumb {
      gap: 5px;
      font-size: 12px;
    }
    .workspace-top {
      gap: 8px;
      padding: 5px 10px;
    }
  }
</style>
