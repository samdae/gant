<script lang="ts">
  import { location } from "svelte-spa-router";
  import { viewMode } from "../stores/mode";

  const pages = [
    ["/research", "예측 연구"], ["/", "대시보드"], ["/portfolio", "포트폴리오"],
    ["/positions","보유 종목"], ["/schedules","분석 예약"], ["/live","실시간"],
    ["/reports","분석 리포트"], ["/reflections","매매 검증"], ["/retrospective","회고 분석"],
    ["/about","서비스 소개"], ["/auth","관리자 인증"],
  ];
  let more = false;
  let trigger: HTMLButtonElement;
  $: if ($location) more = false;

  function active(route: string, current: string) {
    return current === route || (route !== "/" && current.startsWith(route + "/"));
  }
  function navigate(route: string) {
    if (route === "/") viewMode.set("analysis");
    more = false;
  }
  function escape(e: KeyboardEvent) {
    if (e.key === "Escape" && more) { more = false; trigger.focus(); }
  }
</script>

<svelte:window on:keydown={escape} />
<header class="workspace-header">
  <div class="bar">
    <a class="brand" href="#/research" aria-label="Forecast Lab 연구 홈">Forecast Lab</a>
    <nav aria-label="작업 공간">
      {#each pages.slice(0,3) as [route,label]}
        <a class:current={active(route, $location)} aria-current={active(route, $location) ? "page" : undefined}
          href={"#"+route} on:click={() => navigate(route)}>{label}</a>
      {/each}
      <button bind:this={trigger} type="button" aria-expanded={more} aria-controls="other-pages"
        on:click={() => more = !more}>전체 메뉴 <span aria-hidden="true">▾</span></button>
    </nav>
    {#if more}
      <nav class="menu" id="other-pages" aria-label="기능별 메뉴">
        {#each pages.slice(3) as [route,label]}
          <a class:current={active(route, $location)} href={"#"+route} on:click={() => navigate(route)}>{label}</a>
        {/each}
      </nav>
    {/if}
  </div>
</header>

<style>
  .workspace-header { color:#e8f3ee; background:#16383a; border-bottom:1px solid #325154; }
  .bar { position:relative; max-width:1160px; margin:auto; padding:9px 22px; display:flex; justify-content:space-between; align-items:center; gap:10px; }
  .brand { font-weight:750; letter-spacing:-.03em; white-space:nowrap; font-size:1.25rem; }
  nav { display:flex; align-items:center; gap:3px; }
  nav a, nav button { background:none; color:inherit; font:inherit; font-size:.9rem; border:0; border-radius:6px; padding:9px 12px; white-space:nowrap; }
  nav a:hover, nav button:hover, .current { color:white; background:#345954; }
  .menu { position:absolute; z-index:150; right:16px; top:calc(100% - 2px); width:min(340px,calc(100vw - 24px)); display:grid; grid-template-columns:1fr 1fr; padding:8px; border:1px solid #48625e; border-radius:8px; background:#173b38; box-shadow:0 8px 24px #0004; }
  a:focus-visible,button:focus-visible {outline:2px solid #bbe8d4;outline-offset:1px}
  @media(max-width:630px) {
    .bar {padding:8px 10px;flex-wrap:wrap;gap:4px;}
    .brand {font-size:1.06rem;}
    nav a,nav button {padding:8px 7px;font-size:.78rem;}
  }
</style>
