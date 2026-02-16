<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { fetchReportsByTicker } from "../lib/api/endpoints";
  import { formatDateTime, formatErrorMessage } from "../lib/utils/format";
  import { marked } from "marked";
  import DOMPurify from "dompurify";

  type Report = {
    id: number;
    created_at: string;
    ticker?: string;
    scheduled_cycle?: number;
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
      name: "Analysis",
      items: [
        { key: "market_report", label: "Market Analyst" },
        { key: "fundamentals_report", label: "Fundamentals Analyst" },
      ],
    },
    {
      name: "Investment Debate",
      items: [
        { key: "investment_debate_judge_decision", label: "Judge Decision", isDecision: true },
      ],
      children: [
        { key: "bull_history", label: "Bull Analyst" },
        { key: "bear_history", label: "Bear Analyst" },
      ],
    },
    {
      name: "Investment Plan",
      items: [
        { key: "investment_plan", label: "Investment Plan" },
      ],
    },
    {
      name: "Trade Decision",
      items: [
        { key: "trader_investment_decision", label: "Trader Decision" },
      ],
    },
    {
      name: "Risk Assessment",
      items: [
        { key: "trader_investment_judge_decision", label: "Risk Judge Decision", isDecision: true },
      ],
      children: [
        { key: "aggressive_history", label: "Aggressive Analyst" },
        { key: "conservative_history", label: "Conservative Analyst" },
        { key: "neutral_history", label: "Neutral Analyst" },
      ],
    },
    {
      name: "Final Decision",
      items: [
        { key: "final_trade_decision", label: "Final Trade Decision" },
      ],
    },
    {
      name: "Trader Decision",
      items: [
        { key: "pa_opinion", label: "Trader Opinion" },
      ],
    },
  ];

  let ticker = "";
  let loading = true;
  let error = "";
  let report: Report | null = null;
  let openSections: Record<string, boolean> = {};

  const toggle = (key: string) => {
    openSections[key] = !openSections[key];
  };

  const getField = (r: Report, key: keyof Report): string => {
    const val = r[key];
    return typeof val === "string" ? val : "";
  };

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>No data</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

  const loadReport = async (t: string) => {
    loading = true;
    error = "";
    try {
      const reports = (await fetchReportsByTicker(t, 1)) as Report[];
      report = reports && reports.length > 0 ? reports[0] : null;
    } catch (err) {
      error = formatErrorMessage(err, "Failed to load report.");
    } finally {
      loading = false;
    }
  };

  $: if ($params?.ticker) {
    ticker = String($params.ticker).toUpperCase();
  }

  $: if (ticker) {
    loadReport(ticker);
  }

  onMount(() => {
    if (ticker) loadReport(ticker);
  });
</script>

<section class="page" id="page-report-detail">
  <div class="page-container">
    <div class="page-header">
      <button class="back-btn" on:click={() => history.back()}>&larr;</button>
      <h2>{ticker} Report</h2>
    </div>

    {#if loading}
      <div class="card" style="padding:16px">Loading...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if !report}
      <div class="card" style="padding:16px">No report found for {ticker}.</div>
    {:else}
      <div class="report-meta">
        <span class="cycle-badge">Report #{report.id}</span>
        <span class="report-date">{formatDateTime(report.created_at)}</span>
        {#if report.scheduled_cycle}
          <span class="report-date">Cycle #{report.scheduled_cycle}</span>
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
