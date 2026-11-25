<script lang="ts">
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import LabTimeline from "../components/LabTimeline.svelte";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import { onMount } from "svelte";
  import { fetchQueue, fetchLiveEvents, type LiveMessage as WsMessage } from "../lib/api/endpoints";
  import { connectLiveStream } from "../lib/ws/liveStream";
  import { tickerNames } from "../stores/tickerNames";

  type QueueStatus = {
    running: string | null;
    pending: string[];
  };

  let queue: QueueStatus = { running: null, pending: [] };
  let messages: WsMessage[] = [];
  let queueSeen = false;
  let queueFailed = false;
  let checkedAt = "";
  let ws: WebSocket | null = null;
  let connectedTicker: string | null = null;
  let stepStates: Record<string, WsMessage> = {};

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

  const getStatus = (msg?: WsMessage) => {
    if (!msg?.status) return "pending";
    if (msg.status === "completed") return "completed";
    if (msg.status === "running") return "running";
    if (msg.status === "error") return "error";
    return "pending";
  };

  const seedEvents = (events: WsMessage[]) => {
    messages = events.slice(0, 20);
    stepStates = {};
    for (const event of events) {
      if (event.agent && event.agent !== "system" && !stepStates[event.agent]) {
        stepStates[event.agent] = event;
      }
    }
  };

  const connect = (ticker: string) => {
    if (ws) ws.close();
    if (connectedTicker !== ticker) {
      messages = [];
      stepStates = {};
      connectedTicker = ticker;
    }
    const socket = connectLiveStream(ticker, (data) => {
      if (ws !== socket || !data || typeof data !== "object") return;
      const msg = data as WsMessage;
      messages = [msg, ...messages].slice(0, 20);
      if (msg.agent && msg.agent !== "system") {
        stepStates = { ...stepStates, [msg.agent]: msg };
      }
    });
    ws = socket;
    fetchLiveEvents(ticker).then((events) => {
      if (ws === socket) seedEvents([...messages, ...events]);
    }).catch(() => {});
  };

  onMount(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = (await fetchQueue()) as QueueStatus;
        if (stopped) return;
        queue = next;
        queueSeen = true;
        queueFailed = false;
        checkedAt = new Date().toISOString();
        if (!queue.running) {
          ws?.close();
          ws = null;
          connectedTicker = null;
        } else if (!isPublicViewer && (queue.running !== connectedTicker || !ws || ws.readyState >= WebSocket.CLOSING)) {
          connect(queue.running);
        }
      } catch {
        if (!stopped) queueFailed = true;
        // Retry on the next poll; keep the last confirmed queue state.
      } finally {
        if (!stopped) timer = setTimeout(poll, 5000);
      }
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      ws?.close();
      ws = null;
    };
  });

</script>

{#if isForecastLab}
  <section class="op-page">
    <header class="op-title">
      <div>
        <h1>실시간 실행</h1>
        <p>{isPublicViewer ? "가상매매 분석의 현재 실행 종목과 대기열입니다." : "가상매매 분석의 실행 종목과 단계별 진행 상황입니다."}</p>
      </div>
      <a class="op-link" href="#/schedules">분석 예약 보기 →</a>
    </header>
    {#if queueFailed}<p role="alert" class="op-error">
        대기열을 갱신하지 못했습니다. {queueSeen
          ? "마지막 확인 상태를 표시합니다."
          : "다시 연결하고 있습니다."}
      </p>{/if}
    {#if queueSeen && !queue.running && !queue.pending.length}
      <section class="op-panel"><h2>실행 중인 분석 없음</h2><p class="op-hint">최근 확인 {formatStepTime(checkedAt)} · 대기 중인 종목이 없습니다.</p></section>
    {:else}
    <div class="op-summary">
      <div>
        <span>현재 실행</span>
        {#if queue.running}<InstrumentLabel ticker={queue.running} />
        {:else}<strong>{queueSeen ? "실행 없음" : "확인 중"}</strong>{/if}
      </div>
      <div>
        <span>다음 대기 종목</span>
        {#if queue.pending[0]}<InstrumentLabel ticker={queue.pending[0]} />
        {:else}<strong>{queueSeen ? "대기 없음" : "확인 중"}</strong>{/if}
      </div>
      <div><span>최근 확인 · 현지 시각</span><strong>{formatStepTime(checkedAt)}</strong></div>
    </div>
    {/if}
    {#if queue.pending.length}<section class="op-panel">
        <h2>실행 대기열</h2>
        <ol class="op-pending">
          {#each queue.pending as symbol}<li><InstrumentLabel ticker={symbol} /></li>{/each}
        </ol>
      </section>{/if}
    {#if !isPublicViewer && (queue.running || messages.length)}
      {#if !queue.running}<p class="op-hint">가장 최근에 수신한 실행 기록입니다.</p>{/if}
      <LabTimeline groups={phaseGroups} states={stepStates} events={messages} />
    {:else if !isPublicViewer && queueSeen && queue.pending.length}<section class="op-panel">
        <h2>단계별 진행</h2>
        <p>분석이 시작되면 단계와 이벤트 시각을 표시합니다.</p>
      </section>{/if}
  </section>
{:else}
<section class="page" id="page-live">
  <div class="page-container">
    <div class="page-header">
      <h2>{isForecastLab ? "실시간 실행" : "실시간"}</h2>
    </div>

    <div class="live-layout">
      <div class="card live-queue">
        <div class="card-header">
          <h3>대기열</h3>
        </div>
        <div class="card-body">
          {#if queue.running}
            <div class="queue-item queue-running">
              <span class="queue-indicator"></span>
              <span class="queue-ticker">{queue.running}</span>
              <span class="badge badge-info" style="font-size:0.625rem;padding:2px 6px">
                <span class="spinner" style="width:8px;height:8px;margin-right:3px"></span>
                실행중
              </span>
            </div>
          {/if}
          {#if queue.pending.length === 0 && !queue.running}
            <div class="queue-item queue-pending">
              <span class="queue-indicator"></span>
              <span class="queue-ticker">대기 없음</span>
            </div>
          {:else}
            {#each queue.pending as item}
              <div class="queue-item queue-pending">
                <span class="queue-indicator"></span>
                <span class="queue-ticker">{item}</span>
              </div>
            {/each}
          {/if}
        </div>
      </div>

      <div class="card live-feed">
        <div class="card-header">
          <h3>에이전트 파이프라인</h3>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="live-dot"></span>
            <span style="font-size:0.75rem;color:var(--text-dim)">
              {queue.running ? `${queue.running} · 실시간` : "대기"}
            </span>
          </div>
        </div>
        <div class="card-body">
          {#if messages.length > 0}
            <div style="margin-bottom:12px;font-size:0.8125rem;color:var(--text-secondary)">
              최근: {messages[0].agent || ""} · {messages[0].message || ""}
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
