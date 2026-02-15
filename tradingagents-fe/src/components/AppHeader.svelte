<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    { label: "대시보드", route: "/" },
    { label: "포지션", route: "/positions" },
    { label: "스케줄", route: "/schedules" },
    { label: "라이브", route: "/live" },
    { label: "검색", route: "/search" },
  ];

  let currentRoute = "";

  $: currentRoute = $location;
  const isActive = (route: string) => currentRoute === route;
</script>

<header class="app-header">
  <a href="#/" class="logo" use:link>GANT</a>

  <nav class="nav-desktop">
    {#each navItems as item}
      <a
        href={`#${item.route}`}
        class={`nav-link ${isActive(item.route) ? "active" : ""}`}
        data-route={item.route}
        use:link
      >
        {item.label}
      </a>
    {/each}
  </nav>
</header>
