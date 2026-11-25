<script lang="ts">
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import LabTimeline from "../components/LabTimeline.svelte";
  import { operationTime, operationState } from "../lib/utils/operations";
  import { params } from "svelte-spa-router";
  import { fetchScheduleCycles, fetchScheduleCycleEvents } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import SelectMenu from "../components/SelectMenu.svelte";
  import { tickerNames } from "../stores/tickerNames";

  type ScheduleCycle = {
    id: number;
    ticker: string;
    interval_days: number;
    scheduled_cycle: number;
    status?: string;
    error_message?: string;
    created_at: string;
  };

  type ScheduleEvent = {
    agent?: string;
    status?: string;
    message?: string;
    step?: number;
    phase?: string;
    total_steps?: number;
    timestamp?: string;
  };

  let ticker = "";
  let cycles: ScheduleCycle[] = [];
  let selectedCycleId = "";
  let loading = true;
  let loadingEvents = false;
  let cycleError = "";
  let eventsError = "";
  let events: ScheduleEvent[] = [];
  let stepStates: Record<string, ScheduleEvent> = {};
  let cycleOptions: Array<{ value: string; label: string }> = [];

  const phaseLabels: Record<string, string> = {
    "Data Collection": "분석",
    "Investment Debate": "투자 토론",
    "Trade Decision": "매매 결정",
    "Risk Assessment": "리스크 토론",
    Execution: "실행",
  };

  const agentSteps = [
    { step: 1, agent: "Market Analyst", label: "시장 분석 에이전트", phase: "Data Collection" },
    { step: 2, agent: "Social Analyst", label: "소셜분석 에이전트", phase: "Data Collection" },
    { step: 3, agent: "News Analyst", label: "뉴스 분석 에이전트", phase: "Data Collection" },
    { step: 4, agent: "Fundamentals Analyst", label: "펀더멘털 분석 에이전트", phase: "Data Collection" },
    { step: 5, agent: "Bull Researcher", label: "강세 분석 에이전트", phase: "Investment Debate" },
    { step: 6, agent: "Bear Researcher", label: "약세 분석 에이전트", phase: "Investment Debate" },
    { step: 7, agent: "Research Manager", label: "심판 결론 에이전트", phase: "Investment Debate" },
    { step: 8, agent: "Trader", label: "트레이더 결정 에이전트", phase: "Trade Decision" },
    { step: 9, agent: "Aggressive Analyst", label: "공격적 분석 에이전트", phase: "Risk Assessment" },
    { step: 10, agent: "Neutral Analyst", label: "중립적 분석 에이전트", phase: "Risk Assessment" },
    { step: 11, agent: "Conservative Analyst", label: "보수적 분석 에이전트", phase: "Risk Assessment" },
    { step: 12, agent: "Risk Judge", label: "리스크 결론 에이전트", phase: "Risk Assessment" },
    { step: 13, agent: "Portfolio Agent", label: "포트폴리오 에이전트", phase: "Execution" },
  ];

  const formatInterval = (days?: number | null) => {
    if (!days) return "-";
    return days === 1 ? "매일" : `${days}일마다`;
  };

  const phaseGroups = [
    "Data Collection",
    "Investment Debate",
    "Trade Decision",
    "Risk Assessment",
    "Execution",
  ].map((phase) => ({
    key: phase,
    label: phaseLabels[phase],
    steps: agentSteps.filter((item) => item.phase === phase),
  }));

  const formatStepTime = (iso?: string) => {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const getStatus = (msg?: ScheduleEvent) => {
    if (!msg?.status) return "pending";
    if (msg.status === "completed") return "completed";
    if (msg.status === "running") return "running";
    if (msg.status === "error") return "error";
    return "pending";
  };

  const seedEvents = (items: ScheduleEvent[]) => {
    events = items.slice(0, 20);
    stepStates = {};
    for (const event of items) {
      if (event.agent && event.agent !== "system" && !stepStates[event.agent]) {
        stepStates[event.agent] = event;
      }
    }
  };

  const selectedCycle = () =>
    cycles.find((cycle) => String(cycle.id) === selectedCycleId) || null;

  $: cycleOptions = cycles.map((cycle) => ({
    value: String(cycle.id),
    label: `${cycle.scheduled_cycle} 회차 · ${formatDateTime(cycle.created_at)}`,
  }));

  const loadCycles = async (t: string) => {
    loading = true;
    cycleError = "";
    try {
      const response = (await fetchScheduleCycles(t, 20)) as ScheduleCycle[];
      if (t !== ticker) return;
      cycles = response || [];
      if (cycles.length > 0) {
        selectedCycleId = String(cycles[0].id);
        await loadEvents();
      } else {
        selectedCycleId = "";
        events = [];
        stepStates = {};
      }
    } catch (err) {
      if (t !== ticker) return;
      cycleError = formatErrorMessage(err, "회차를 불러오지 못했습니다.");
    } finally {
      if (t === ticker) loading = false;
    }
  };

  const loadEvents = async () => {
    if (isPublicViewer || !selectedCycleId || !ticker) {
      events = [];
      stepStates = {};
      return;
    }
    const cycleId = selectedCycleId;
    const eventTicker = ticker;
    loadingEvents = true;
    eventsError = "";
    try {
      const response = (await fetchScheduleCycleEvents(
        ticker,
        Number(selectedCycleId),
        200,
      )) as ScheduleEvent[];
      if (eventTicker === ticker && cycleId === selectedCycleId) seedEvents(response || []);
    } catch (err) {
      if (eventTicker !== ticker || cycleId !== selectedCycleId) return;
      eventsError = formatErrorMessage(err, "회차 이벤트를 불러오지 못했습니다.");
      events = [];
      stepStates = {};
    } finally {
      if (eventTicker === ticker && cycleId === selectedCycleId) loadingEvents = false;
    }
  };

  const handleCycleChange = async (value: string) => {
    selectedCycleId = value;
    await loadEvents();
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadCycles(ticker);
  }

</script>

{#if isForecastLab}
  <section class="op-page">
    <a class="op-link" href="#/schedules">← 분석 예약</a>
    <header class="op-title">
      <div>
        <h1><InstrumentLabel {ticker} /></h1>
        <p>최근 20개 분석 회차의 실행 기록입니다.</p>
      </div>

    </header>
    {#if loading}<p class="op-panel" role="status">회차를 불러오는 중입니다.</p>
    {:else if cycleError}<p class="op-error" role="alert">{cycleError}</p>
    {:else if !cycles.length}<section class="op-panel folio-empty"><h2>실행 회차 없음</h2><p>예약이 실행되면 여기에 회차별 시작 시각과 결과가 표시됩니다.</p><a href="#/live">실시간 실행 →</a></section>
    {:else}
      {@const cycle = cycles.find((c) => String(c.id) === selectedCycleId)}
      <section class="op-panel">
        <div class="op-toolbar">
          <h2>실행 회차</h2>
          <label
            >회차 선택 <select
              value={selectedCycleId}
              on:change={(e) => handleCycleChange(e.currentTarget.value)}
              >{#each cycles as item}<option value={String(item.id)}
                  >{item.scheduled_cycle}회 · {operationTime(item.created_at)}</option
                >{/each}</select
            ></label
          >
        </div>
        <div class="op-summary">
          <div><span>선택 회차</span><strong>{cycle?.scheduled_cycle}회</strong></div>
          <div><span>실행 상태</span><strong>{operationState(cycle?.status)}</strong></div>
          <div><span>등록 시각 · 한국</span><strong>{operationTime(cycle?.created_at)}</strong></div>
        </div>
        {#if !isPublicViewer && cycle?.error_message}<p class="op-error">{cycle.error_message}</p>{/if}
      </section>
      {#if isPublicViewer}<p class="op-hint">세부 실행 로그는 관리자 화면에서 확인할 수 있습니다.</p>
      {:else if loadingEvents}<p class="op-panel" role="status">이벤트를 불러오는 중입니다.</p>
      {:else if eventsError}<p class="op-error" role="alert">{eventsError}</p>
      {:else}<LabTimeline groups={phaseGroups} states={stepStates} {events} />{/if}
    {/if}
  </section>
{:else}
<section class="page" id="page-schedule-detail">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker}</h2>
    </div>

    <div class="live-layout">
      <div class="card live-queue">
        <div class="card-header">
          <h3>회차</h3>
        </div>
        <div class="card-body">
          {#if loading}
            <div class="empty-state">회차 불러오는 중...</div>
          {:else if cycleError}
            <div class="empty-state error-text">{cycleError}</div>
          {:else if cycles.length === 0}
            <div class="empty-state">회차가 없습니다.</div>
          {:else}
            <div class="form-label"><label for="cycle-select">회차</label>
            <SelectMenu id="cycle-select"
                value={selectedCycleId}
                options={cycleOptions}
                placeholder="회차 선택"
                on:change={(event) => handleCycleChange(event.detail)}
              />
            </div>
            {#if selectedCycle()}
              <div class="stat-row">
                <span class="stat-label">주기</span>
                <span class="stat-value">{formatInterval(selectedCycle()?.interval_days)}</span>
              </div>
              <div class="stat-row">
                <span class="stat-label">생성일</span>
                <span class="stat-value">{formatDateTime(selectedCycle()?.created_at)}</span>
              </div>
            {/if}
          {/if}
        </div>
      </div>

      <div class="card live-feed">
        <div class="card-header">
          <h3>에이전트 파이프라인</h3>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="live-dot"></span>
            <span style="font-size:0.75rem;color:var(--text-dim)">
              {selectedCycleId ? `${selectedCycle()?.scheduled_cycle || ""} 회차` : "대기"}
            </span>
          </div>
        </div>
        <div class="card-body">
          {#if loadingEvents}
            <div class="empty-state" style="margin-bottom:12px">이벤트 불러오는 중...</div>
          {:else if eventsError}
            <div class="empty-state error-text" style="margin-bottom:12px">{eventsError}</div>
          {:else if events.length === 0}
            <div class="empty-state" style="margin-bottom:12px">이 회차의 이벤트가 없습니다.</div>
          {:else}
            <div style="margin-bottom:12px;font-size:0.8125rem;color:var(--text-secondary)">
              최근: {events[0].agent || ""} · {events[0].message || ""}
            </div>
          {/if}
          {#each phaseGroups as group}
            <div class="phase-group">
              <div class="phase-label">{group.label}</div>
              <div class="agent-steps">
                {#each group.steps as step}
                  {@const state = stepStates[step.agent]}
                  {@const status = getStatus(state)}
                  <div class={`agent-step step-${status}`}>
                    <div class="step-header">
                      <span class="step-time">{formatStepTime(state?.timestamp)}</span>
                      <span class="step-name">{step.label}</span>
                      {#if status === "completed"}
                        <span class="step-check done">&#10003;</span>
                      {:else if status === "running"}
                        <span class="spinner"></span>
                      {:else if status === "error"}
                        <span class="step-check error">!</span>
                      {/if}
                    </div>
                    <div class="step-message">
                      {state?.message ? state.message : "대기"}
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
</section>

{/if}
