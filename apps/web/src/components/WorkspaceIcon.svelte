<script lang="ts">
  export let name: string;
  export let size = 19;
  const paths: Record<string, string> = {
    research: "M3 4h7l2 2h9v14h-9l-2-2H3z M7 9h3m-3 4h5",
    results: "M4 4v16h16 M8 16v-4m5 4V7m5 9v-6",
    observe:
      "M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z M14.5 12a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0",
    reports: "M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8m-8 4h6",
    reflections:
      "M12 3l8 3v6c0 4-4 7.5-8 9-4-1.5-8-5-8-9V6z M8.5 12l2.5 2.5 4.5-5",
    retrospective: "M4 8a8.5 8.5 0 1 1-.5 7 M3 4v5h5 M12 7v5l3 2",
    dashboard: "M3 4h8v7H3z M14 4h7v4h-7z M3 14h8v6H3z M14 11h7v9h-7z",
    portfolio: "M3 7h18v13H3z M8 7V4h8v3 M3 12a24 24 0 0 0 18 0 M11 13h2v2h-2z",
    positions: "M3 8l9-5 9 5-9 5z M3 12l9 5 9-5 M3 16l9 5 9-5",
    schedules: "M4 6h16v15H4z M8 3v5m8-5v5 M4 11h16m-12 4h4",
    live: "M2 12h5l3-7 4 14 3-7h5",
    about: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v5m0-9v.2",
    auth: "M5 10h14v11H5z M8 10V7a4 4 0 0 1 8 0v3 M12 14v3",
    menu: "M4 6h16M4 12h16M4 18h16",
    close: "M6 6l12 12M6 18L18 6",
    chevron: "M9 6l6 6-6 6",
    globe:
      "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M3 12h18 M12 3a16 16 0 0 0 0 18 16 16 0 0 0 0-18",
  };
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.65"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"><path d={paths[name]} /></svg
>
