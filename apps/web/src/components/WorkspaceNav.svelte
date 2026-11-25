<script lang="ts">
  import { tick } from "svelte";
  import { location } from "svelte-spa-router";
  import { currentPage, sections } from "../lib/workspaceNavigation";
  import { isPublicViewer } from "../lib/workspace";
  import WorkspaceRail from "./WorkspaceRail.svelte";

  let drawer: HTMLDialogElement;
  let opener: HTMLButtonElement;
  let open = false;
  $: context = currentPage($location);

  async function closeMenu() {
    drawer.close();
    await tick();
    opener?.focus();
  }
</script>

<header class="folio-mast">
  <div class="mast-inner">
    <a class="brand" href="#/research" aria-label="GANT Forecast Lab 연구 홈"
      ><span>GANT<span class="brand-dot">.</span></span><small
        >Forecast Lab</small
      ></a
    >
    <nav class="desktop-rail" aria-label="주 탐색">
      {#each sections as section}
        <a
          href={"#" + section.pages[0].route}
          class:active={context.section.name === section.name}>{section.name}</a
        >
      {/each}
    </nav>
    <span class="access">{isPublicViewer ? "공개 열람" : "운영 콘솔"}</span>
    <button
      class="menu-toggle"
      type="button"
      bind:this={opener}
      aria-label="전체 메뉴 열기"
      aria-expanded={open}
      aria-controls="workspace-drawer"
      on:click={() => {
        drawer.showModal();
        open = true;
      }}>메뉴 <span aria-hidden="true">☰</span></button
    >
  </div>
</header>
<div class="folio-subnav">
  <div class="sub-inner">
    <nav aria-label={context.section.name + " 세부 메뉴"}>
      {#each context.section.pages.filter((p) => !isPublicViewer || p.route !== "/auth") as page}
        <a
          href={"#" + page.route}
          aria-current={context.page.route === page.route ? "page" : undefined}
          >{page.label}</a
        >
      {/each}
    </nav>
    <div class="actions"><slot /></div>
  </div>
</div>
<dialog
  id="workspace-drawer"
  aria-label="전체 메뉴"
  bind:this={drawer}
  on:close={() => (open = false)}
>
  <WorkspaceRail dismiss={closeMenu} />
</dialog>

<style>
  .folio-mast {
    background: #272722;
    color: #fff;
  }
  .mast-inner,
  .sub-inner {
    max-width: 1280px;
    margin: auto;
    padding-inline: var(--content-gutter);
    box-sizing: border-box;
    display: flex;
    align-items: center;
  }
  .mast-inner {
    gap: clamp(20px, 4vw, 64px);
    min-height: 66px;
  }
  .brand {
    display: flex;
    align-items: baseline;
    gap: 10px;
    color: #fff;
    white-space: nowrap;
  }
  .brand > span {
    font:
      700 38px/0.9 Georgia,
      "Times New Roman",
      serif;
    letter-spacing: -2.3px;
  }
  .brand-dot {
    color: #e1a7ac;
  }
  .brand small {
    font:
      italic 16px Georgia,
      serif;
    color: #eae7dd;
  }
  .desktop-rail {
    display: flex;
    align-self: stretch;
    gap: clamp(18px, 2.5vw, 34px);
  }
  .desktop-rail a {
    color: #d6d4ca;
    font-size: 14px;
    display: flex;
    align-items: center;
    position: relative;
    padding: 0 2px;
    white-space: nowrap;
  }
  .desktop-rail a.active {
    color: white;
    font-weight: 750;
  }
  .desktop-rail a.active::after {
    content: "";
    position: absolute;
    height: 3px;
    inset: auto 0 0;
    background: #d9a3ae;
  }
  .access {
    margin-left: auto;
    font-size: 12px;
    color: #dedacf;
    white-space: nowrap;
  }
  .menu-toggle {
    display: none;
    background: none;
    border: 1px solid #77756d;
    color: #fff;
    padding: 7px 10px;
    font: inherit;
    font-size: 13px;
  }
  .folio-subnav {
    background: #fffefa;
    border-bottom: 1px solid var(--fl-line);
  }
  .sub-inner {
    min-height: 42px;
    gap: 12px;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .sub-inner nav {
    display: flex;
    gap: clamp(15px, 2.4vw, 30px);
  }
  .sub-inner a {
    font-size: 13px;
    min-height: 41px;
    display: flex;
    align-items: center;
    color: var(--fl-muted);
    border-bottom: 2px solid transparent;
  }
  .sub-inner a[aria-current] {
    color: var(--fl-accent);
    border-color: currentColor;
    font-weight: 750;
  }
  .actions:empty {
    display: none;
  }
  .actions {
    padding: 4px 0;
  }
  .mast-inner a:focus-visible,
  .menu-toggle:focus-visible {
    outline: 2px solid white;
    outline-offset: 3px;
  }
  dialog {
    position: fixed;
    inset: 10px 10px auto auto;
    margin: 0;
    padding: 0;
    border: 0;
    width: min(380px, calc(100vw - 20px));
    max-height: 90dvh;
    overflow-y: auto;
    color: var(--fl-ink);
    background: #fffefa;
    box-shadow: 0 12px 60px #24231c40;
  }
  dialog::backdrop {
    background: #1d191752;
  }
  @media (max-width: 830px) {
    .desktop-rail {
      display: none;
    }
    .menu-toggle {
      display: block;
    }
    .mast-inner {
      min-height: 58px;
      gap: 15px;
    }
    .brand > span {
      font-size: 32px;
    }
    .brand small {
      font-size: 14px;
    }
    .sub-inner {
      gap: 0 15px;
    }
    .actions {
      margin-left: auto;
    }
  }
  @media (max-width: 520px) {
    .sub-inner {
      align-items: center;
    }
    .actions:not(:empty) {
      width: 100%;
      border-top: 1px solid var(--fl-line);
      padding: 6px 0;
    }
    .access {
      font-size: 11px;
    }
  }
  @media (max-width: 830px) {
    .menu-toggle,
    .sub-inner nav a {
      min-height: 44px;
    }
    .menu-toggle {
      padding-inline: 12px;
    }
    .sub-inner nav a {
      font-size: 14px;
    }
  }
</style>
