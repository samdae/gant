<script lang="ts">
  import { isPublicViewer } from "../lib/workspace";
  import { location } from "svelte-spa-router";
  import { currentPage, sections } from "../lib/workspaceNavigation";
  import { viewMode } from "../stores/mode";

  export let dismiss: (() => void) | undefined = undefined;
  export let onNavigate: (() => void) | undefined = undefined;
  $: current = currentPage($location).page.route;

  function navigate(route: string) {
    if (route === "/") viewMode.set("analysis");
    onNavigate?.();
  }
</script>

<div class="rail">
  <div class="identity">
    <a
      class="brand"
      href="#/research"
      aria-label="Forecast Lab 연구 홈"
      on:click={() => navigate("/research")}
    >
      <svg
        class="mark"
        width="35"
        height="35"
        viewBox="0 0 36 36"
        aria-hidden="true"
      >
        <rect width="36" height="36" rx="9" fill="#4977f4" />
        <path
          d="M9 27V11l5-3v19zM17 23V13l5-3v13zM25 18v-7l4-3v10z"
          fill="white"
        />
      </svg>
      <span>Forecast <b>Lab</b></span>
    </a>
    {#if dismiss}
      <button
        class="dismiss"
        type="button"
        aria-label="메뉴 닫기"
        on:click={dismiss}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"
          ><path d="M6 6l12 12M18 6L6 18" /></svg
        >
      </button>
    {/if}
  </div>
  <nav aria-label="작업 공간 주 탐색">
    {#each sections as section}
      <div class="group" class:settings={section.name === "설정"}>
        <div class="group-label">{section.name}</div>
        {#each section.pages.filter((p) => !isPublicViewer || p.route !== "/auth") as page}
          <a
            class="item"
            href={"#" + page.route}
            class:active={current === page.route}
            aria-current={current === page.route ? "page" : undefined}
            on:click={() => navigate(page.route)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"
              ><path d={page.icon} /></svg
            >
            <span>{page.label}</span>
          </a>
        {/each}
      </div>
    {/each}
  </nav>
</div>

<style>
  .rail {
    background: var(--fl-nav);
    color: var(--fl-nav-ink);
    font-family: var(--fl-font);
    display: flex;
    flex-direction: column;
    min-height: 100%;
  }
  .identity {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 24px 20px 27px;
  }
  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: white;
    font-size: 21px;
    letter-spacing: -0.055em;
    font-weight: 650;
  }
  .brand b {
    font-weight: 480;
    color: #c5d5ee;
  }
  nav {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 22px;
    padding: 0 12px 18px;
  }
  .group-label {
    color: var(--fl-nav-muted);
    font-size: 11px;
    letter-spacing: 0.045em;
    font-weight: 650;
    padding: 0 12px 6px;
  }
  .item {
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 39px;
    margin: 2px 0;
    padding: 8px 12px;
    color: #c8d4e8;
    font-size: 14px;
    font-weight: 510;
    border-radius: 8px;
    line-height: 1.3;
  }
  .item svg,
  .dismiss svg {
    width: 18px;
    height: 18px;
    flex: none;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.65;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .item:hover {
    background: #1e304c;
    color: white;
  }
  .item.active {
    color: white;
    background: #25437b;
    box-shadow: inset 3px 0 #789cff;
    font-weight: 680;
  }
  .item.active svg {
    color: #bbd0ff;
  }
  .settings {
    margin-top: auto;
    padding-top: 14px;
    border-top: 1px solid #2a3850;
  }
  .dismiss {
    display: grid;
    place-items: center;
    width: 36px;
    height: 36px;
    background: transparent;
    border: 1px solid #43546c;
    color: white;
    border-radius: 8px;
  }
  a:focus-visible,
  button:focus-visible {
    outline: 2px solid #b5cdff;
    outline-offset: 2px;
  }
</style>
