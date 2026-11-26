<script lang="ts">
  import PendingState from "./PendingState.svelte";
  export let summary: { total:number; done:number; skipped:number; failed:number; running:number; pending:number; as_of:string } | null;
  export let loading: boolean;
  export let error: string;
  const phases = [
    { key:"done", label:"완료", color:"#77516c" },
    { key:"running", label:"실행 중", color:"#22685b" },
    { key:"pending", label:"대기", color:"#b39682" },
    { key:"skipped", label:"건너뜀", color:"#877d87" },
    { key:"failed", label:"실패", color:"#b0433a" },
  ] as const;
  $: ready = !loading && !error && summary && Number.isFinite(summary.total);
  $: asOf = ready && summary?.as_of ? new Date(summary.as_of) : null;
  const day = new Intl.DateTimeFormat("ko-KR", { month:"long", day:"numeric", timeZone:"Asia/Seoul" });
</script>

<section class="session" aria-label="오늘의 분석 일정">
  <header><h3>오늘의 분석 일정</h3><a href="#/schedules">예약 보기 <span aria-hidden="true">↗</span></a></header>
  {#if loading}<PendingState label="분석 일정 조회 중" />
  {:else if !ready || !summary}<p role="status">일정 집계를 확인할 수 없습니다.</p>
  {:else}
    <div class="session-lead">
      <div><strong>{summary.total}</strong><span>건</span></div>
      {#if asOf && Number.isFinite(asOf.getTime())}<time datetime={summary.as_of}>{day.format(asOf)} · 한국시간</time>{/if}
    </div>
    <div class="schedule-track" aria-hidden="true">
      {#each phases as phase}{#if summary[phase.key] > 0}<i style:background={phase.color} style:flex-grow={summary[phase.key]}></i>{/if}{/each}
    </div>
    <dl>{#each phases as phase}<div><dt><i style:background={phase.color}></i>{phase.label}</dt><dd>{summary[phase.key]}</dd></div>{/each}</dl>
  {/if}
</section>

<style>
  .session { display:flex; flex-direction:column; justify-content:space-between; gap:14px; min-width:0; border:1px solid #d9c6ce; border-radius:22px; padding:clamp(18px,2.4vw,32px); background:linear-gradient(115deg,#f1e0e3,#f8eee5 88%); color:var(--fl-ink); }
  header,.session-lead { display:flex; align-items:center; justify-content:space-between; gap:9px; flex-wrap:wrap; }
  h3,.session p { margin:0; } h3 { font-size:1.05rem; letter-spacing:-.03em; }
  a { padding:6px 0 6px 6px; color:var(--fl-accent-hover); font-size:.82rem; font-weight:650; text-decoration:none; }
  a:hover { text-decoration:underline; } a span { margin-left:4px; }
  .session-lead { align-items:baseline; }
  .session-lead strong { font:660 clamp(2.9rem,5.5vw,5.1rem)/1 var(--fl-font); letter-spacing:-.075em; }
  .session-lead span { margin-left:5px; color:var(--fl-muted); font-size:1rem; }
  time, dt { color:#65545e; font-size:.78rem; }
  .schedule-track { display:flex; overflow:hidden; gap:2px; height:7px; border-radius:5px; background:#d8c8c9; }
  dl { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); margin:0; }
  dl div+div { border-left:1px solid #d9c9ce; padding-left:clamp(4px,1vw,14px); }
  dt { display:flex; align-items:center; gap:4px; white-space:nowrap; }
  dt i { width:5px; height:5px; border-radius:50%; flex:none; }
  dd { margin:3px 0 0; font-weight:670; line-height:1.35; font-size:1.25rem; }
  @media(max-width:400px){ dt { font-size:.72rem; } }
</style>
