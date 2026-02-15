<script lang="ts">
  import { link, location } from "svelte-spa-router";

  const navItems = [
    { label: "홈", route: "/" },
    { label: "포지션", route: "/positions" },
    { label: "스케줄", route: "/schedules" },
    { label: "라이브", route: "/live" },
    { label: "검색", route: "/search" },
  ];

  let currentRoute = "";

  $: currentRoute = $location;
  const isActive = (route: string) => currentRoute === route;
</script>

<nav class="bottom-nav" id="bottomNav">
  {#each navItems as item}
    <a
      href={`#${item.route}`}
      class={`bottom-nav-item ${isActive(item.route) ? "active" : ""}`}
      data-route={item.route}
      use:link
    >
      <span>{item.label}</span>
    </a>
  {/each}
</nav>
