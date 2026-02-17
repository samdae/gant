<script lang="ts">
  import { params } from "svelte-spa-router";
  import { fetchScheduleCycles, fetchScheduleCycleEvents } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";

  type ScheduleCycle = {
    id: number;
    ticker: string;
    interval_days: number;
    scheduled_cycle: number;
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

  const loadCycles = async (t: string) => {
    loading = true;
    cycleError = "";
    try {
      const response = (await fetchScheduleCycles(t, 20)) as ScheduleCycle[];
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
      cycleError = formatErrorMessage(err, "회차를 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const loadEvents = async () => {
    if (!selectedCycleId || !ticker) {
      events = [];
      stepStates = {};
      return;
    }
    loadingEvents = true;
    eventsError = "";
    try {
      const response = (await fetchScheduleCycleEvents(
        ticker,
        Number(selectedCycleId),
        200,
      )) as ScheduleEvent[];
      seedEvents(response || []);
    } catch (err) {
      eventsError = formatErrorMessage(err, "회차 이벤트를 불러오지 못했습니다.");
      events = [];
      stepStates = {};
    } finally {
      loadingEvents = false;
    }
  };

  const handleCycleChange = async (event: Event) => {
    const target = event.currentTarget as HTMLSelectElement;
    selectedCycleId = target.value;
    await loadEvents();
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadCycles(ticker);
  }

</script>

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
            <label class="form-label">
              회차
              <select class="select" value={selectedCycleId} on:change={handleCycleChange}>
                {#each cycles as cycle}
                  <option value={String(cycle.id)}>
                    {cycle.scheduled_cycle} 회차 · {formatDateTime(cycle.created_at)}
                  </option>
                {/each}
              </select>
            </label>
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
