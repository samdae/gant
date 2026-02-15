<script lang="ts">
  import { onMount } from "svelte";
  import {
    createSchedule,
    deleteSchedule,
    fetchQueue,
    fetchScheduleCycles,
    fetchSchedules,
  } from "../lib/api/endpoints";
  import { formatDateTime, formatAgo } from "../lib/utils/format";

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
  let formInterval = 4;
  let formError = "";
  let submitting = false;

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
      error = err instanceof Error ? err.message : "스케줄을 불러오지 못했습니다.";
    } finally {
      loading = false;
    }
  };

  const openAdd = () => {
    formTicker = "";
    formInterval = 4;
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
      formError = "티커는 영문 대문자 1~10자여야 합니다.";
      return null;
    }
    if (!Number.isInteger(formInterval) || formInterval < 1 || formInterval > 365) {
      formError = "주기는 1~365 사이 정수여야 합니다.";
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
      formError = err instanceof Error ? err.message : "생성 실패";
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
      error = err instanceof Error ? err.message : "삭제 실패";
    } finally {
      submitting = false;
    }
  };

  const statusBadge = (ticker: string) => {
    if (queue.running === ticker) return { label: "실행 중", className: "badge badge-info" };
    if (queue.pending.includes(ticker)) return { label: "대기", className: "badge badge-warn" };
    return { label: "활성", className: "badge badge-gain" };
  };

  onMount(() => {
    loadSchedules();
  });
</script>

<section class="page" id="page-schedules">
  <div class="page-container">
    <div class="page-header">
      <h2>스케줄</h2>
      <button class="btn btn-primary" id="addScheduleBtn" on:click={openAdd}>+ 추가</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card" style="padding:16px">{error}</div>
    {:else if schedules.length === 0}
      <div class="card" style="padding:16px">등록된 스케줄이 없습니다.</div>
    {:else}
      <div class="schedule-list">
        {#each schedules as schedule}
          {@const status = statusBadge(schedule.ticker)}
          <div class="card schedule-card">
            <div class="schedule-top">
              <span class="ticker-badge">{schedule.ticker}</span>
              <span class={status.className}>{status.label}</span>
              <span class="interval-label">{schedule.interval_days}일</span>
            </div>
            <div class="schedule-details">
              <span>{schedule.interval_days}일마다</span>
              <span>다음 실행: {formatDateTime(schedule.next_run_time)}</span>
              {#if cycles[schedule.ticker]}
                <span>
                  마지막 실행: {formatAgo(cycles[schedule.ticker]?.created_at)} · 사이클
                  #{cycles[schedule.ticker]?.scheduled_cycle}
                </span>
              {:else}
                <span>마지막 실행: -</span>
              {/if}
            </div>
            <button class="btn-icon btn-danger schedule-delete" title="삭제" on:click={() => openDelete(schedule.ticker)}>&times;</button>
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
        <h3>스케줄 추가</h3>
        <button class="modal-close" on:click={() => (showAdd = false)}>&times;</button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          티커
          <input type="text" class="input" placeholder="예: AAPL" bind:value={formTicker} />
        </label>
        <label class="form-label">
          주기(일)
          <input type="number" class="input" min="1" max="365" bind:value={formInterval} />
        </label>
        {#if formError}
          <p class="text-loss" style="font-size:0.8125rem">{formError}</p>
        {/if}
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" on:click={() => (showAdd = false)} disabled={submitting}>취소</button>
        <button class="btn btn-primary" on:click={submitAdd} disabled={submitting}>생성</button>
      </div>
    </div>
  </div>
{/if}

{#if showDelete}
  <div class="modal-overlay" id="deleteModal">
    <div class="modal modal-sm">
      <div class="modal-header">
        <h3>스케줄 삭제</h3>
        <button class="modal-close" on:click={() => (showDelete = false)}>&times;</button>
      </div>
      <div class="modal-body">
        <p><strong>{deleteTarget}</strong> 스케줄을 삭제할까요?</p>
        <p>큐에 있으면 함께 제거됩니다.</p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-ghost" on:click={() => (showDelete = false)} disabled={submitting}>취소</button>
        <button class="btn btn-danger" on:click={submitDelete} disabled={submitting}>삭제</button>
      </div>
    </div>
  </div>
{/if}
