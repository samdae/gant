<script lang="ts">
  import { instrumentName, tickerNames } from "../stores/tickerNames";
  import { callName, roundDate, roundLink, type PulseRow, type ReportRound } from "../lib/reportPulse";

  export let rows: PulseRow[];
  let selection = "";

  $: changed = rows.filter(row => row.status === "changed" && row.current?.decision && row.previous?.decision);
  $: comparable = changed.length ? changed : rows.filter(row => row.status === "unchanged" && row.current?.decision && row.previous?.decision);
  $: selected = comparable.find(row => row.ticker === selection) ?? comparable[0];
  $: remaining = rows.filter(row => row.status !== "changed" && row.status !== "unchanged").length;
  $: company = selected ? nameOf(selected.ticker, $tickerNames) : "";
  function nameOf(ticker: string, names: Record<string, string>) {
    return (instrumentName(ticker, names) || ticker).replace(/\s*\([^()]*\)$/, "");
  }
  const level = { BUY: 16, HOLD: 42, SELL: 68 };
  function ordinate(round: ReportRound) {
    return round.decision ? level[round.decision] : 42;
  }
  function label(round: ReportRound | null) {
    return round?.decision ? callName[round.decision] : "미기록";
  }
</script>

{#if selected?.current?.decision && selected.previous?.decision}
  {@const current = selected.current}
  {@const previous = selected.previous}
  <section class="briefing" aria-label="회차별 분석 판단 비교">
    <article class="feature" data-call={current.decision} aria-live="polite" aria-atomic="true">
      <header class="feature-label">
        <span class="pulse-symbol" aria-hidden="true"><svg viewBox="0 0 22 18"><path d="M1 10h5l3-7 4 12 3-6h5"/></svg></span>
        <span>{changed.length ? "이번 회차 판단 변경" : "이번 회차 판단 유지"}</span>
        <time datetime={current.at}>{roundDate(current)} 발행</time>
      </header>
      <div class="feature-body">
        <div class="subject">
          <h3>{company}</h3>
          <span class="ticker">{selected.ticker}{#if current.cycle} <i>·</i> {current.cycle}회차{/if}</span>
        </div>
        <div class="comparison" aria-label="직전과 이번 회차의 판단">
          <div class="reading prior"><span>직전 판단</span><strong>{label(previous)}</strong></div>
          <svg class="advance" viewBox="0 0 40 20" aria-hidden="true"><path d="M1 10h36M28 1l9 9-9 9"/></svg>
          <div class="reading now" data-call={current.decision}><span>이번 판단</span><strong>{label(current)}</strong></div>
          <svg class="trajectory" viewBox="0 0 228 84" preserveAspectRatio="none" aria-hidden="true">
            {#each [16,42,68] as y}<line class="guide" x1="12" y1={y} x2="216" y2={y}/>{/each}
            <line class="path" x1="27" y1={ordinate(previous)} x2="201" y2={ordinate(current)}/>
            <circle class="prior-point" cx="27" cy={ordinate(previous)} r="4"/>
            <circle class="halo" cx="201" cy={ordinate(current)} r="9"/>
            <circle class="final-point" cx="201" cy={ordinate(current)} r="4.5"/>
          </svg>
          <div class="axis"><time datetime={previous.at}>{roundDate(previous)}</time><time datetime={current.at}>{roundDate(current)}</time></div>
        </div>
        {#if selected.reason}<div class="excerpt"><span>이번 판단 근거</span><p>{selected.reason}</p></div>{/if}
      </div>
      <footer class="feature-actions">
        <a class="open-report" href={roundLink(selected.ticker, current)}>리포트 읽기 <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10m-4-4 4 4-4 4"/></svg></a>
        <a class="open-prior" href={roundLink(selected.ticker, previous)}>직전 회차</a>
      </footer>
    </article>
    {#if changed.length}
      <div class="switchboard">
        <header><h3>판단이 바뀐 종목</h3><span>{changed.length}개</span></header>
        <div class="switch-items" role="group" aria-label="비교할 종목 선택">
          {#each changed as row (row.ticker)}
            <button type="button" aria-pressed={selected.ticker === row.ticker} on:click={() => selection = row.ticker}
              aria-label={nameOf(row.ticker,$tickerNames) + " 판단 비교"}>
              <span class="switch-text"><b>{nameOf(row.ticker, $tickerNames)}</b><small>{label(row.previous)} <span aria-hidden="true">→</span> {label(row.current)}</small></span>
              <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m6 4 4 4-4 4"/></svg>
            </button>
          {/each}
        </div>
      </div>
    {:else}
      <div class="steady"><h3>비교 결과</h3><p>비교할 수 있는 {comparable.length}개 종목 모두 직전 판단을 유지했습니다.</p>{#if remaining}<small>{remaining}개 종목은 비교 자료가 부족합니다.</small>{/if}</div>
    {/if}
  </section>
{:else if rows.length}
  <p class="no-pair">이 종목의 직전 회차와 현재 판단을 아직 비교할 수 없습니다.</p>
{/if}

<style>
  .briefing{display:grid;grid-template-columns:minmax(0,1.9fr) minmax(210px,.82fr);gap:clamp(15px,2vw,32px);align-items:stretch;margin-bottom:28px;}
  .feature{--call:var(--fl-hold);--feature-secondary:#dcdcdc;position:relative;isolation:isolate;overflow:hidden;min-width:0;border-radius:24px;padding:clamp(20px,2.6vw,36px);color:var(--fl-feature-ink);background:var(--fl-feature);
    box-shadow:inset 0 0 0 1px var(--fl-line),0 10px 32px -24px rgb(0 0 0 / 15%);}
  .feature[data-call=SELL]{--call:var(--fl-sell);}
  .feature[data-call=BUY]{--call:var(--fl-buy);}
  .feature::before{content:"";position:absolute;z-index:-1;inset:-20% -16% 8% 45%;border:1px solid color-mix(in srgb,var(--fl-feature-muted) 16%,transparent);border-radius:50%;transform:rotate(-34deg);pointer-events:none;}
  .feature-label{display:flex;align-items:center;gap:8px;color:var(--feature-secondary);font-size:.83rem;font-weight:650;}
  .feature-label time{font-size:.77rem;font-weight:500;color:var(--fl-feature-muted);margin-left:auto;}
  .pulse-symbol{display:grid;place-items:center;width:24px;height:20px;color:var(--fl-accent);}
  .pulse-symbol svg,.advance,.feature-actions svg,.switch-items svg{fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round;}
  .feature-body{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(195px,.9fr);column-gap:clamp(12px,2.2vw,32px);align-items:center;margin-top:clamp(20px,3vw,42px);}
  .feature .subject h3{font-family:var(--fl-display);font-size:clamp(2rem,3.5vw,3.6rem);font-weight:710;line-height:1.16;letter-spacing:-.04em;color:var(--fl-feature-ink);margin:0;word-break:keep-all;overflow-wrap:anywhere;}
  .ticker{display:inline-block;color:var(--fl-feature-muted);font-size:.86rem;letter-spacing:.015em;margin-top:6px;}
  .ticker i{font-style:normal;margin-inline:3px;}
  .comparison{position:relative;display:grid;grid-column:2;grid-row:1/span 2;align-items:center;grid-template-columns:minmax(0,1fr) clamp(20px,3vw,40px) minmax(0,1fr);gap:0 7px;text-align:center;}
  .trajectory,.axis{grid-column:1/-1;width:100%;}
  .trajectory{height:clamp(66px,6.5vw,88px);overflow:visible;}
  .trajectory .guide{stroke:var(--feature-secondary);stroke-opacity:.19;stroke-width:1;stroke-dasharray:2.5 4;}
  .trajectory .path{stroke:var(--call);stroke-width:2.8;stroke-linecap:round;}
  .trajectory .prior-point{fill:var(--fl-feature);stroke:var(--feature-secondary);stroke-width:1.8;}
  .trajectory .final-point{fill:var(--call);}
  .trajectory .halo{fill:var(--call);opacity:.19;}
  .axis{display:flex;justify-content:space-between;padding-inline:5%;color:var(--fl-feature-muted);font-size:.75rem;font-variant-numeric:tabular-nums;}
  .reading.prior{justify-self:start;padding-inline-start:3%;}
  .reading.now{justify-self:end;padding-inline-end:3%;}
  .reading{display:grid;place-items:center;justify-content:center;}
  .reading span{color:var(--fl-feature-muted);font-size:.72rem;line-height:1.5;white-space:nowrap;}
  .reading strong{color:var(--feature-secondary);font-size:clamp(1.2rem,2.2vw,2.15rem);line-height:1.28;letter-spacing:-.04em;margin:5px 0;font-weight:650;}
  .reading.now strong{color:var(--call);font-weight:770;}
  .advance{width:100%;height:18px;color:var(--fl-feature-muted);}
  .excerpt{grid-column:1;max-width:68ch;margin:clamp(16px,2.5vw,27px) 0 0;}
  .excerpt span{display:block;color:var(--fl-accent);font-size:.73rem;font-weight:660;}
  .excerpt p{color:var(--fl-feature-ink);margin:4px 0 0;font-size:.95rem;line-height:1.65;word-break:keep-all;overflow-wrap:anywhere;}
  .feature-actions{display:flex;align-items:center;gap:16px;margin-top:18px;}
  .feature-actions a{display:inline-flex;align-items:center;justify-content:center;min-height:42px;text-decoration:none;font-weight:650;font-size:.85rem;}
  .feature-actions .open-report{border-radius:999px;padding:0 16px;background:var(--fl-action-bg);color:var(--fl-action-ink);gap:10px;}
  .open-report svg,.switch-items svg{width:16px;height:16px;}
  .feature-actions .open-prior{color:var(--fl-accent);text-decoration:underline;text-underline-offset:4px;text-decoration-color:var(--fl-feature-muted);}
  .feature:has(.open-report:hover) .open-report svg{transform:translateX(2px);}
  @media(prefers-reduced-motion:no-preference){.open-report svg{transition:transform .15s ease;}}
  .feature-actions a:focus-visible{outline:2px solid var(--fl-accent);outline-offset:3px;}
  .switchboard,.steady{min-width:0;display:flex;flex-direction:column;}
  .switchboard header{display:flex;align-items:baseline;justify-content:space-between;gap:8px;padding:4px 4px 12px;}
  .switchboard header h3,.steady h3{font-size:1.06rem;color:var(--fl-ink);margin:0;}
  .switchboard header span,.steady small{font-size:.8rem;color:var(--fl-muted);}
  .switch-items{height:0;flex:1 1 auto;min-height:146px;overflow:auto;scrollbar-width:thin;overscroll-behavior:contain;padding:1px 5px 3px 1px;}
  .switch-items button{cursor:pointer;width:100%;padding:9px 10px 9px 13px;min-height:51px;display:flex;align-items:center;justify-content:space-between;text-align:left;gap:10px;color:var(--fl-ink);background:transparent;border:0;border-bottom:1px solid var(--fl-line);font:inherit;border-radius:0;}
  .switch-items button[aria-pressed=true]{background:var(--fl-accent-soft);border-radius:12px;border-color:transparent;color:var(--fl-accent);}
  .switch-items button:hover{background:var(--fl-surface);}
  .switch-text{display:grid;gap:2px;}
  .switch-text b{font-size:.95rem;line-height:1.35;overflow-wrap:anywhere;}
  .switch-text small{font-size:.76rem;color:var(--fl-muted);}
  .switch-items svg{flex:none;color:var(--fl-muted);}
  .steady{justify-content:center;padding:16px;max-width:38ch;}
  .steady p,.no-pair{color:var(--fl-muted);line-height:1.55;}
  .no-pair{margin:12px 0;}
  @media(max-width:1040px) and (min-width:761px){.feature-body{grid-template-columns:minmax(0,1fr) 160px;}.feature .subject h3{font-size:2.15rem;}}
  @media(max-width:760px){
    .briefing{display:block;margin-bottom:22px;}
    .feature{border-radius:20px;}
    .feature-body{margin-top:19px;grid-template-columns:minmax(0,1fr) minmax(132px,.8fr);gap:8px 12px;}
    .feature .subject h3{font-size:clamp(1.74rem,6.5vw,2.35rem);}
    .reading span{font-size:.7rem;}
    .reading strong{font-size:clamp(1.23rem,5vw,1.63rem);}
    .comparison{grid-row:1;gap:0 3px;grid-template-columns:minmax(0,1fr) 17px minmax(0,1fr);}
    .trajectory{height:44px;}
    .axis{font-size:.68rem;line-height:1.2;}
    .excerpt{grid-column:1/-1;}
    .excerpt{margin:0;}
    .excerpt p{font-size:.9rem;}
    .feature-actions{margin-top:13px;}
    .feature-actions a{min-height:44px;}
    .switchboard{margin-top:15px;}
    .switchboard header{padding:0 2px 7px;}
    .switch-items{display:flex;gap:6px;min-height:0;height:auto;padding:2px 1px 6px;scroll-snap-type:x proximity;}
    .switch-items button{flex:0 0 auto;width:auto;min-width:92px;border:1px solid var(--fl-line);border-radius:12px;padding:7px 10px;scroll-snap-align:start;}
    .switch-items svg{display:none;}
    .switch-text b{font-size:.84rem;}
    .steady{padding:9px 0 0;}
    .steady p{margin:2px 0;}
  }
  @media(max-width:370px){.feature{padding:16px;}.feature-body{grid-template-columns:minmax(0,1fr) 126px;}.feature .subject h3{font-size:1.49rem;}.feature-body{grid-template-columns:1fr;gap:11px;}.comparison{grid-column:1;grid-row:2;grid-template-columns:auto 1fr auto;column-gap:12px;align-items:center;}.comparison .advance{display:none;}.comparison .reading.prior{grid-column:1;}.comparison .reading.now{grid-column:3;}.trajectory{grid-row:1;grid-column:2;height:45px;}.axis{font-size:.66rem;padding:0;}.reading strong{margin:1px 0;font-size:1.36rem;}.feature .subject{display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 10px;}.subject .ticker{margin:0;}}
  @media(forced-colors:active){.feature,.switch-items button,.open-report{border:1px solid CanvasText;}.feature::before{display:none;}.switch-items button[aria-pressed=true]{border:2px solid Highlight;}}
</style>
