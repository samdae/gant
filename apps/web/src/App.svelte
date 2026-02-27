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
  import Retrospective from "./routes/Retrospective.svelte";
  import RetroDetail from "./routes/RetroDetail.svelte";
  import About from "./routes/About.svelte";
  import Auth from "./routes/Auth.svelte";
  import NotFoundRedirect from "./routes/NotFoundRedirect.svelte";
  import { loadTickerNames } from "./stores/tickerNames";

  const routes = {
    "/": Dashboard,
    "/positions": Positions,
    "/schedules": Schedules,
    "/schedules/:ticker": ScheduleDetail,
    "/trade/:ticker": TradeDetail,
    "/reports": Reports,
    "/reports/:ticker": ReportDetail,
    "/live": Live,
    "/reflections": Reflections,
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

<AppHeader />

<main class="main-content">
  <Router {routes} />
</main>

<BottomNav />
