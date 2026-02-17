<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    {
      label: "예약",
      route: "/schedules",
      icon: "M6 4v3M18 4v3M4 9h16M6 9h12v9a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9z",
    },
    {
      label: "실시간",
      route: "/live",
      icon: "M3 14l4-4 4 4 6-6 4 4",
    },
    {
      label: "홈",
      route: "/",
      icon: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
    },
    {
      label: "투자",
      route: "/positions",
      icon: "M4 8h16l2 3v7a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-7l2-3zm4-3h8a2 2 0 0 1 2 2v1H6V7a2 2 0 0 1 2-2z",
    },
    {
      label: "AI분석",
      route: "/reports",
      icon: "M7 4h7l4 4v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm6 1v4h4",
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
