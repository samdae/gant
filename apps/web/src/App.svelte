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

  import { homeRoute } from "./lib/workspaceNavigation";
  import Research from "./routes/Research.svelte";
  import Portfolio from "./routes/Portfolio.svelte";
  import WorkspaceNav from "./components/WorkspaceNav.svelte";
  import ViewportProgress from "./components/ViewportProgress.svelte";
  import { isForecastLab, isPublicViewer } from "./lib/workspace";

  const routes = {
    ...(isForecastLab ? { "/research": Research, "/research/:id": Research, "/results": Research, "/performance": Research, "/observe": Research, "/dashboard": Dashboard, "/portfolio": Portfolio } : {}),
    "/": isForecastLab ? NotFoundRedirect : Dashboard,
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
    ...(!isPublicViewer ? { "/auth": Auth } : {}),
    "*": NotFoundRedirect,
  };

  onMount(() => {
    if (!window.location.hash) {
      window.location.hash = isForecastLab ? "#" + homeRoute : "#/";
    }
    loadTickerNames();
  });

  $: showMode = ["/dashboard", "/portfolio", "/positions"].includes($location) || $location.startsWith("/trade/");
  $: showCurrency = ["/dashboard", "/portfolio", "/positions", "/reports", "/retrospective", "/schedules"].includes($location);

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
      <WorkspaceNav denseControls={showMode && showCurrency}>
        {#if showMode || showCurrency}
          <AppHeader {showMode} {showCurrency} />

        {/if}
      </WorkspaceNav>
      <main class="main-content" id="workspace-content" tabindex="-1"><Router {routes} /></main>
    </div>
  </div>
  <ViewportProgress />
{:else}
  <div class="app-shell"><AppHeader /><main class="main-content"><Router {routes} /></main><BottomNav /></div>
{/if}

<style>
  .app-shell {
    width: min(100vw, 480px);
    margin: 0 auto;
    min-height: 100dvh;
    position: relative;
    border-inline: 1px solid rgb(255 255 255 / 4%);
  }
  :global(.app-header), :global(.bottom-nav) {
    width: min(100vw, 480px); left: 50%; right: auto; transform: translateX(-50%);
  }
  .workspace {
    --content-max: 1320px;
    --content-gutter: clamp(20px, 3.5vw, 54px);
    --content-top: clamp(20px, 2vw, 30px);
    min-height: 100dvh;
    width: 100%;
    font-family: var(--fl-font);
    font-variant-numeric: tabular-nums;
    color: var(--fl-ink);
    background: var(--fl-bg);
    isolation: isolate;
  }
  .workspace-body { min-width:0; }
  .workspace .main-content { max-width:var(--content-max); margin-inline:auto; padding:0; outline:none; }
  .skip {
    position: fixed; top: -64px; left: 12px; z-index: 160;
    padding: 10px 15px; border-radius: 12px; background: var(--fl-surface); color: var(--fl-accent);
  }
  .skip:focus { top: 12px; }
  @media (max-width: 900px) {
    .workspace { --content-gutter: clamp(14px, 3.5vw, 30px); --content-top: 23px; }
    .workspace-body { margin-left: 0; padding-bottom: calc(83px + env(safe-area-inset-bottom)); }
  }
</style>
