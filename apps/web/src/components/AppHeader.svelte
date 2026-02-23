<script lang="ts">
  import { link, location } from "svelte-spa-router";
  import { currencyFilter, type CurrencyFilter } from "../stores/currency";

  const navItems = [
    { label: "예약", route: "/schedules" },
    { label: "실시간", route: "/live" },
    { label: "홈", route: "/" },
    { label: "투자", route: "/positions" },
    { label: "회고", route: "/reflections" },
  ];

  const currencies: CurrencyFilter[] = ["ALL", "KRW", "USD"];

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

  const setCurrency = (c: CurrencyFilter) => { currencyFilter.set(c); };
</script>

<header class="app-header">
  <a href="#/" class="logo" use:link>GANT</a>

  <div class="currency-selector">
    {#each currencies as c}
      <button
        class="currency-btn"
        class:active={$currencyFilter === c}
        on:click={() => setCurrency(c)}
      >{c}</button>
    {/each}
  </div>

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

<style>
  .currency-selector {
    display: flex;
    gap: 2px;
    background: var(--surface-2, #1a1a2e);
    border-radius: 6px;
    padding: 2px;
  }
  .currency-btn {
    padding: 4px 10px;
    font-size: 0.7rem;
    font-weight: 600;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    background: transparent;
    color: var(--text-muted, #8892b0);
    transition: all 0.15s ease;
  }
  .currency-btn.active {
    background: var(--accent, #64ffda);
    color: var(--surface-1, #0a0a1a);
  }
</style>
