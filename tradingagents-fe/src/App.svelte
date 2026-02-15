<script lang="ts">
  import { onMount } from "svelte";
  import Router from "svelte-spa-router";
  import BottomNav from "./components/BottomNav.svelte";
  import Dashboard from "./routes/Dashboard.svelte";
  import Positions from "./routes/Positions.svelte";
  import Schedules from "./routes/Schedules.svelte";
  import ScheduleDetail from "./routes/ScheduleDetail.svelte";
  import TradeDetail from "./routes/TradeDetail.svelte";
  import Archive from "./routes/Archive.svelte";
  import Live from "./routes/Live.svelte";
  import Search from "./routes/Search.svelte";
  import Auth from "./routes/Auth.svelte";
  import NotFoundRedirect from "./routes/NotFoundRedirect.svelte";

  const routes = {
    "/": Dashboard,
    "/positions": Positions,
    "/schedules": Schedules,
    "/schedules/:ticker": ScheduleDetail,
    "/trade/:ticker": TradeDetail,
    "/archive/:ticker": Archive,
    "/live": Live,
    "/search": Search,
    "/auth": Auth,
    "*": NotFoundRedirect,
  };

  onMount(() => {
    if (!window.location.hash) {
      window.location.hash = "#/";
    }
  });
</script>

<main class="main-content">
  <Router {routes} />
</main>

<BottomNav />
