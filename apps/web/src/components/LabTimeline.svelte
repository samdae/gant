<script lang="ts">
  import "./labOperations.css";
  export let groups: {
    key: string;
    label: string;
    steps: { agent: string; label: string; step: number }[];
  }[];
  type Event = { agent?: string; status?: string; timestamp?: string; message?: string };
  export let states: Record<string, Event> = {};
  export let events: Event[] = [];
  const status = (s?: string) =>
    ({ completed: "완료", running: "실행 중", error: "오류", failed: "실패" })[s || ""] || "대기";
  const when = (s?: string) =>
    s && Number.isFinite(Date.parse(s))
      ? new Intl.DateTimeFormat("ko-KR", {
          timeZone: "Asia/Seoul",
          month: "numeric",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(new Date(s))
      : "—";
</script>

<section class="op-panel">
  <h2>단계별 진행</h2>
  {#each groups as group}
    <details
      class="op-stage"
      open={group.steps.some((step) => states[step.agent]?.status === "running")}
    >
      <summary
        ><strong>{group.label}</strong><span
          >{group.steps.filter((step) => states[step.agent]?.status === "completed").length} / {group
            .steps.length} 완료</span
        ></summary
      >
      <ol>
        {#each group.steps as step}
          {@const event = states[step.agent]}
          <li>
            <div>
              <strong>{step.label}</strong>
              <span class="op-state" data-state={event?.status}>{status(event?.status)}</span
              >{#if event?.message}<p>{event.message}</p>{/if}
            </div>
            <time>{when(event?.timestamp)}</time>
          </li>
        {/each}
      </ol>
    </details>
  {/each}
</section>
<section class="op-panel">
  <h2>최근 이벤트 <small>한국 시각</small></h2>
  {#if events.length}<ol class="op-events">
      {#each events as event}<li>
          <time>{when(event.timestamp)}</time>
          <div>
            <strong
              >{groups.flatMap((g) => g.steps).find((step) => step.agent === event.agent)?.label ||
                (event.agent === "system" ? "시스템" : event.agent || "실행")}</strong
            >
            <p>{event.message || status(event.status)}</p>
          </div>
        </li>{/each}
    </ol>
  {:else}<p>기록된 이벤트가 없습니다.</p>{/if}
</section>
