<script lang="ts">
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import "../components/labOperations.css";
  import { operationTime, operationState } from "../lib/utils/operations";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import { onMount } from "svelte";
  import {
    createSchedule,
    deleteSchedule,
    fetchQueue,
    fetchSchedules,
    searchTickers,
  } from "../lib/api/endpoints";
  import { formatDateTime, formatAgo, formatErrorMessage } from "../lib/utils/format";
  import { instrumentName, instrumentText, tickerNames, setTickerName, loadTickerNames } from "../stores/tickerNames";
  import { currencyFilter, matchesCurrency } from "../stores/currency";

  type Schedule = {
    ticker: string;
    interval_days: number;
    next_run_time: string | null;
    latest_cycle?: Cycle | null;
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
    if (!formDisplayName) formDisplayName = isForecastLab ? instrumentName(item.symbol, $tickerNames, item.name) : item.name;
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

  const formatNextRun = (iso: string | null): string => {
    if (!iso) return "";
    const d = new Date(iso);
    const h = d.getHours().toString().padStart(2, "0");
    const m = d.getMinutes().toString().padStart(2, "0");
    const mon = d.getMonth() + 1;
    const day = d.getDate();
    return `${mon}/${day} ${h}:${m}`;
  };

  onMount(() => {
    loadSchedules();
  });

  let search = "";
  $: filteredSchedules = schedules.filter((s) => matchesCurrency(s.ticker, $currencyFilter)
    && (!isForecastLab || (s.ticker + " " + ($tickerNames[s.ticker] || "")).toLowerCase().includes(search.trim().toLowerCase())));
</script>

{#if isForecastLab}
  <section class="op-page">
    <header class="op-title">
      <div>
        <h1>분석 예약</h1>
        <p>종목별 분석 주기와 최근 실행 회차를 확인합니다.</p>
      </div>
      {#if !isPublicViewer}<button class="op-primary" id="addScheduleBtn" on:click={openAdd}>예약 추가</button>{/if}
    </header>
    {#if error}<p class="op-error" role="alert">
        {error} <button on:click={loadSchedules}>다시 조회</button>
      </p>{/if}
    <div class="op-summary">
      <div><span>등록 종목</span><strong>{loading || error ? "—" : schedules.length}</strong></div>
      <div>
        <span>현재 실행</span>
        {#if queue.running}<InstrumentLabel ticker={queue.running} />
        {:else}<strong>{loading || error ? "—" : "실행 없음"}</strong>{/if}
      </div>
      <div>
        <span>대기열</span><strong>{loading || error ? "—" : queue.pending.length + "종목"}</strong>
      </div>
    </div>
    <section class="op-panel op-schedule-panel">
      <header class="op-toolbar">
        <div>
          <h2>종목별 일정</h2>
          <small>시각은 한국 시간 기준입니다.</small>
        </div>
        <label
          >종목 검색 <input
            type="search"
            bind:value={search}
            placeholder="티커 또는 표시 이름"
          /></label
        >
      </header>
      {#if loading}<p class="op-hint" role="status">예약을 불러오는 중입니다.</p>
      {:else if !error && !filteredSchedules.length}
        <div class="folio-empty">
          <h3>{schedules.length ? "검색 결과 없음" : "등록된 일정 없음"}</h3>
          {#if schedules.length}<button class="btn btn-secondary" on:click={() => search = ""}>검색어 지우기</button>
          {:else}<p>종목과 실행 주기가 등록되면 다음 실행 시각을 확인할 수 있습니다.</p>{/if}
        </div>
      {:else if filteredSchedules.length}
        <div class="op-schedules" role="list">
          <div class="op-grid-row op-colhead" aria-hidden="true">
            <span>종목 / 주기</span><span>상태</span><span>다음 실행</span><span>최근 회차</span>{#if !isPublicViewer}<span>관리</span>{/if}
          </div>
          {#each filteredSchedules as schedule}
            {@const badge = statusBadge(schedule.ticker)}
            {@const cycle = schedule.latest_cycle}
            <div class="op-grid-row" role="listitem">
              <a href={`#/schedules/${encodeURIComponent(schedule.ticker.toLowerCase())}`}>
                <InstrumentLabel ticker={schedule.ticker} />
                <small>{formatInterval(schedule.interval_days)}</small>
              </a>
              <span class="op-state" data-state={queue.running === schedule.ticker ? "running" : ""}
                >{badge.label}</span
              >
              <div>
                <span class="op-mobile-label">다음 실행</span><time
                  >{operationTime(schedule.next_run_time)}</time
                >
              </div>
              <div>
                <span class="op-mobile-label">최근 회차</span>{#if cycle}<b
                    >{cycle.scheduled_cycle}회 · {operationState(cycle.status)}</b
                  ><small>{operationTime(cycle.created_at)}</small>{:else}<span>기록 없음</span>{/if}
              </div>
              {#if !isPublicViewer}<button
                class="op-cancel"
                aria-label={instrumentText(schedule.ticker, $tickerNames) + " 예약 삭제"}
                title={instrumentText(schedule.ticker, $tickerNames) + " 예약 삭제"}
                on:click={() => openDelete(schedule.ticker)}
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none"
                  stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5m4-5v5" />
                </svg>
              </button>{/if}
            </div>
          {/each}
        </div>{/if}
    </section>
    <nav class="op-related">
      <a href="#/live">실시간 대기열 →</a><a href="#/observe">예측 연구 관찰 종목 →</a>
    </nav>
  </section>
{:else}
<section class="page" id="page-schedules">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? "분석 예약" : "예약"}</h2>
      <button class="btn btn-primary" id="addScheduleBtn" on:click={openAdd}>+ 추가</button>
    </div>
    {#if isForecastLab}
      <p class="scope-note">이 목록은 콘솔 전용 DB의 에이전트 실행 일정입니다. <a href="#/observe">예측 연구 관찰 종목 보기</a></p>
    {/if}

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if schedules.length === 0}
      <div class="card" style="padding:16px">예약이 없습니다.</div>
    {:else}
      <div class="schedule-list list-grid">
        {#if isForecastLab}
          <header class="desk-toolbar">
            <div class="desk-heading"><h3>예약된 종목</h3><span>{filteredSchedules.length}종목</span></div>
            <label class="desk-search"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/></svg><input type="search" bind:value={search} aria-label="예약 종목 검색" placeholder="예약 종목 검색" /></label>
          </header>
          <div class="desk-schedule-head" aria-hidden="true"><span>종목</span><span>상태</span><span>실행 일정</span></div>
          {#if filteredSchedules.length === 0}<div class="desk-state">조건에 맞는 예약이 없습니다.</div>{/if}
        {/if}
        {#each filteredSchedules as schedule}
          {@const status = statusBadge(schedule.ticker)}
          <a
            class={`schedule-card list-row ${status.label === "실행중" ? "schedule-running" : status.label === "대기중" ? "schedule-queued" : "schedule-active"}`}
            href={`#/schedules/${encodeURIComponent(schedule.ticker.toLowerCase())}`}
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
                e.preventDefault();
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
              <span>{formatInterval(schedule.interval_days)}{#if schedule.next_run_time} · {formatNextRun(schedule.next_run_time)} 예정{/if}</span>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</section>

{/if}
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
                    {#if isForecastLab}
                      <InstrumentLabel ticker={item.symbol} name={item.name} />
                    {:else}
                      <span class="ac-symbol">{item.symbol}</span>
                      <span class="ac-name">{item.name}</span>
                    {/if}
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
      <p>{#if isForecastLab && deleteTarget}<InstrumentLabel ticker={deleteTarget} inline />
         {:else}<strong>{deleteTarget}</strong>{/if} 예약을 삭제할까요?</p>
      <p>대기중이면 함께 제거됩니다.</p>
      {#if isForecastLab && error}<p role="alert" class="op-error">{error}</p>{/if}
    </div>
    <div class="modal-footer">
      <button class="btn btn-ghost" on:click={() => (showDelete = false)} disabled={submitting}>취소</button>
      <button class="btn btn-danger" on:click={submitDelete} disabled={submitting}>삭제</button>
    </div>
    </div>
  </div>
{/if}
