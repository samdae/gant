<script lang="ts">
  import { onMount } from "svelte";
  import {
    createSchedule,
    deleteSchedule,
    fetchQueue,
    fetchScheduleCycles,
    fetchSchedules,
    searchTickers,
  } from "../lib/api/endpoints";
  import { formatDateTime, formatAgo, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames, setTickerName, loadTickerNames } from "../stores/tickerNames";

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

  type TickerResult = {
    symbol: string;
    name: string;
    exchange: string;
    type: string;
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
  let formDisplayName = "";
  let formError = "";
  let submitting = false;

  // Autocomplete state
  let suggestions: TickerResult[] = [];
  let showSuggestions = false;
  let searchTimeout: ReturnType<typeof setTimeout> | null = null;
  let selectedIndex = -1;

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

      const cyclePairs = await Promise.all(
        schedules.map(async (item) => {
          try {
            const res = (await fetchScheduleCycles(item.ticker, 1)) as Cycle[];
            return [item.ticker, res && res.length > 0 ? res[0] : null] as const;
          } catch {
            return [item.ticker, null] as const;
          }
        })
      );
      const cycleMap: Record<string, Cycle | null> = {};
      for (const [ticker, cycle] of cyclePairs) {
        cycleMap[ticker] = cycle;
      }
      cycles = cycleMap;
    } catch (err) {
      error = formatErrorMessage(err, "예약을 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const openAdd = () => {
    formTicker = "";
    formInterval = 1;
    formDisplayName = "";
    formError = "";
    suggestions = [];
    showSuggestions = false;
    selectedIndex = -1;
    showAdd = true;
  };

  const openDelete = (ticker: string) => {
    deleteTarget = ticker;
    showDelete = true;
  };

  const onTickerInput = () => {
    const q = formTicker.trim();
    if (searchTimeout) clearTimeout(searchTimeout);
    selectedIndex = -1;
    if (q.length < 1) {
      suggestions = [];
      showSuggestions = false;
      return;
    }
    searchTimeout = setTimeout(async () => {
      try {
        suggestions = (await searchTickers(q)) as TickerResult[];
        showSuggestions = suggestions.length > 0;
      } catch {
        suggestions = [];
        showSuggestions = false;
      }
    }, 250);
  };

  const selectTicker = (item: TickerResult) => {
    formTicker = item.symbol;
    if (!formDisplayName) formDisplayName = item.name;
    suggestions = [];
    showSuggestions = false;
    selectedIndex = -1;
  };

  const onTickerKeydown = (e: KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, suggestions.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
    } else if (e.key === "Enter" && selectedIndex >= 0) {
      e.preventDefault();
      selectTicker(suggestions[selectedIndex]);
    } else if (e.key === "Escape") {
      showSuggestions = false;
    }
  };

  const onTickerBlur = () => {
    // Delay to allow click on suggestion
    setTimeout(() => {
      showSuggestions = false;
    }, 200);
  };

  const validateForm = () => {
    const ticker = formTicker.trim().toUpperCase();
    if (!/^[A-Z0-9.\-]{1,15}$/.test(ticker)) {
      formError = "유효하지 않은 티커입니다.";
      return null;
    }
    if (!Number.isInteger(formInterval) || formInterval < 1 || formInterval > 365) {
      formError = "주기는 1~365 사이의 정수여야 합니다.";
      return null;
    }
    const dn = formDisplayName.trim() || undefined;
    return { ticker, interval_days: formInterval, display_name: dn };
  };

  const submitAdd = async () => {
    const payload = validateForm();
    if (!payload) return;
    submitting = true;
    formError = "";
    try {
      await createSchedule(payload);
      if (payload.display_name) setTickerName(payload.ticker, payload.display_name);
      showAdd = false;
      await loadSchedules();
      loadTickerNames();
    } catch (err) {
      formError = formatErrorMessage(err, "예약을 생성하지 못했습니다.");
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
      error = formatErrorMessage(err, "예약을 삭제하지 못했습니다.");
    } finally {
      submitting = false;
    }
  };

  const statusBadge = (ticker: string) => {
    if (queue.running === ticker) return { label: "실행중", className: "badge badge-gain" };
    if (queue.pending.includes(ticker)) return { label: "대기중", className: "badge badge-loss" };
    return { label: "활성", className: "badge badge-muted" };
  };

  const formatInterval = (days: number) => (days === 1 ? "매일" : `${days}일마다`);

  onMount(() => {
    loadSchedules();
  });
</script>

<section class="page" id="page-schedules">
  <div class="page-container">
    <div class="page-header">
      <h2>예약</h2>
      <button class="btn btn-primary" id="addScheduleBtn" on:click={openAdd}>+ 추가</button>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if schedules.length === 0}
      <div class="card" style="padding:16px">예약이 없습니다.</div>
    {:else}
      <div class="schedule-list">
        {#each schedules as schedule}
          {@const status = statusBadge(schedule.ticker)}
          <div
            class="card schedule-card"
            on:click={() => goSchedule(schedule.ticker)}
            on:touchstart|passive={(e) => {
              const t = e.currentTarget;
              t.dataset.sx = String(e.touches[0].clientX);
              t.dataset.sy = String(e.touches[0].clientY);
              t.style.transition = 'none';
            }}
            on:touchmove|passive={(e) => {
              const t = e.currentTarget;
              const sx = Number(t.dataset.sx);
              const sy = Number(t.dataset.sy);
              const dx = e.touches[0].clientX - sx;
              const dy = e.touches[0].clientY - sy;
              if (Math.abs(dx) > Math.abs(dy) && dx < 0) {
                t.style.transform = `translateX(${Math.max(dx, -120)}px)`;
                t.style.opacity = String(Math.max(1 + dx / 300, 0.5));
              }
            }}
            on:touchend={(e) => {
              const t = e.currentTarget;
              const sx = Number(t.dataset.sx);
              const dx = e.changedTouches[0].clientX - sx;
              t.style.transition = 'transform 0.25s ease, opacity 0.25s ease';
              t.style.transform = '';
              t.style.opacity = '';
              if (dx < -80) {
                openDelete(schedule.ticker);
              }
            }}
          >
            <div class="schedule-top">
              <div class="schedule-top-left">
                <span class="ticker-badge">{schedule.ticker}</span>
                {#if $tickerNames[schedule.ticker]}
                  <span class="ticker-tag">{$tickerNames[schedule.ticker]}</span>
                {/if}
              </div>
              <span class={status.className}>{status.label}</span>
            </div>
            <div class="schedule-details">
              <span>{formatInterval(schedule.interval_days)}</span>
              <span>다음 실행: {formatDateTime(schedule.next_run_time)}</span>
              {#if cycles[schedule.ticker]}
                <span>
                  최근 실행: {formatAgo(cycles[schedule.ticker]?.created_at)} ·
                  {cycles[schedule.ticker]?.scheduled_cycle} 회차
                </span>
              {:else}
                <span>최근 실행: -</span>
              {/if}
            </div>
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
      <h3>예약 추가</h3>
        <button class="modal-close" on:click={() => (showAdd = false)}>&times;</button>
      </div>
      <div class="modal-body">
        <label class="form-label">
          티커
          <div class="autocomplete-wrap">
            <input
              type="text"
              class="input"
            placeholder="티커 검색 (예: AAPL, TSLA)"
              bind:value={formTicker}
              on:input={onTickerInput}
              on:keydown={onTickerKeydown}
              on:blur={onTickerBlur}
              on:focus={() => { if (suggestions.length > 0) showSuggestions = true; }}
              autocomplete="off"
            />
            {#if showSuggestions}
              <div class="autocomplete-dropdown">
                {#each suggestions as item, i}
                  <button
                    class="autocomplete-item"
                    class:selected={i === selectedIndex}
                    on:mousedown|preventDefault={() => selectTicker(item)}
                  >
                    <span class="ac-symbol">{item.symbol}</span>
                    <span class="ac-name">{item.name}</span>
                    <span class="ac-exchange">{item.exchange}</span>
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        </label>
        <label class="form-label">
          표시 이름
          <input
            type="text"
            class="input"
            placeholder="예: 삼성전자, NVIDIA"
            bind:value={formDisplayName}
          />
        </label>
        <label class="form-label">
          주기 (일)
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
      <h3>예약 삭제</h3>
        <button class="modal-close" on:click={() => (showDelete = false)}>&times;</button>
      </div>
    <div class="modal-body">
      <p><strong>{deleteTarget}</strong> 예약을 삭제할까요?</p>
      <p>대기중이면 함께 제거됩니다.</p>
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" on:click={() => (showDelete = false)} disabled={submitting}>취소</button>
      <button class="btn btn-danger" on:click={submitDelete} disabled={submitting}>삭제</button>
    </div>
    </div>
  </div>
{/if}
