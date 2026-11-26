<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import ReportIssueArchive from "../components/ReportIssueArchive.svelte";
  import ReportDecisionEvidence from "../components/ReportDecisionEvidence.svelte";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import { params, querystring } from "svelte-spa-router";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { publicJson } from "../lib/api/publicReads";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { renderNarrative } from "../lib/utils/researchMarkdown";
  import SelectMenu from "../components/SelectMenu.svelte";

  type Report = {
    id: number;
    created_at: string;
    ticker?: string;
    display_name?: string;
    scheduled_cycle?: number;
    decision_position?: string;
    portfolio_action?: string;
    portfolio_shares?: number;
    portfolio_rationale?: string;
    market_report?: string;
    fundamentals_report?: string;
    bull_history?: string;
    bear_history?: string;
    investment_debate_judge_decision?: string;
    aggressive_history?: string;
    conservative_history?: string;
    neutral_history?: string;
    trader_investment_judge_decision?: string;
    trader_investment_decision?: string;
    investment_plan?: string;
    final_trade_decision?: string;
    pa_opinion?: string;
  };

  type ReportField = {
    key: keyof Report;
    label: string;
    isDecision?: boolean;
  };

  type ReportGroup = {
    name: string;
    items: ReportField[];
    children?: ReportField[];
  };

  const reportGroups: ReportGroup[] = [
    {
      name: "분석",
      items: [
        { key: "market_report", label: "시장 분석" },
        { key: "fundamentals_report", label: "펀더멘털 분석" },
      ],
    },
    {
      name: "투자 토론",
      items: [
        { key: "investment_debate_judge_decision", label: "심판 결론", isDecision: true },
      ],
      children: [
        { key: "bull_history", label: "강세 분석" },
        { key: "bear_history", label: "약세 분석" },
      ],
    },
    {
      name: "투자 계획",
      items: [
        { key: "investment_plan", label: "투자 계획" },
      ],
    },
    {
      name: "매매 결정",
      items: [
        { key: "trader_investment_decision", label: "트레이더 결정" },
      ],
    },
    {
      name: "리스크 토론",
      items: [
        { key: "trader_investment_judge_decision", label: "리스크 결론", isDecision: true },
      ],
      children: [
        { key: "aggressive_history", label: "공격적 분석" },
        { key: "conservative_history", label: "보수적 분석" },
        { key: "neutral_history", label: "중립적 분석" },
      ],
    },
    {
      name: "최종 결정",
      items: [
        { key: "final_trade_decision", label: "최종 매매 결정" },
      ],
    },
    {
      name: "트레이더 의견",
      items: [
        { key: "pa_opinion", label: "트레이더 의견" },
      ],
    },
  ];

  const conclusion = reportGroups.find((group) => group.items.some((field) => field.key === "final_trade_decision"));
  const orderedGroups = isForecastLab && conclusion ? [conclusion, ...reportGroups.filter((group) => group !== conclusion)] : reportGroups;
  const sectionsByReport = new Map<number,Record<string,boolean>>();

  let ticker = "";
  let loading = true;
  let error = "";
  let report: Report | null = null;
  let reports: Report[] = [];
  let selectedReportId = "";
  let reportOptions: Array<{ value: string; label: string }> = [];
  let decisionKey = "";
  let decisionLabel = "";
  let openSections: Record<string, boolean> = {};

  const toggle = (key: string) => {
    openSections[key] = !openSections[key];
  };

  const getField = (r: Report, key: keyof Report): string => {
    const val = r[key];
    return typeof val === "string" ? val : "";
  };

  const renderMd = (text?: string | null) => renderNarrative(text, "데이터 없음");

  const normalizeDecision = (value: string): string => {
    const upper = value.trim().toUpperCase();
    if (upper === "BUY" || upper === "SELL" || upper === "HOLD") return upper;
    if (value.includes("매수")) return "BUY";
    if (value.includes("매도")) return "SELL";
    if (value.includes("관망") || value.includes("보유")) return "HOLD";
    return "";
  };

  const extractDecision = (text?: string | null): string => {
    if (!text) return "";
    const cleaned = text.replace(/\*\*/g, "");
    const lines = cleaned
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    const decisionLine = lines.find((line) => /결정|decision/i.test(line));
    if (decisionLine) {
    const match = decisionLine.match(/(?:결정|decision)[:：]\s*(BUY|SELL|HOLD|매수|매도|관망|보유)/i);
      if (match?.[1]) return normalizeDecision(match[1]);
    }
    return "";
  };

  const getDecision = (r: Report | null): string => {
    if (!r) return "";
    if (r.portfolio_action) return normalizeDecision(r.portfolio_action);
    if (r.decision_position) return normalizeDecision(r.decision_position);
    return extractDecision(r.final_trade_decision);
  };

  const getDecisionLabel = (value: string) => {
    if (value === "BUY") return "매수";
    if (value === "SELL") return "매도";
    if (value === "HOLD") return "관망";
    return "";
  };

  const formatShares = (value?: number | null): string => {
    if (value == null) return "";
    return value.toLocaleString(undefined, { maximumFractionDigits: 6 });
  };

  const selectReport = (id: string) => {
    if (isForecastLab && report) sectionsByReport.set(report.id, { ...openSections });
    selectedReportId = id;
    report = reports.find((item) => String(item.id) === id) || null;
    openSections = isForecastLab && report ? sectionsByReport.get(report.id) ?? { final_trade_decision: Boolean(report.final_trade_decision?.trim()) } : {};
  };

  let loadSequence = 0;
  const loadReport = async (t: string, requested: string) => {
    const request = ++loadSequence;
    loading = true;
    error = "";
    try {
      let symbol = t;
      const publicId = isPublicViewer && /^[1-9]\d*$/.test(t) ? t : "";
      if (publicId) {
        const item = await publicJson<{ticker?: string}>("/public-api/reports/" + publicId, {
          notFoundMessage: "공개된 리포트를 찾을 수 없습니다.",
        });
        if (typeof item.ticker !== "string") throw new Error("리포트의 종목을 확인할 수 없습니다.");
        symbol = item.ticker;
      }
      let result = (await fetchReportsByTicker(symbol, 20)) as Report[];
      const requestedId = publicId || requested;
      if (isPublicViewer && requestedId && !result.some(item => String(item.id) === requestedId) && request === loadSequence) {
        result = (await fetchReportsByTicker(symbol, 20, {refresh: true})) as Report[];
      }
      if (request !== loadSequence || ticker !== t) return;
      reports = result;
      if (reports && reports.length > 0) {
        selectReport(publicId || requested || String(reports[0].id));
      } else {
        report = null;
        selectedReportId = "";
      }
    } catch (err) {
      if (request !== loadSequence || ticker !== t) return;
      error = formatErrorMessage(err, "AI분석을 불러오지 못했습니다.");
    } finally {
      if (request === loadSequence && ticker === t) loading = false;
    }
  };

  const handleReportChange = (value: string) => {
    selectReport(value);
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    const requested = isForecastLab ? new URLSearchParams($querystring).get("report") || "" : "";
    loadReport(ticker, /^[1-9]\d{0,15}$/.test(requested) ? requested : "");
  }

  $: decisionKey = getDecision(report);
  $: decisionLabel = getDecisionLabel(decisionKey);

  $: reportOptions = reports.map((item) => ({
    value: String(item.id),
    label: item.scheduled_cycle ? `${item.scheduled_cycle} 회차 · ${formatDateTime(item.created_at)}` : `AI분석 #${item.id} · ${formatDateTime(item.created_at)}`,
  }));

</script>

<section class="page" id="page-report-detail">
  <div class="page-container">
    {#if isForecastLab}
      <header class="report-heading">
        <a class="archive-back" href="#/reports"><svg aria-hidden="true" viewBox="0 0 20 20"><path d="m11 5-5 5 5 5m-5-5h9"/></svg>리포트 목록</a>
        <div class="report-identity">
          <h2><InstrumentLabel ticker={report?.ticker || ticker} name={report?.display_name} /></h2>
          {#if report && !loading && !error}<p>분석 리포트 <span>·</span> <time datetime={report.created_at}>{formatDateTime(report.created_at)}</time></p>{/if}
        </div>
        {#if report && !loading && !error}
          <div class="round-select"><label for="cycle-select">발행 회차</label>
            <SelectMenu id="cycle-select" value={selectedReportId} options={reportOptions} placeholder="회차 선택"
              on:change={(event) => handleReportChange(event.detail)} />
          </div>
        {/if}
      </header>
    {:else}
      <div class="page-header">
        <button class="back-btn" aria-label="이전 화면" on:click={() => history.back()}>&larr;</button>
        <h2><InstrumentLabel ticker={report?.ticker || ticker} name={report?.display_name} inline /> AI분석</h2>
      </div>
    {/if}

    {#if loading}
      <div class="card" style="padding:16px"><PendingState label="분석 리포트 조회 중"/></div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if !report}
      <div class="card" style="padding:16px"><InstrumentLabel {ticker} inline /> AI분석이 없습니다.</div>
    {:else}
      {#if !isForecastLab && reports.length > 0}
        <div class="form-label"><label for="cycle-select">회차</label>
            <SelectMenu id="cycle-select"
            value={selectedReportId}
            options={reportOptions}
            placeholder="회차 선택"
            on:change={(event) => handleReportChange(event.detail)}
          />
        </div>
      {/if}
      <div class="report-meta">
        {#if isForecastLab}
          <ReportDecisionEvidence {report} />
        {:else if decisionKey}
          <span class={`decision-badge decision-${decisionKey.toLowerCase()}`}>{decisionLabel}</span>
        {:else}
          <span class="decision-badge decision-unknown">—</span>
        {/if}
        {#if !isForecastLab}<span class="report-date">{formatDateTime(report.created_at)}</span>{/if}
        {#if !isForecastLab && report.scheduled_cycle}
          <span class="report-date">{report.scheduled_cycle} 회차</span>
        {/if}
        {#if !isForecastLab && report.portfolio_action}
          <span class="report-date">
            실행 제안: {getDecisionLabel(normalizeDecision(report.portfolio_action))}
            {#if report.portfolio_shares != null}
              · {isForecastLab ? "제안 수량 " : ""}{formatShares(report.portfolio_shares)}주
            {/if}
          </span>
        {/if}
      </div>

      {#each orderedGroups as group}
        <div class="report-group" class:desk-conclusion={isForecastLab && group === conclusion}>
          {#if !isForecastLab || group !== conclusion}
            <div class="report-group-label">{group.name}</div>
          {/if}

          {#each group.items as field}
            <button
              class="report-accordion"
              aria-expanded={!!openSections[field.key]}
              class:open={openSections[field.key]}
              class:decision={field.isDecision}
              on:click={() => toggle(String(field.key))}
            >
              <span class="accordion-title">{field.label}</span>
              <svg class="disclose" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>
            </button>
            {#if openSections[field.key]}
              <div class="report-content markdown-body">
                {@html renderMd(report ? getField(report, field.key) : '')}
              </div>
            {/if}
          {/each}

          {#if group.children}
            <div class="report-children">
              {#each group.children as child}
                <button
                  class="report-accordion child"
                  aria-expanded={!!openSections[child.key]}
                  class:open={openSections[child.key]}
                  on:click={() => toggle(String(child.key))}
                >
                  <span class="accordion-title">{child.label}</span>
                  <svg class="disclose" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg>
                </button>
                {#if openSections[child.key]}
                  <div class="report-content markdown-body child-content">
                    {@html renderMd(report ? getField(report, child.key) : '')}
                  </div>
                {/if}
              {/each}
            </div>
          {/if}
        </div>
        {#if isForecastLab && group === conclusion}
          {#key report.id}
            <ReportIssueArchive id={report.id} ticker={report.ticker || ticker} />
          {/key}
        {/if}
      {/each}
    {/if}
  </div>
</section>

<style>
  .report-heading { display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:end; gap:10px 22px; padding-bottom:8px; }
  .archive-back { grid-column:1/-1; display:inline-flex; align-items:center; gap:6px; width:fit-content; color:var(--fl-accent); font-size:.85rem; font-weight:650; text-decoration:none; }
  .archive-back svg,.disclose { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
  .archive-back:hover { text-decoration:underline; }
  .report-identity h2 { margin:0; font:730 clamp(2rem,4vw,3.5rem)/1.15 var(--fl-display); letter-spacing:-.04em; }
  .report-identity p { margin:8px 0 0; color:var(--fl-muted); font-size:.82rem; }
  .report-identity p span { padding-inline:3px; }
  .round-select { display:flex; align-items:center; justify-content:flex-end; gap:8px; font-size:.82rem; color:var(--fl-muted); min-width:0; }
  .round-select label { white-space:nowrap; flex-shrink:0; }
  .round-select :global(.select-menu) { min-width:0; max-width:100%; }
  .disclose { flex-shrink:0; width:15px; height:15px; transition:transform .16s ease; }
  .open .disclose { transform:rotate(180deg); }
  :global(.workspace) #page-report-detail .report-meta { background:var(--fl-forecast-soft); border:1px solid var(--fl-line); border-radius:var(--fl-radius,16px); margin:12px 0 16px; padding:clamp(14px,1.7vw,20px); }
  :global(.workspace) #page-report-detail .report-group { border:1px solid var(--fl-line); border-radius:var(--fl-radius,16px); overflow:hidden; }
  :global(.workspace) #page-report-detail .report-group-label { color:var(--fl-ink); background:var(--fl-surface-subtle); padding:12px 18px; }
  :global(.workspace) #page-report-detail .report-content { padding:4px clamp(15px,3vw,35px) 22px; }
  :global(.workspace) #page-report-detail .report-content :global(p) { max-width:72ch; line-height:1.72; }
  :global(.workspace) #page-report-detail .desk-conclusion { background:var(--fl-surface); border-top:3px solid var(--fl-accent); }
  :global(.workspace) #page-report-detail .desk-conclusion .report-accordion { width:100%; margin:0; min-height:48px; padding:14px clamp(16px,2.8vw,34px); border-radius:0; font-size:1.05rem; font-weight:720; color:var(--fl-ink); background:transparent; }
  :global(.workspace) #page-report-detail .desk-conclusion .report-accordion:hover { background:var(--fl-forecast-soft); }
  :global(.workspace) #page-report-detail .desk-conclusion .report-content { margin:0; border-radius:0; background:transparent; padding:0 clamp(16px,2.8vw,34px) 22px; font-size:.95rem; }
  :global(.workspace) #page-report-detail .desk-conclusion .report-content :global(p:first-child) { margin-top:0; }
  @media(max-width:670px) {
    .report-heading { grid-template-columns:minmax(0,1fr); gap:12px; }
    .round-select { display:grid; grid-template-columns:minmax(0,1fr); justify-content:start; gap:5px; }
    .round-select :global(.select-menu) { width:100%; }
  }
  @media(prefers-reduced-motion:reduce) { .disclose { transition:none; } }
</style>
