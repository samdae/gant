<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    {
      label: "SCHEDULE",
      route: "/schedules",
      icon: "M7 3v3M17 3v3M4 8h16M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8",
    },
    {
      label: "LIVE",
      route: "/live",
      icon: "M4 12h3l2-4 4 8 2-4h5",
    },
    {
      label: "DASHBOARD",
      route: "/",
      icon: "M3 11.5 12 4l9 7.5v7A1.5 1.5 0 0 1 19.5 20H14v-6h-4v6H4.5A1.5 1.5 0 0 1 3 18.5z",
    },
    {
      label: "POSITION",
      route: "/positions",
      icon: "M6 7h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2zm4-3h4a2 2 0 0 1 2 2v1H8V6a2 2 0 0 1 2-2z",
    },
    {
      label: "SEARCH",
      route: "/search",
      icon: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm8.5 15.5-3.5-3.5",
    },
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

<nav class="bottom-nav" id="bottomNav">
  {#each navItems as item}
    <a
      href={`#${item.route}`}
      class={`bottom-nav-item ${item.route === "/" ? "is-home" : ""} ${isActive(item.route) ? "active" : ""}`}
      data-route={item.route}
      use:link
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d={item.icon} fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>{item.label}</span>
    </a>
  {/each}
</nav>
