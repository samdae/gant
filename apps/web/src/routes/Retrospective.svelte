<script lang="ts">
  import { onMount } from "svelte";
  import {
    fetchRetroSummary,
    fetchRetroTickers,
    fetchRetroPositions,
    requestRetroAnalysis,
  } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { currencyFilter, matchesCurrency } from "../stores/currency";
  import AnalysisTabs from "../components/AnalysisTabs.svelte";

  type TickerSummary = {
    ticker: string;
    display_name: string | null;
    completed_count: number;
    total_count: number;
    latest_at: string;
  };

  type TickerInfo = {
    ticker: string;
    display_name: string | null;
    position_count: number;
    has_trades: boolean;
  };

  type PositionRow = {
    position_id: number;
    ticker: string;
    pos_status: string;
    shares: number;
    avg_cost: number;
    return_pct: number | null;
    opened_at: string;
    closed_at: string | null;
    position_sequence: number;
    retro_id: number | null;
    retro_position_status: string | null;
    retro_status: string | null;
    analysis_count: number | null;
  };

  let loading = true;
  let error = "";
  let tickers: TickerSummary[] = [];

  let showModal = false;
  let modalTickers: TickerInfo[] = [];
  let modalTickersLoading = false;
  let modalActiveTicker = "";
  let modalPositions: PositionRow[] = [];
  let modalPositionsLoading = false;
  let modalSelectedPositions: Set<number> = new Set();
  let analyzing = false;
  let analyzeMessage = "";

  onMount(async () => {
    await loadSummary();
  });

  const loadSummary = async () => {
    loading = true;
    error = "";
    try {
      tickers = (await fetchRetroSummary()) as TickerSummary[];
    } catch (err) {
      error = formatErrorMessage(err, "회고분석 목록을 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const displayName = (t: TickerSummary): string => {
    if (t.display_name) return t.display_name;
    return $tickerNames[t.ticker] || "";
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    try {
      return new Date(iso).toLocaleDateString("ko-KR", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return "-";
    }
  };

  const openModal = async () => {
    showModal = true;
    analyzeMessage = "";
    modalActiveTicker = "";
    modalPositions = [];
    modalSelectedPositions = new Set();
    if (modalTickers.length === 0) {
      modalTickersLoading = true;
      try {
        modalTickers = (await fetchRetroTickers()) as TickerInfo[];
      } catch (err) {
        analyzeMessage = formatErrorMessage(err, "티커 목록 로드 실패");
      } finally {
        modalTickersLoading = false;
      }
    }
  };

  const closeModal = () => {
    showModal = false;
    analyzeMessage = "";
  };

  const modalToggleTicker = async (ticker: string) => {
    modalActiveTicker = modalActiveTicker === ticker ? "" : ticker;
    modalPositions = [];
    modalSelectedPositions = new Set();
    if (modalActiveTicker) {
      modalPositionsLoading = true;
      try {
        modalPositions = (await fetchRetroPositions(modalActiveTicker)) as PositionRow[];
        for (const row of modalPositions) {
          const status = getAnalysisStatus(row);
          if (status.canAnalyze) {
            modalSelectedPositions.add(row.position_id);
          }
        }
        modalSelectedPositions = modalSelectedPositions;
      } catch (err) {
        analyzeMessage = formatErrorMessage(err, "포지션 목록 로드 실패");
      } finally {
        modalPositionsLoading = false;
      }
    }
  };

  const modalTogglePosition = (pid: number) => {
    if (modalSelectedPositions.has(pid)) {
      modalSelectedPositions.delete(pid);
    } else {
      modalSelectedPositions.add(pid);
    }
    modalSelectedPositions = modalSelectedPositions;
  };

  const getAnalysisStatus = (row: PositionRow): { label: string; canAnalyze: boolean } => {
    if (!row.retro_status) return { label: "분석미완료", canAnalyze: true };
    if (row.retro_status === "pending" || row.retro_status === "running")
      return { label: "분석중", canAnalyze: false };
    if (row.retro_status === "completed" && row.retro_position_status === "closed")
      return { label: "완료(closed)", canAnalyze: false };
    if (row.retro_status === "completed" && row.retro_position_status === "open")
      return { label: "완료(open)", canAnalyze: true };
    if (row.retro_status === "failed")
      return { label: "실패", canAnalyze: true };
    return { label: row.retro_status, canAnalyze: true };
  };

  const runAnalysis = async (mode: "selected" | "all") => {
    analyzing = true;
    analyzeMessage = "";
    try {
      const payload = mode === "selected"
        ? { mode: "ticker", position_ids: [...modalSelectedPositions] }
        : { mode: "all" };
      const res = (await requestRetroAnalysis(payload)) as { enqueued: number[]; message: string };
      analyzeMessage = res.message;
      if (modalActiveTicker) {
        await modalToggleTicker(modalActiveTicker);
      }
    } catch (err) {
      analyzeMessage = formatErrorMessage(err, "분석 요청 실패");
    } finally {
      analyzing = false;
    }
  };

  const modalDisplayName = (t: TickerInfo): string => {
    if (t.display_name) return t.display_name;
    return $tickerNames[t.ticker] || t.ticker;
  };

  const formatModalDate = (iso: string | null) => {
    if (!iso) return "진행중";
    try {
      return new Date(iso).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
    } catch {
      return "-";
    }
  };

  $: filteredTickers = tickers.filter((t) => matchesCurrency(t.ticker, $currencyFilter));

  $: canRunSelected = modalSelectedPositions.size > 0;
</script>

<section class="page" id="page-retrospective">
  <div class="page-container">
    <div class="page-header">
      <h2>AI분석</h2>
    </div>
    <AnalysisTabs>
      <button slot="action" class="btn btn-primary" on:click={openModal}>요청</button>
    </AnalysisTabs>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if filteredTickers.length === 0}
      <div class="card" style="padding:16px;color:var(--text-dim)">완료된 회고분석이 없습니다. "회고분석 요청" 버튼으로 분석을 요청하세요.</div>
    {:else}
      <div class="retro-ticker-list list-grid">
        {#each filteredTickers as item}
          <a href={`#/retrospective/${item.ticker.toLowerCase()}`} class="retro-ticker-card list-row">
            <div class="retro-ticker-left">
              <span class="ticker-badge">{item.ticker}</span>
              {#if displayName(item)}
                <span class="ticker-tag">{displayName(item)}</span>
              {/if}
            </div>
            <div class="retro-ticker-meta">
              <span class="meta-count">{item.completed_count}건</span>
              <span class="meta-date">{formatDate(item.latest_at)}</span>
              <svg class="retro-ticker-chevron" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path d="M9 18l6-6-6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</section>

{#if showModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-overlay" on:click={closeModal}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h3>회고분석 요청</h3>
        <button class="modal-close" on:click={closeModal}>&times;</button>
      </div>

      <div class="modal-tab-bar">
        <div class="modal-tab active">티커</div>
      </div>

      <div class="modal-body">
        {#if modalTickersLoading}
          <div style="padding:12px;color:var(--text-dim)">불러오는 중...</div>
        {:else}
          <div class="modal-tickers">
            {#each modalTickers as t}
              <button
                class="tag-chip"
                class:active={modalActiveTicker === t.ticker}
                class:disabled={!t.has_trades}
                disabled={!t.has_trades}
                on:click={() => modalToggleTicker(t.ticker)}
              >
                {modalDisplayName(t)}
              </button>
            {/each}
          </div>

          {#if modalActiveTicker}
            {#if modalPositionsLoading}
              <div style="padding:8px;color:var(--text-dim);font-size:0.8125rem">포지션 로딩 중...</div>
            {:else if modalPositions.length === 0}
              <div style="padding:8px;color:var(--text-dim);font-size:0.8125rem">포지션이 없습니다.</div>
            {:else}
              <div class="modal-positions">
                {#each modalPositions as row}
                  {@const status = getAnalysisStatus(row)}
                  <label class="modal-pos-row" class:disabled={!status.canAnalyze}>
                    <span class="custom-checkbox" class:checked={modalSelectedPositions.has(row.position_id)} class:cb-disabled={!status.canAnalyze}>
                      <input
                        type="checkbox"
                        checked={modalSelectedPositions.has(row.position_id)}
                        disabled={!status.canAnalyze}
                        on:change={() => modalTogglePosition(row.position_id)}
                      />
                      <svg viewBox="0 0 14 14" class="check-icon">
                        <path d="M3 7l3 3 5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                      </svg>
                    </span>
                    <span>{row.position_sequence}회차</span>
                    <span class="pos-date">{formatModalDate(row.opened_at)}~{formatModalDate(row.closed_at)}</span>
                    <span class="pos-status">{status.label}</span>
                  </label>
                {/each}
              </div>
            {/if}
          {/if}
        {/if}
      </div>

      {#if analyzeMessage}
        <div class="modal-message">
          {analyzeMessage}
        </div>
      {/if}

      <div class="modal-footer">
        <button class="btn btn-primary" on:click={() => runAnalysis("selected")} disabled={analyzing || !canRunSelected}>
          {analyzing ? "요청 중..." : "선택티커"}
        </button>
        <button class="btn btn-primary" on:click={() => runAnalysis("all")} disabled={analyzing}>
          {analyzing ? "요청 중..." : "전체티커"}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .retro-ticker-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-decoration: none;
    color: inherit;
    padding: 14px 16px;
  }
  .retro-ticker-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .retro-ticker-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.8125rem;
    color: var(--text-dim);
  }
  .meta-count {
    color: var(--accent);
    font-weight: 600;
  }
  .retro-ticker-chevron {
    opacity: 0.4;
  }

  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 16px;
  }
  .modal-content {
    background: var(--bg-card, #1a1a2e);
    border-radius: 12px;
    width: 100%;
    max-width: 520px;
    max-height: 80vh;
    border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 20px 12px;
    flex-shrink: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }
  .modal-header h3 {
    margin: 0;
    font-size: 1rem;
  }
  .modal-close {
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }
  .modal-tab-bar {
    display: flex;
    gap: 4px;
    margin: 12px 20px 12px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    flex-shrink: 0;
  }
  .modal-tab {
    flex: 1;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 600;
    text-align: center;
    color: var(--text-dim);
  }
  .modal-tab.active {
    background: rgba(255, 255, 255, 0.08);
    color: #fff;
  }
  .modal-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0 20px;
    min-height: 0;
    scrollbar-width: thin;
  }
  .modal-message {
    padding: 8px 20px;
    font-size: 0.8125rem;
    color: var(--text-secondary);
    background: rgba(255, 255, 255, 0.04);
    flex-shrink: 0;
  }
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 20px 20px;
    flex-shrink: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }

  .modal-tickers {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 12px;
  }
  .tag-chip {
    padding: 5px 10px;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s ease;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tag-chip:hover:not(.disabled) {
    background: rgba(255, 255, 255, 0.08);
  }
  .tag-chip.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }
  .tag-chip.disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .modal-positions {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .modal-pos-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 8px;
    font-size: 0.8125rem;
    border-radius: 6px;
    cursor: pointer;
  }
  .modal-pos-row:hover {
    background: rgba(255, 255, 255, 0.04);
  }
  .modal-pos-row.disabled {
    opacity: 0.45;
    cursor: default;
  }
  .pos-date {
    color: var(--text-dim);
    font-size: 0.75rem;
  }
  .pos-status {
    margin-left: auto;
    font-size: 0.6875rem;
    color: var(--text-dim);
  }

  /* Custom checkbox */
  .custom-checkbox {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1.5px solid rgba(255, 255, 255, 0.25);
    background: rgba(255, 255, 255, 0.04);
    flex-shrink: 0;
    transition: all 0.15s ease;
  }
  .custom-checkbox input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
    pointer-events: none;
  }
  .custom-checkbox .check-icon {
    width: 12px;
    height: 12px;
    opacity: 0;
    color: #fff;
    transition: opacity 0.1s ease;
  }
  .custom-checkbox.checked {
    background: var(--accent);
    border-color: var(--accent);
  }
  .custom-checkbox.checked .check-icon {
    opacity: 1;
  }
  .custom-checkbox.cb-disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

</style>
