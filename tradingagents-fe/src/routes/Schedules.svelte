<script lang="ts">
  import { onMount } from "svelte";
  import {
    createSchedule,
    deleteSchedule,
    fetchQueue,
    fetchScheduleCycles,
    fetchSchedules,
  } from "../lib/api/endpoints";
  import { formatDateTime, formatAgo, formatErrorMessage } from "../lib/utils/format";

  type Schedule = {
    ticker: string;
    interval_days: number;
    next_run_time: string | null;
  };

  type Cycle = {
    id: number;
    scheduled_cycle: number;
    created_at: string;
    status: string;
  };

  type QueueStatus = {
    running: string | null;
    pending: string[];
  };

  let schedules: Schedule[] = [];
  let cycles: Record<string, Cycle | null> = {};
  let queue: QueueStatus = { running: null, pending: [] };
  let loading = true;
  let error = "";

  let showAdd = false;
  let showDelete = false;
  let deleteTarget: string | null = null;
  let formTicker = "";
  let formInterval = 1;
  let formError = "";
  let submitting = false;

  const goSchedule = (ticker: string) => {
    window.location.hash = `#/schedules/${ticker.toLowerCase()}`;
  };

  const loadSchedules = async () => {
    loading = true;
    error = "";
    try {
      const [scheduleRes, queueRes] = await Promise.all([
        fetchSchedules(),
        fetchQueue(),
      ]);
      schedules = (scheduleRes as Schedule[]) || [];
      queue = (queueRes as QueueStatus) || { running: null, pending: [] };

      const cycleMap: Record<string, Cycle | null> = {};
      for (const item of schedules) {
        const res = (await fetchScheduleCycles(item.ticker, 1)) as Cycle[];
        cycleMap[item.ticker] = res && res.length > 0 ? res[0] : null;
      }
      cycles = cycleMap;
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load schedules.");
    } finally {
      loading = false;
    }
  };

  const openAdd = () => {
    formTicker = "";
    formInterval = 1;
    formError = "";
    showAdd = true;
  };

  const openDelete = (ticker: string) => {
    deleteTarget = ticker;
    showDelete = true;
  };

  const validateForm = () => {
    const ticker = formTicker.trim().toUpperCase();
    if (!/^[A-Z]{1,10}$/.test(ticker)) {
      formError = "Ticker must be 1-10 uppercase letters.";
      return null;
    }
    if (!Number.isInteger(formInterval) || formInterval < 1 || formInterval > 365) {
      formError = "Interval must be an integer between 1 and 365.";
      return null;
    }
    return { ticker, interval_days: formInterval };
  };

  const submitAdd = async () => {
    const payload = validateForm();
    if (!payload) return;
    submitting = true;
    formError = "";
    try {
      await createSchedule(payload);
      showAdd = false;
      await loadSchedules();
    } catch (err) {
      formError = formatErrorMessage(err, "Failed to create schedule.");
    } finally {
      submitting = false;
    }
  };

  const submitDelete = async () => {
    if (!deleteTarget) return;
    submitting = true;
    try {
      await deleteSchedule(deleteTarget);
      showDelete = false;
      deleteTarget = null;
      await loadSchedules();
    } catch (err) {
      error = formatErrorMessage(err, "Failed to delete schedule.");
    } finally {
      submitting = false;
    }
  };

  const statusBadge = (ticker: string) => {
    if (queue.running === ticker) return { label: "Running", className: "badge badge-info" };
    if (queue.pending.includes(ticker)) return { label: "Queued", className: "badge badge-warn" };
    return { label: "Active", className: "badge badge-gain" };
  };

  onMount(() => {
    loadSchedules();
  });
</script>

<section class="page" id="page-schedules">
  <div class="page-container">
    <div class="page-header">
      <h2>Schedule</h2>
      <button class="btn btn-primary" id="addScheduleBtn" on:click={openAdd}>+ Add</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">Loading...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if schedules.length === 0}
      <div class="card" style="padding:16px">No schedules found.</div>
    {:else}
      <div class="schedule-list">
        {#each schedules as schedule}
          {@const status = statusBadge(schedule.ticker)}
          <div class="card schedule-card" on:click={() => goSchedule(schedule.ticker)}>
            <div class="schedule-top">
              <span class="ticker-badge">{schedule.ticker}</span>
              <span class={status.className}>{status.label}</span>
              <span class="interval-label">{schedule.interval_days} days</span>
            </div>
            <div class="schedule-details">
              <span>Every {schedule.interval_days} day(s)</span>
              <span>Next run: {formatDateTime(schedule.next_run_time)}</span>
              {#if cycles[schedule.ticker]}
                <span>
                  Last run: {formatAgo(cycles[schedule.ticker]?.created_at)} · Cycle
                  #{cycles[schedule.ticker]?.scheduled_cycle}
                </span>
              {:else}
                <span>Last run: -</span>
              {/if}
            </div>
            <button
              class="btn-icon btn-danger schedule-delete"
              title="Delete"
              on:click|stopPropagation={() => openDelete(schedule.ticker)}
            >&times;</button>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</section>

{#if showAdd}
  <div class="modal-overlay" id="addModal">
    <div class="modal">
    <div class="modal-header">
      <h3>Add Schedule</h3>
        <button class="modal-close" on:click={() => (showAdd = false)}>&times;</button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          Ticker
          <input type="text" class="input" placeholder="e.g. AAPL" bind:value={formTicker} />
        </label>
        <label class="form-label">
          Interval (days)
          <input type="number" class="input" min="1" max="365" bind:value={formInterval} />
        </label>
        {#if formError}
          <p class="text-loss" style="font-size:0.8125rem">{formError}</p>
        {/if}
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" on:click={() => (showAdd = false)} disabled={submitting}>Cancel</button>
        <button class="btn btn-primary" on:click={submitAdd} disabled={submitting}>Create</button>
      </div>
    </div>
  </div>
{/if}

{#if showDelete}
  <div class="modal-overlay" id="deleteModal">
    <div class="modal modal-sm">
    <div class="modal-header">
      <h3>Delete Schedule</h3>
        <button class="modal-close" on:click={() => (showDelete = false)}>&times;</button>
      </div>
    <div class="modal-body">
      <p>Delete schedule for <strong>{deleteTarget}</strong>?</p>
      <p>If queued, it will be removed as well.</p>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" on:click={() => (showDelete = false)} disabled={submitting}>Cancel</button>
      <button class="btn btn-danger" on:click={submitDelete} disabled={submitting}>Delete</button>
    </div>
    </div>
  </div>
{/if}
