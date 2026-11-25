<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import { onMount } from "svelte";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { formatDateTime } from "../lib/utils/format";
  import DecisionBadge from "./DecisionBadge.svelte";

  export let ticker: string;
  type Round = {
    id: number;
    scheduled_cycle?: number;
    created_at: string;
    stored_decision_position?: string | null;
    decision_position?: string;
  };
  let rows: Round[] = [],
    loading = true,
    failed = false;
  async function load() {
    failed = false;
    loading = true;
    try {
      rows = (await fetchReportsByTicker(ticker, 20)) as Round[];
    } catch {
      failed = true;
    } finally {
      loading = false;
    }
  }
  onMount(() => {
    load();
  });
</script>

<div class="rounds">
  {#if loading}<p><PendingState label="회차 조회 중"/></p>
  {:else if failed}<p role="alert">
      회차를 불러오지 못했습니다. <button on:click={load}>다시 조회</button>
    </p>
  {:else}
    <p>최근 발행 회차 · {rows.length}건</p>
    {#each rows as row}
      <a
        href={"#/reports/" +
          encodeURIComponent(ticker.toLowerCase()) +
          "?report=" +
          row.id}
      >
        <strong
          >{row.scheduled_cycle
            ? row.scheduled_cycle + "회차"
            : "리포트 #" + row.id}</strong
        >
        <time>{formatDateTime(row.created_at)}</time>
        <DecisionBadge
          value={(row.stored_decision_position === undefined
            ? row.decision_position
            : row.stored_decision_position) || ""}
        />
      </a>
    {/each}
  {/if}
</div>

<style>
  .rounds {
    padding: 0.5rem 1rem;
    background: var(--fl-surface-subtle, #27282b);
    border-block: 1px solid var(--fl-line, #3b3d41);
  }
  p {
    margin: 0.45rem 0;
    color: var(--fl-muted, #b5b4ad);
    font-size: 0.82rem;
  }
  a {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
    color: var(--fl-ink, #f4f2e9);
    text-decoration: none;
    border-top: 1px solid var(--fl-line, #3b3d41);
    padding: 0.7rem 0;
  }
  time {
    margin-right: auto;
    color: var(--fl-muted, #b5b4ad);
    font-size: 0.85rem;
  }
  a:hover strong,
  a:focus-visible strong {
    color: var(--fl-accent, #d5f65e);
    text-decoration: underline;
  }
</style>
