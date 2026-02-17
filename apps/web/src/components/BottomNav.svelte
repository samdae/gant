<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    {
      label: "예약",
      route: "/schedules",
      icon: "M7 3v2M17 3v2M4 8h16M5 8v11a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8M7 12h4M13 12h4M7 16h4M13 16h4",
    },
    {
      label: "실시간",
      route: "/live",
      icon: "M3 12h4l2-4 4 8 2-4h6",
    },
    {
      label: "홈",
      route: "/",
      icon: "M4 10l8-6 8 6v8a2 2 0 0 1-2 2h-4v-6H10v6H6a2 2 0 0 1-2-2z",
    },
    {
      label: "투자",
      route: "/positions",
      icon: "M4 18V6m0 12h16M8 14V9m4 5v-7m4 7V8",
    },
    {
      label: "AI분석",
      route: "/reports",
      icon: "M12 3v4m0 10v4m-9-9h4m10 0h4M7 7l2.5 2.5M14.5 14.5 17 17M7 17l2.5-2.5M14.5 9.5 17 7",
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
</script>

<nav class="bottom-nav" id="bottomNav">
  {#each navItems as item}
    <a
      href={`#${item.route}`}
      class={`bottom-nav-item ${item.route === "/" ? "is-home" : ""}`}
      class:active={currentBaseRoute === item.route}
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
