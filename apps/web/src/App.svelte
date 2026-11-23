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

<div class="app-shell" class:workspace={isForecastLab}>
  {#if isForecastLab}<WorkspaceNav />{/if}
  {#if !isForecastLab || $location !== "/research"}
    {#key isForecastLab && $location === "/portfolio"}
      <AppHeader />
    {/key}
  {/if}

  <main class="main-content">
    <Router {routes} />
  </main>

  {#if !isForecastLab}<BottomNav />{/if}
</div>

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
  .workspace { width:100%; max-width:none; border:0; }
  .workspace .main-content { padding:0; }
  .workspace :global(.app-header) { position:relative; left:auto; width:100%; transform:none; }
  .workspace :global(.control-shell), .workspace :global(.page-container) { max-width:1160px; }
  .workspace :global(.page-container) { padding-bottom:48px; }
</style>
