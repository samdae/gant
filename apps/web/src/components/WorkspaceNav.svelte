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
    { href: "/dashboard", label: "대시보드", icon: "dashboard" },
    {
      href: "/portfolio",
      label: "모의계좌",
      group: "모의 거래",
      icon: "portfolio",
    },
  ];
  let dialog: HTMLDialogElement;
  export let denseControls = false;
  let opener: HTMLButtonElement;
  let open = false;
  let viaLink = false;
  let closeTimer: number | undefined;
  $: context = currentPage($location);
  $: activeTab = tabs.find((tab) => tab.href === context.page.route)
    ?? tabs.find((tab) => tab.group === context.section.name);

  // Move the rim reflection within the glass, without moving text or blurring the page.
  function glassRim(node: HTMLElement) {
    const allowed = window.matchMedia("(hover: hover) and (prefers-reduced-motion: no-preference)");
    let frame = 0, x = 0, y = 0;
    function move(event: PointerEvent) {
      if (event.pointerType !== "mouse" || !allowed.matches) return;
      x = event.clientX;
      y = event.clientY;
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const box = node.getBoundingClientRect();
        node.style.setProperty("--rim-x", (x - box.left) + "px");
        node.style.setProperty("--rim-y", (y - box.top) + "px");
      });
    }
    node.addEventListener("pointermove", move, { passive: true });
    return { destroy() {
      node.removeEventListener("pointermove", move);
      cancelAnimationFrame(frame);
    } };
  }

  function showMenu(event: MouseEvent) {
    opener = event.currentTarget as HTMLButtonElement;
    if (dialog.open) return;
    viaLink = false;
    delete dialog.dataset.motion;
    dialog.showModal();
    open = true;
    dialog.querySelector<HTMLButtonElement>("button")?.focus();
  }
  function finish(navigated = false) {
    viaLink ||= navigated;
    if (!dialog.open || dialog.dataset.motion === "closing") return;
    dialog.dataset.motion = "closing";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      dialog.close();
      return;
    }
    // Also complete if the browser cancels the transition during a resize.
    closeTimer = window.setTimeout(() => { if (dialog.open) dialog.close(); }, 270);
  }
  function motionEnded(event: TransitionEvent) {
    if (dialog.dataset.motion === "closing" && event.target === dialog
        && !event.pseudoElement && event.propertyName === "transform" && dialog.open) {
      dialog.close();
    }
  }
  async function closed() {
    clearTimeout(closeTimer);
    delete dialog.dataset.motion;
    dialog.style.removeProperty("--drawer-offset");
    dialog.style.removeProperty("--drawer-shade");
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
      if (!node.open || node.dataset.motion === "closing") {
        event.preventDefault();
        event.stopPropagation();
      }
    }
    let touch: {
      x: number;
      y: number;
      id: number;
      axis: "pending" | "horizontal" | "vertical";
    } | null = null;
    function releaseDrag() {
      touch = null;
      if (node.dataset.motion === "dragging") delete node.dataset.motion;
      node.style.removeProperty("--drawer-offset");
      node.style.removeProperty("--drawer-shade");
    }
    function beginTouch(event: TouchEvent) {
      const point = event.touches[0];
      if (node.dataset.motion === "closing") return;
      if (event.touches.length !== 1 || outside(point.clientX, point.clientY)) {
        releaseDrag();
        return;
      }
      touch = { x: point.clientX, y: point.clientY, id:point.identifier, axis:"pending" };
    }
    function moveTouch(event: TouchEvent) {
      if (!touch || event.touches.length !== 1) return;
      const point = event.touches[0];
      const dx = point.clientX - touch.x,
        dy = point.clientY - touch.y;
      if (touch.axis === "pending" && Math.max(Math.abs(dx), Math.abs(dy)) > 10)
        touch.axis = dx > Math.abs(dy) * 1.5 ? "horizontal" : "vertical";
      if (touch.axis === "horizontal" && node.dataset.motion !== "closing") {
        if (event.cancelable) event.preventDefault();
        const offset = Math.max(0, Math.min(node.offsetWidth, dx));
        node.dataset.motion = "dragging";
        node.style.setProperty("--drawer-offset", offset + "px");
        node.style.setProperty("--drawer-shade", String(1 - offset / node.offsetWidth));
      }
    }
    function endTouch(event: TouchEvent) {
      const point = event.changedTouches[0];
      if (touch?.axis === "horizontal" && point.identifier === touch.id) {
        if (event.cancelable) event.preventDefault(); // No link activation after a drag.
        if (point.clientX - touch.x >= 64 && node.open) {
          touch = null;
          finish();
          return;
        }
      }
      releaseDrag();
    }
    node.addEventListener("touchstart", beginTouch, { passive: true });
    node.addEventListener("touchmove", moveTouch, { passive: false });
    node.addEventListener("touchend", endTouch, { passive: false });
    node.addEventListener("touchcancel", releaseDrag);
    node.addEventListener("pointerdown", down);
    node.addEventListener("pointerup", up);
    node.addEventListener("pointercancel", cancel);
    node.addEventListener("click", suppressClosedClick, true);
    return {
      destroy() {
        node.removeEventListener("touchstart", beginTouch);
        node.removeEventListener("touchmove", moveTouch);
        node.removeEventListener("touchend", endTouch);
        node.removeEventListener("touchcancel", releaseDrag);
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
      if (dialog.open) finish(true);
    };
    const navigate = () => {
      if (dialog.open) finish(true);
    };
    window.addEventListener("hashchange", navigate);
    desktop.addEventListener("change", resize);
    return () => {
      clearTimeout(closeTimer);
      desktop.removeEventListener("change", resize);
      window.removeEventListener("hashchange", navigate);
    };
  });
</script>

<header class="context-bar">
  <div class="context-inner" class:dense={denseControls}>
    <a href="#/dashboard" class="mobile-brand" aria-label="GANT 대시보드">
      <GantMark size={32} /><b>GANT</b>
    </a>
    <nav class="desk-tabs" aria-label="주 탐색">
      {#each [tabs[2], tabs[1], tabs[0], tabs[3]] as tab}
        <a href={"#" + tab.href} aria-current={tab === activeTab ? "location" : undefined}>{tab.label}</a>
      {/each}
    </nav>
    <div class="actions"><slot /></div>
    <div class="access" title={isPublicViewer ? "공개 열람" : "운영 콘솔"}>
      {#if isPublicViewer}<i class="public-lamp" aria-hidden="true"
        ></i>{:else}<WorkspaceIcon name="auth" size={15} />{/if}<span
        >{isPublicViewer ? "공개 열람" : "운영 콘솔"}</span
      >
    </div>
    <button class="desktop-menu" type="button" aria-label="전체 메뉴 열기" aria-controls="workspace-drawer" aria-expanded={open} on:click={showMenu}>
      <WorkspaceIcon name="menu" size={20} /><span>전체 메뉴</span>
    </button>
  </div>
</header>
<nav class="phone-tabs" use:glassRim style:--tab-index={open || !activeTab ? 4 : tabs.indexOf(activeTab)} aria-label="모바일 주 탐색">
  {#each tabs as tab}<a
      href={"#" + tab.href}
      aria-current={!open && tab === activeTab ? "location" : undefined}
      ><WorkspaceIcon name={tab.icon} size={21} /><span>{tab.label}</span></a
    >{/each}
  <button
    type="button"
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
  on:cancel|preventDefault={() => finish()}
  on:transitionend={motionEnded}
  on:close={closed}
>
  <WorkspaceRail
    drawer
    dismiss={() => finish()}
    onNavigate={() => finish(true)}
  />
</dialog>

<style>
  .context-bar {
    position:sticky; top:0; z-index:45; background:var(--fl-glass);
    border-bottom:1px solid var(--fl-line);
    backdrop-filter:var(--fl-glass-blur); -webkit-backdrop-filter:var(--fl-glass-blur);
  }
  .context-inner {
    max-width:var(--content-max); padding:7px var(--content-gutter); margin-inline:auto;
    display:flex; align-items:center; min-height:68px; gap:clamp(10px,1.7vw,25px);
  }
  .mobile-brand,.desk-tabs,.desk-tabs a,.access,.desktop-menu { display:inline-flex; align-items:center; white-space:nowrap; }
  .mobile-brand {
    gap:9px; min-height:44px; color:var(--fl-ink); text-decoration:none;
  }
  .mobile-brand b { font:800 22px/1 var(--fl-font); letter-spacing:-.065em; }
  .desk-tabs { align-self:stretch; gap:2px; }
  .desk-tabs a {
    position:relative; padding:0 clamp(9px,1.3vw,18px); color:var(--fl-muted); font-size:.88rem;
    font-weight:620; text-decoration:none; border-radius:9px;
  }
  .desk-tabs a[aria-current] { color:var(--fl-accent); }
  .desk-tabs a[aria-current]::after {
    content:""; position:absolute; left:14%; right:14%; height:3px; border-radius:3px; bottom:0; background:currentColor;
  }
  .desk-tabs a:hover,.desktop-menu:hover { background:var(--fl-accent-soft); color:var(--fl-accent-hover); }
  .actions { margin-left:auto; }
  .actions:empty { display:none; }
  .access { margin-left:auto; gap:8px; color:var(--fl-muted); font-size:.77rem; font-weight:650; }
  .actions:not(:empty)+.access { margin-left:0; }
  .public-lamp { flex:none; width:7px; height:7px; border-radius:50%; background:#278265; box-shadow:0 0 0 3px rgb(31 129 86 / 12%); }
  .desktop-menu {
    padding:0 12px; gap:7px; min-height:42px; cursor:pointer; font:650 .8rem var(--fl-font);
    color:var(--fl-ink); background:var(--fl-surface); border:1px solid var(--fl-line); border-radius:12px;
  }
  .phone-tabs { display:none; }
  dialog { border:1px solid var(--fl-glass-edge); box-shadow:var(--fl-glass-shadow); backdrop-filter:var(--fl-glass-blur); }
  dialog {
    position: fixed;
    inset: max(9px, env(safe-area-inset-top)) max(9px, env(safe-area-inset-right)) max(9px, env(safe-area-inset-bottom)) auto;
    touch-action: pan-y;
    margin: 0;
    padding: 0;
    width: min(350px, calc(100vw - 44px));
    max-width: none;
    height: calc(100dvh - max(9px, env(safe-area-inset-top)) - max(9px, env(safe-area-inset-bottom)));
    max-height: none;
    overflow: hidden;
    border-radius: 24px;
    background: var(--fl-glass-raised);
    color: var(--fl-ink);
    transform: translateX(var(--drawer-offset, 0px));
  }
  :global(html:has(#workspace-drawer[open])) { overscroll-behavior-x: none; }
  dialog::backdrop { background: var(--bg-modal); opacity: var(--drawer-shade, 1); }
  dialog:global([data-motion="closing"]) { transform: translateX(calc(100% + 14px)); }
  dialog:global([data-motion="closing"])::backdrop { opacity: 0; }
  @media (prefers-reduced-motion: no-preference) {
    dialog, dialog::backdrop { transition: transform 220ms cubic-bezier(.22,.76,.22,1), opacity 220ms ease-out; }
    dialog:global([data-motion="dragging"]), dialog:global([data-motion="dragging"])::backdrop { transition: none; }
  }
  @media (max-width: 900px) {
    .desk-tabs,.desktop-menu { display:none; }
    .context-inner { min-height:57px; padding-block: max(5px,env(safe-area-inset-top)) 5px; gap:10px; }
    .mobile-brand { gap:7px; }
    .mobile-brand b { font-size:20px; }
    .phone-tabs {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      position: fixed;
      z-index: 60;
      left: max(10px, env(safe-area-inset-left));
      right: max(10px, env(safe-area-inset-right));
      bottom: max(9px, env(safe-area-inset-bottom));
      max-width: 468px;
      margin-inline: auto;
      padding: 5px;
      border-radius: 29px;
      color:#fcf6fa;
      border:1px solid rgb(255 232 242 / 36%);
      background:#422e42;
      background:linear-gradient(145deg,rgb(74 45 68 / 83%),rgb(45 32 50 / 87%));
      backdrop-filter:var(--fl-glass-blur); -webkit-backdrop-filter:var(--fl-glass-blur);
      box-shadow:inset 0 1px 1px rgb(255 250 244 / 44%),inset 0 -1px 2px rgb(225 173 201 / 24%),0 7px 24px -8px rgb(48 26 46 / 52%);
    }
    .phone-tabs::before {
      content: "";
      position: absolute;
      pointer-events: none;
      inset: 5px auto 5px 5px;
      width: calc((100% - 10px) / 5);
      border-radius: 23px;
      background: #f3e3ed;
      box-shadow: inset 0 1px 1px rgb(255 255 255 / 85%);
      transform: translateX(calc(var(--tab-index) * 100%));
    }
    @media (prefers-reduced-motion: no-preference) {
      .phone-tabs::before { transition: transform 240ms cubic-bezier(.2,.78,.17,1); }
    }
    .phone-tabs :is(a,button) {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 3px;
      min-height: 47px;
      min-width: 0;
      padding: 2px;
      white-space: nowrap;
      border: 0;
      border-radius: 23px;
      color: #f4eaf0;
      background: transparent;
      font: 580 .68rem/1.2 var(--fl-font);
      text-decoration: none;
      cursor: pointer;
    }
    .phone-tabs :is([aria-current],.active) {
      color: #52263f;
      font-weight: 760;
    }
    .phone-tabs :is([aria-current],.active) :global(svg) { stroke-width: 2; }
    .phone-tabs :focus-visible, .mobile-brand:focus-visible {
      outline: 2px solid var(--fl-accent); outline-offset: -2px;
    }
  }
  @media (max-width: 570px) {
    .context-inner { gap: 5px; }
    .actions:not(:empty) + .access { border: 0; }
    .context-inner.dense .access span {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip-path: inset(50%); white-space: nowrap;
    }
  }
  @media (max-width: 370px) {
    .context-inner.dense .mobile-brand b { display: none; }
  }
  @media (hover: hover) and (prefers-reduced-motion: no-preference) and (prefers-contrast: no-preference) {
    @supports (mask-composite: exclude) {
      .phone-tabs::after {
        content: "";
        position: absolute;
        pointer-events: none;
        inset: 0;
        padding: 1px;
        border-radius: inherit;
        background: radial-gradient(120px at var(--rim-x, 15%) var(--rim-y, 0px), #fff 10%, rgb(255 215 233 / 80%) 38%, transparent);
        mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        mask-composite: exclude;
      }
    }
  }
  @media (prefers-reduced-transparency: reduce), (prefers-contrast: more) {
    .phone-tabs { background:#372638; backdrop-filter:none; }
  }
  @media (forced-colors: active) {
    .phone-tabs :is([aria-current],.active), .public-lamp { outline: 2px solid Highlight; outline-offset: -2px; }
  }
</style>
