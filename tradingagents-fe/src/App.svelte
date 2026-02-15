<script lang="ts">
  import { onMount } from "svelte";
  import Router from "svelte-spa-router";
  import BottomNav from "./components/BottomNav.svelte";
  import Dashboard from "./routes/Dashboard.svelte";
  import Positions from "./routes/Positions.svelte";
  import Schedules from "./routes/Schedules.svelte";
  import ScheduleDetail from "./routes/ScheduleDetail.svelte";
  import TradeDetail from "./routes/TradeDetail.svelte";
  import Reports from "./routes/Reports.svelte";
  import ReportDetail from "./routes/ReportDetail.svelte";
  import Live from "./routes/Live.svelte";
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
    "/auth": Auth,
    "*": NotFoundRedirect,
  };

  onMount(() => {
    if (!window.location.hash) {
      window.location.hash = "#/";
    }
    loadTickerNames();
  });

</script>

<main class="main-content">
  <Router {routes} />
</main>

<BottomNav />
