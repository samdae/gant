<script lang="ts">
  import { onMount, tick } from "svelte";
  import { location } from "svelte-spa-router";
  import { currentPage } from "../lib/workspaceNavigation";
  import { isPublicViewer } from "../lib/workspace";
  import WorkspaceRail from "./WorkspaceRail.svelte";
  import WorkspaceIcon from "./WorkspaceIcon.svelte";
  import GantMark from "./GantMark.svelte";

  const tabs = [
    { href: "/research", label: "연구", group: "예측 연구", icon: "research" },
    { href: "/reports", label: "리포트", group: "분석 기록", icon: "reports" },
    {
      href: "/portfolio",
      label: "모의계좌",
      group: "모의 거래",
      icon: "portfolio",
    },
  ];
  let dialog: HTMLDialogElement;
  let opener: HTMLButtonElement;
  let open = false;
  let viaLink = false;
  $: context = currentPage($location);

  function showMenu() {
    viaLink = false;
    dialog.showModal();
    open = true;
    dialog.querySelector<HTMLButtonElement>("button")?.focus();
  }
  function finish(navigated = false) {
    viaLink = navigated;
    dialog.close();
  }
  async function closed() {
    open = false;
    await tick();
    if (viaLink)
      document
        .getElementById("workspace-content")
        ?.focus({ preventScroll: true });
    else if (opener?.offsetParent) opener.focus({ preventScroll: true });
  }
  onMount(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    const resize = () => {
      if (desktop.matches && dialog.open) finish(true);
    };
    desktop.addEventListener("change", resize);
    return () => desktop.removeEventListener("change", resize);
  });
</script>

<aside class="desktop-rail"><WorkspaceRail /></aside>
<header class="context-bar">
  <div class="context-inner">
    <a href="#/research" class="mobile-brand" aria-label="GANT 연구 홈"
      ><GantMark size={26} /><b>GANT</b></a
    >
    <nav aria-label="현재 위치" class="crumb">
      <span>{context.section.name}</span><WorkspaceIcon
        name="chevron"
        size={12}
      /><strong>{context.page.label}</strong>
    </nav>
    <div class="actions"><slot /></div>
    <div class="access">
      <WorkspaceIcon name={isPublicViewer ? "globe" : "auth"} size={15} /><span
        >{isPublicViewer ? "공개 열람" : "운영 콘솔"}</span
      >
    </div>
  </div>
</header>
<nav class="phone-tabs" aria-label="모바일 주 탐색">
  {#each tabs as tab}<a
      href={"#" + tab.href}
      aria-current={context.section.name === tab.group ? "location" : undefined}
      ><WorkspaceIcon name={tab.icon} size={21} /><span>{tab.label}</span></a
    >{/each}
  <button
    type="button"
    bind:this={opener}
    aria-controls="workspace-drawer"
    aria-expanded={open}
    aria-label="전체 메뉴 열기"
    class:active={open ||
      !tabs.some((tab) => tab.group === context.section.name)}
    on:click={showMenu}
    ><WorkspaceIcon name="menu" size={21} /><span>전체 메뉴</span></button
  >
</nav>
<dialog
  id="workspace-drawer"
  aria-label="전체 메뉴"
  bind:this={dialog}
  on:close={closed}
>
  <WorkspaceRail
    drawer
    dismiss={() => finish()}
    onNavigate={() => finish(true)}
  />
</dialog>

<style>
  .desktop-rail {
    position: fixed;
    left: 0;
    inset-block: 0;
    width: var(--rail-width);
    border-right: 1px solid var(--fl-line);
    z-index: 40;
  }
  .context-bar {
    background: var(--fl-bg);
    border-bottom: 1px solid var(--fl-line);
  }
  .context-inner {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 8px var(--content-gutter);
    min-height: 55px;
  }
  .crumb,
  .access,
  .mobile-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--fl-muted);
    white-space: nowrap;
  }
  .crumb {
    font-size: 13px;
  }
  .crumb strong {
    color: var(--fl-ink);
    font-weight: 650;
  }
  .actions {
    margin-left: auto;
  }
  .actions:empty {
    display: none;
  }
  .access {
    margin-left: auto;
    font-size: 12px;
  }
  .actions:not(:empty) + .access {
    margin-left: 0;
    border-left: 1px solid var(--fl-line);
    padding-left: 14px;
  }
  .mobile-brand,
  .phone-tabs {
    display: none;
  }
  dialog {
    position: fixed;
    inset: 0 0 0 auto;
    margin: 0;
    width: min(370px, 88vw);
    max-width: none;
    height: 100dvh;
    max-height: none;
    overflow: hidden;
    background: var(--fl-surface);
    border: 0;
    padding: env(safe-area-inset-top) 0 env(safe-area-inset-bottom);
    color: var(--fl-ink);
    box-shadow: -10px 0 50px #0005;
  }
  dialog::backdrop {
    background: #0009;
  }
  @media (max-width: 900px) {
    .desktop-rail,
    .crumb {
      display: none;
    }
    .mobile-brand {
      display: flex;
      color: var(--fl-ink);
      text-decoration: none;
    }
    .mobile-brand b {
      transform: skewX(-7deg);
      font-size: 19px;
      letter-spacing: -1px;
    }
    .context-inner {
      min-height: 50px;
      flex-wrap: wrap;
      gap: 6px 12px;
      padding-block: 5px;
    }
    .actions:not(:empty) + .access {
      display: none;
    }
    .phone-tabs {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      position: fixed;
      z-index: 60;
      bottom: 0;
      left: 0;
      right: 0;
      box-sizing: border-box;
      padding: 4px max(5px, env(safe-area-inset-right))
        max(4px, env(safe-area-inset-bottom))
        max(5px, env(safe-area-inset-left));
      background: var(--fl-surface);
      border-top: 1px solid var(--fl-line);
    }
    .phone-tabs :is(a, button) {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 3px;
      flex-direction: column;
      min-height: 48px;
      color: var(--fl-muted);
      font: 550 11px/1.3 var(--fl-font);
      background: none;
      border: 0;
      text-decoration: none;
    }
    .phone-tabs a,
    .phone-tabs button {
      position: relative;
    }
    .phone-tabs :is([aria-current], .active)::before {
      content: "";
      position: absolute;
      top: 0;
      width: 22px;
      height: 2px;
      background: var(--fl-accent);
    }
    .phone-tabs :is([aria-current], .active) {
      color: var(--fl-accent);
      font-weight: 750;
    }
    .phone-tabs :focus-visible,
    .mobile-brand:focus-visible {
      outline: 2px solid var(--fl-accent);
      outline-offset: -2px;
    }
  }
</style>
