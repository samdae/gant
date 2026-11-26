<script lang="ts">
  import { onMount, tick } from "svelte";
  import { location } from "svelte-spa-router";
  import { currentPage, homeRoute } from "../lib/workspaceNavigation";
  import { isPublicViewer } from "../lib/workspace";
  import WorkspaceRail from "./WorkspaceRail.svelte";
  import WorkspaceIcon from "./WorkspaceIcon.svelte";
  import GantMark from "./GantMark.svelte";

  const tabs = [
    { href: "/research", label: "연구", group: "예측 연구", icon: "research" },
    { href: "/reports", label: "리포트", group: "분석 기록", icon: "reports" },
    { href: "/dashboard", label: "대시보드", icon: "dashboard" },
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
  $: activeTab = tabs.find((tab) => tab.href === context.page.route)
    ?? tabs.find((tab) => tab.group === context.section.name);

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
  function drawerGestures(node: HTMLDialogElement) {
    let backdropPointer: number | null = null;
    function outside(x: number, y: number) {
      const bounds = node.getBoundingClientRect();
      return (
        x < bounds.left ||
        x >= bounds.right ||
        y < bounds.top ||
        y >= bounds.bottom
      );
    }
    function down(event: PointerEvent) {
      backdropPointer =
        event.isPrimary &&
        event.button === 0 &&
        outside(event.clientX, event.clientY)
          ? event.pointerId
          : null;
    }
    function up(event: PointerEvent) {
      if (
        backdropPointer === event.pointerId &&
        outside(event.clientX, event.clientY) &&
        node.open
      ) {
        event.preventDefault();
        finish();
      }
      backdropPointer = null;
    }
    const cancel = () => {
      backdropPointer = null;
    };
    function suppressClosedClick(event: MouseEvent) {
      if (!node.open) {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    let touch: {
      x: number;
      y: number;
      axis: "pending" | "horizontal" | "vertical";
    } | null = null;
    function beginTouch(event: TouchEvent) {
      const point = event.touches[0];
      touch =
        event.touches.length === 1
          ? { x: point.clientX, y: point.clientY, axis: "pending" }
          : null;
    }
    function moveTouch(event: TouchEvent) {
      if (!touch || event.touches.length !== 1) return;
      const point = event.touches[0];
      const dx = point.clientX - touch.x,
        dy = point.clientY - touch.y;
      if (touch.axis === "pending" && Math.max(Math.abs(dx), Math.abs(dy)) > 10)
        touch.axis = dx > Math.abs(dy) * 1.5 ? "horizontal" : "vertical";
      if (touch.axis === "horizontal" && event.cancelable)
        event.preventDefault();
    }
    function endTouch(event: TouchEvent) {
      if (
        touch?.axis === "horizontal" &&
        event.changedTouches[0].clientX - touch.x >= 64 &&
        node.open
      ) {
        if (event.cancelable) event.preventDefault();
        finish();
      }
      touch = null;
    }
    const cancelTouch = () => {
      touch = null;
    };
    node.addEventListener("touchstart", beginTouch, { passive: true });
    node.addEventListener("touchmove", moveTouch, { passive: false });
    node.addEventListener("touchend", endTouch, { passive: false });
    node.addEventListener("touchcancel", cancelTouch);
    node.addEventListener("pointerdown", down);
    node.addEventListener("pointerup", up);
    node.addEventListener("pointercancel", cancel);
    node.addEventListener("click", suppressClosedClick, true);
    return {
      destroy() {
        node.removeEventListener("touchstart", beginTouch);
        node.removeEventListener("touchmove", moveTouch);
        node.removeEventListener("touchend", endTouch);
        node.removeEventListener("touchcancel", cancelTouch);
        node.removeEventListener("pointerdown", down);
        node.removeEventListener("pointerup", up);
        node.removeEventListener("pointercancel", cancel);
        node.removeEventListener("click", suppressClosedClick, true);
      },
    };
  }
  onMount(() => {
    const desktop = window.matchMedia("(min-width: 901px)");
    const resize = () => {
      if (desktop.matches && dialog.open) finish(true);
    };
    const navigate = () => {
      if (dialog.open) finish(true);
    };
    window.addEventListener("hashchange", navigate);
    desktop.addEventListener("change", resize);
    return () => {
      desktop.removeEventListener("change", resize);
      window.removeEventListener("hashchange", navigate);
    };
  });
</script>

<aside class="desktop-rail"><WorkspaceRail /></aside>
<header class="context-bar">
  <div class="context-inner">
    <a
      href={"#" + homeRoute}
      class="mobile-brand"
      aria-label="GANT 분석 리포트 홈"><GantMark size={26} /><b>GANT</b></a
    >
    <nav aria-label="현재 위치" class="crumb">
      <span>{context.section.name}</span><WorkspaceIcon
        name="chevron"
        size={12}
      /><strong>{context.page.label}</strong>
    </nav>
    <div class="actions"><slot /></div>
    <div class="access">
      {#if isPublicViewer}<i class="public-lamp" aria-hidden="true"
        ></i>{:else}<WorkspaceIcon name="auth" size={15} />{/if}<span
        >{isPublicViewer ? "공개 열람" : "운영 콘솔"}</span
      >
    </div>
  </div>
</header>
<nav class="phone-tabs" aria-label="모바일 주 탐색">
  {#each tabs as tab}<a
      href={"#" + tab.href}
      aria-current={!open && tab === activeTab ? "location" : undefined}
      ><WorkspaceIcon name={tab.icon} size={21} /><span>{tab.label}</span></a
    >{/each}
  <button
    type="button"
    bind:this={opener}
    aria-controls="workspace-drawer"
    aria-expanded={open}
    aria-label="전체 메뉴 열기"
    class:active={open || !activeTab}
    on:click={showMenu}
    ><WorkspaceIcon name="menu" size={21} /><span>전체 메뉴</span></button
  >
</nav>
<dialog
  id="workspace-drawer"
  aria-label="전체 메뉴"
  bind:this={dialog}
  use:drawerGestures
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
  .public-lamp {
    width: 8px;
    height: 8px;
    flex: none;
    border-radius: 50%;
    background: #75dc94;
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
    touch-action: pan-y;
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
  :global(html:has(#workspace-drawer[open])) {
    overscroll-behavior-x: none;
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
      display: flex;
    }
    @media (max-width: 520px) {
      .context-inner {
        display: grid;
        grid-template-columns: auto 1fr;
        align-items: center;
      }
      .access,
      .actions:not(:empty) + .access {
        grid-column: 2;
        grid-row: 1;
        justify-self: end;
        margin: 0;
        border: 0;
        padding: 0;
      }
      .actions:not(:empty) {
        grid-column: 1/-1;
        grid-row: 2;
        justify-self: end;
        max-width: 100%;
      }
    }
    .phone-tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      position: fixed;
      z-index: 60;
      bottom: 0;
      left: 0;
      right: 0;
      box-sizing: border-box;
      padding-block: 4px max(4px, env(safe-area-inset-bottom));
      padding-inline: max(5px, env(safe-area-inset-left), env(safe-area-inset-right));
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
      padding-inline: 0;
      white-space: nowrap;
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
