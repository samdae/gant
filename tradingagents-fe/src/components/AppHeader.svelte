<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    { label: "SCHEDULE", route: "/schedules" },
    { label: "LIVE", route: "/live" },
    { label: "DASHBOARD", route: "/" },
    { label: "POSITION", route: "/positions" },
    { label: "SEARCH", route: "/search" },
  ];

  let currentBaseRoute = "/";

  const normalizeRoute = (value: string) => {
    const cleaned = value.split("?")[0].replace(/^#/, "");
    if (!cleaned) return "/";
    return cleaned.startsWith("/") ? cleaned : `/${cleaned}`;
  };

  const getBaseRoute = (value: string) => {
    const normalized = normalizeRoute(value);
    const parts = normalized.split("/");
    return parts.length > 1 && parts[1] ? `/${parts[1]}` : "/";
  };

  const getCurrentBaseRoute = (value: string) => {
    const fallback = typeof window !== "undefined" ? window.location.hash : "#/";
    return getBaseRoute(value || fallback || "#/");
  };

  $: currentBaseRoute = getCurrentBaseRoute($location);
  const isActive = (route: string) => currentBaseRoute === route;
</script>

<header class="app-header">
  <a href="#/" class="logo" use:link>GANT</a>

  <nav class="nav-desktop">
    {#each navItems as item}
      <a
        href={`#${item.route}`}
        class={`nav-link ${item.route === "/" ? "is-home" : ""} ${isActive(item.route) ? "active" : ""}`}
        data-route={item.route}
        use:link
      >
        {item.label}
      </a>
    {/each}
  </nav>
</header>
