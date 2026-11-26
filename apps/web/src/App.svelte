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
    --frame-gap: 16px;
    --rail-width: clamp(212px, 16vw, 239px);
    --content-max: 1440px;
    --content-gutter: clamp(22px, 3vw, 52px);
    --content-top: clamp(24px, 2.4vw, 38px);
    min-height: 100dvh;
    width: 100%;
    font-family: var(--fl-font);
    font-variant-numeric: tabular-nums;
    color: var(--fl-ink);
    background: var(--fl-bg);
    isolation: isolate;
  }
  /* The pale field sits behind floating navigation. Data keeps a still reading plane. */
  .workspace::before {
    content: "";
    position: fixed;
    z-index: -1;
    inset: 0;
    pointer-events: none;
    background:
      radial-gradient(ellipse 52% 50% at 2% 6%, #a5cfc1 0%, transparent 88%),
      radial-gradient(ellipse 56% 41% at 96% -8%, #d6d1da 0%, transparent 90%),
      radial-gradient(ellipse 28% 44% at -4% 74%, #c1d7cf, transparent 90%),
      linear-gradient(155deg, #d9e8e1 0%, #eff3ed 51%, #e3ede9 100%);
  }
  .workspace-body { margin-left: var(--rail-width); min-width: 0; }
  .workspace .main-content { padding: 0; outline: none; }
  .skip {
    position: fixed; top: -64px; left: 12px; z-index: 160;
    padding: 10px 15px; border-radius: 12px; background: var(--fl-surface); color: var(--fl-accent);
  }
  .skip:focus { top: 12px; }
  @media (max-width: 900px) {
    .workspace { --content-gutter: clamp(14px, 3.5vw, 30px); --content-top: 23px; }
    .workspace-body { margin-left: 0; padding-bottom: calc(83px + env(safe-area-inset-bottom)); }
    .workspace::before {
      background:
        radial-gradient(ellipse 94% 39% at -12% -1%, #afd7c7, transparent 86%),
        radial-gradient(ellipse 67% 39% at 100% -6%, #ddd4db, transparent 85%),
        linear-gradient(153deg, #e7eeea, #eff4ef 55%, #dcebe5);
    }
  }
  @media (prefers-reduced-transparency: reduce), (prefers-contrast: more), (forced-colors: active) {
    .workspace::before { display: none; }
  }
</style>
