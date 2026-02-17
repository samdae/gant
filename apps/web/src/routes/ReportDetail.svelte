<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { marked } from "marked";
  import DOMPurify from "dompurify";
  import SelectMenu from "../components/SelectMenu.svelte";

  type Report = {
    id: number;
    created_at: string;
    ticker?: string;
    scheduled_cycle?: number;
    decision_position?: string;
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

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>데이터 없음</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

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
    if (r.decision_position) return normalizeDecision(r.decision_position);
    return extractDecision(r.final_trade_decision);
  };

  const getDecisionLabel = (value: string) => {
    if (value === "BUY") return "매수";
    if (value === "SELL") return "매도";
    if (value === "HOLD") return "관망";
    return "";
  };

  const selectReport = (id: string) => {
    selectedReportId = id;
    report = reports.find((item) => String(item.id) === id) || null;
    openSections = {};
  };

  const loadReport = async (t: string) => {
    loading = true;
    error = "";
    try {
      reports = (await fetchReportsByTicker(t, 20)) as Report[];
      if (reports && reports.length > 0) {
        selectReport(String(reports[0].id));
      } else {
        report = null;
        selectedReportId = "";
      }
    } catch (err) {
      error = formatErrorMessage(err, "AI분석을 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const handleReportChange = (value: string) => {
    selectReport(value);
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadReport(ticker);
  }

  $: decisionKey = getDecision(report);
  $: decisionLabel = getDecisionLabel(decisionKey);

  $: reportOptions = reports.map((item) => ({
    value: String(item.id),
    label: item.scheduled_cycle ? `${item.scheduled_cycle} 회차 · ${formatDateTime(item.created_at)}` : `AI분석 #${item.id} · ${formatDateTime(item.created_at)}`,
  }));

  onMount(() => {
    if (ticker) loadReport(ticker);
  });
</script>

<section class="page" id="page-report-detail">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker} AI분석</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if !report}
      <div class="card" style="padding:16px">{ticker} AI분석이 없습니다.</div>
    {:else}
      {#if reports.length > 0}
        <label class="form-label">
          회차
          <SelectMenu
            value={selectedReportId}
            options={reportOptions}
            placeholder="회차 선택"
            on:change={(event) => handleReportChange(event.detail)}
          />
        </label>
      {/if}
      <div class="report-meta">
        {#if decisionKey}
          <span class={`decision-badge decision-${decisionKey.toLowerCase()}`}>{decisionLabel}</span>
        {:else}
          <span class="decision-badge decision-unknown">—</span>
        {/if}
        <span class="report-date">{formatDateTime(report.created_at)}</span>
        {#if report.scheduled_cycle}
          <span class="report-date">{report.scheduled_cycle} 회차</span>
        {/if}
      </div>

      {#each reportGroups as group}
        <div class="report-group">
          <div class="report-group-label">{group.name}</div>

          {#each group.items as field}
            <button
              class="report-accordion"
              class:open={openSections[field.key]}
              class:decision={field.isDecision}
              on:click={() => toggle(String(field.key))}
            >
              <span class="accordion-title">{field.label}</span>
              <span class="accordion-chevron">{openSections[field.key] ? '▾' : '▸'}</span>
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
                  class:open={openSections[child.key]}
                  on:click={() => toggle(String(child.key))}
                >
                  <span class="accordion-title">{child.label}</span>
                  <span class="accordion-chevron">{openSections[child.key] ? '▾' : '▸'}</span>
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
      {/each}
    {/if}
  </div>
</section>
