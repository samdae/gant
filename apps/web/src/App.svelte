<script lang="ts">
  import { onMount } from "svelte";
  import Router, { location } from "svelte-spa-router";
  import AppHeader from "./components/AppHeader.svelte";
  import BottomNav from "./components/BottomNav.svelte";
  import Dashboard from "./routes/Dashboard.svelte";
  import Positions from "./routes/Positions.svelte";
  import Schedules from "./routes/Schedules.svelte";
  import ScheduleDetail from "./routes/ScheduleDetail.svelte";
  import TradeDetail from "./routes/TradeDetail.svelte";
  import Reports from "./routes/Reports.svelte";
  import ReportDetail from "./routes/ReportDetail.svelte";
  import Live from "./routes/Live.svelte";
  import Reflections from "./routes/Reflections.svelte";
  import ReflectionDetail from "./routes/ReflectionDetail.svelte";
  import Retrospective from "./routes/Retrospective.svelte";
  import RetroDetail from "./routes/RetroDetail.svelte";
  import About from "./routes/About.svelte";
  import Auth from "./routes/Auth.svelte";
  import NotFoundRedirect from "./routes/NotFoundRedirect.svelte";
  import { loadTickerNames } from "./stores/tickerNames";

  import Research from "./routes/Research.svelte";
  import Portfolio from "./routes/Portfolio.svelte";
  import WorkspaceNav from "./components/WorkspaceNav.svelte";
  import { isForecastLab } from "./lib/workspace";

  const routes = {
    ...(isForecastLab ? { "/research": Research, "/portfolio": Portfolio } : {}),
    "/": isForecastLab ? Portfolio : Dashboard,
    "/positions": Positions,
    "/schedules": Schedules,
    "/schedules/:ticker": ScheduleDetail,
    "/trade/:ticker": TradeDetail,
    "/reports": Reports,
    "/reports/:ticker": ReportDetail,
    "/live": Live,
    "/reflections": Reflections,
    "/reflections/:id": ReflectionDetail,
    "/retrospective": Retrospective,
    "/retrospective/:ticker": RetroDetail,
    "/about": About,
    "/auth": Auth,
    "*": NotFoundRedirect,
  };

  onMount(() => {
    if (!window.location.hash) {
      window.location.hash = "#/";
    }
    loadTickerNames();
  });

  let lastLocation = "";
  $: if ($location && $location !== lastLocation) {
    lastLocation = $location;
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  }

</script>

{#if isForecastLab}
  <div class="workspace">
    <a class="skip" href="#workspace-content" on:click|preventDefault={() => document.getElementById("workspace-content")?.focus()}>본문으로 이동</a>
    <div class="workspace-body">
      <WorkspaceNav>
        {#if $location !== "/research"}
          {#key $location === "/portfolio"}<AppHeader />{/key}
        {:else}
          <a class="standalone" href="/research/">연구 단독 화면 <span aria-hidden="true">↗</span></a>
        {/if}
      </WorkspaceNav>
      <main class="main-content" id="workspace-content" tabindex="-1"><Router {routes} /></main>
    </div>
  </div>
{:else}
  <div class="app-shell"><AppHeader /><main class="main-content"><Router {routes} /></main><BottomNav /></div>
{/if}

<style>
  .app-shell {
    width: min(100vw, 480px);
    margin: 0 auto;
    min-height: 100dvh;
    position: relative;
    border-left: 1px solid rgba(255, 255, 255, 0.04);
    border-right: 1px solid rgba(255, 255, 255, 0.04);
  }

  :global(.app-header),
  :global(.bottom-nav) {
    width: min(100vw, 480px);
    left: 50%;
    right: auto;
    transform: translateX(-50%);
  }
  .workspace {
    --rail-width: 224px;
    min-height: 100dvh;
    width: 100%;
    font-family: var(--fl-font);
    font-variant-numeric: tabular-nums;
    background: var(--fl-bg);
    color: var(--fl-ink);
  }
  .workspace-body { margin-left: var(--rail-width); min-width: 0; }
  .workspace .main-content { padding: 0; outline: none; }
  .workspace :global(.page-container) { width:100%; max-width:none; padding:clamp(20px,3vw,42px) clamp(18px,3.5vw,48px) 48px; }
  .skip { position:fixed; top:-60px; left:8px; background:var(--fl-surface); color:var(--fl-accent); z-index:160; padding:8px 14px; }
  .skip:focus { top:8px; }
  .standalone { display:inline-flex; align-items:center; gap:7px; color:var(--fl-muted); font-size:12px; font-weight:600; padding:7px 4px; }
  .standalone:hover { color:var(--fl-accent); }
  @media(max-width:900px) { .workspace-body { margin-left:0; } }
</style>
