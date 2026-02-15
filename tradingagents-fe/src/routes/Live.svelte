<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { fetchQueue, fetchLiveEvents } from "../lib/api/endpoints";
  import { connectLiveStream } from "../lib/ws/liveStream";

  type QueueStatus = {
    running: string | null;
    pending: string[];
  };

  type WsMessage = {
    agent?: string;
    status?: string;
    message?: string;
    step?: number;
    phase?: string;
    total_steps?: number;
    timestamp?: string;
  };

  let queue: QueueStatus = { running: null, pending: [] };
  let messages: WsMessage[] = [];
  let ws: WebSocket | null = null;
  let connectedTicker: string | null = null;
  let stepStates: Record<string, WsMessage> = {};

  const phaseLabels: Record<string, string> = {
    "Data Collection": "1단계 — 데이터 수집",
    "Investment Debate": "2단계 — 투자 토론",
    "Trade Decision": "3단계 — 매매 결정",
    "Risk Assessment": "4단계 — 리스크 평가",
    Execution: "5단계 — 실행",
  };

  const agentSteps = [
    { step: 1, agent: "Market Analyst", label: "시장 분석가", phase: "Data Collection" },
    { step: 2, agent: "Social Analyst", label: "소셜 분석가", phase: "Data Collection" },
    { step: 3, agent: "News Analyst", label: "뉴스 분석가", phase: "Data Collection" },
    { step: 4, agent: "Fundamentals Analyst", label: "펀더멘털 분석가", phase: "Data Collection" },
    { step: 5, agent: "Bull Researcher", label: "강세 연구원", phase: "Investment Debate" },
    { step: 6, agent: "Bear Researcher", label: "약세 연구원", phase: "Investment Debate" },
    { step: 7, agent: "Research Manager", label: "리서치 매니저", phase: "Investment Debate" },
    { step: 8, agent: "Trader", label: "트레이더 에이전트", phase: "Trade Decision" },
    { step: 9, agent: "Aggressive Analyst", label: "공격적 리스크", phase: "Risk Assessment" },
    { step: 10, agent: "Neutral Analyst", label: "중립 리스크", phase: "Risk Assessment" },
    { step: 11, agent: "Conservative Analyst", label: "보수적 리스크", phase: "Risk Assessment" },
    { step: 12, agent: "Risk Judge", label: "리스크 매니저", phase: "Risk Assessment" },
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

  const loadQueue = async () => {
    try {
      queue = (await fetchQueue()) as QueueStatus;
    } catch {
      queue = { running: null, pending: [] };
    }
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
    fetchLiveEvents(ticker)
      .then((events: WsMessage[]) => seedEvents(events))
      .catch(() => {
        messages = [];
        stepStates = {};
      });
    ws = connectLiveStream(ticker, (data) => {
      const msg = data as WsMessage;
      messages = [msg, ...messages].slice(0, 20);
      if (msg.agent && msg.agent !== "system") {
        stepStates = { ...stepStates, [msg.agent]: msg };
      }
    });
  };

  onMount(async () => {
    await loadQueue();
    if (queue.running) {
      connect(queue.running);
    }
  });

  onDestroy(() => {
    if (ws) ws.close();
  });
</script>

<section class="page" id="page-live">
  <div class="page-container">
    <div class="page-header">
      <h2>실시간 분석</h2>
      <span class="badge badge-info">
        <span class="spinner" style="width:10px;height:10px;margin-right:4px"></span>
        {queue.running ? `${queue.running} 분석 중` : "대기 중"}
      </span>
    </div>

    <div class="live-layout">
      <div class="card live-queue">
        <div class="card-header">
          <h3>큐</h3>
        </div>
        <div class="card-body">
          {#if queue.running}
            <div class="queue-item queue-running">
              <span class="queue-indicator"></span>
              <span class="queue-ticker">{queue.running}</span>
              <span class="badge badge-info" style="font-size:0.625rem;padding:2px 6px">실행 중</span>
            </div>
          {/if}
          {#if queue.pending.length === 0}
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
              {queue.running ? `${queue.running} · 라이브` : "대기 중"}
            </span>
          </div>
        </div>
        <div class="card-body">
          {#if messages.length > 0}
            <div style="margin-bottom:12px;font-size:0.8125rem;color:var(--text-secondary)">
              최신: {messages[0].agent || ""} · {messages[0].message || ""}
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
                      {state?.message ? state.message : "대기 중"}
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
