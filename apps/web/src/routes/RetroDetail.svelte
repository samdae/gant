<script lang="ts">
  import { onMount } from "svelte";
  import { params } from "svelte-spa-router";
  import { fetchRetroByTicker } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { marked } from "marked";
  import DOMPurify from "dompurify";
  import SelectMenu from "../components/SelectMenu.svelte";
  import AnalysisTabs from "../components/AnalysisTabs.svelte";

  type RetroItem = {
    id: number;
    position_id: number;
    ticker: string;
    position_sequence: number;
    position_status: string;
    status: string;
    analysis_content: string | null;
    analysis_count: number;
    position_open_date: string | null;
    position_close_date: string | null;
    pos_status: string;
    return_pct: number | null;
    error_message: string | null;
    created_at: string;
    updated_at: string;
  };

  let ticker = "";
  let loading = true;
  let error = "";
  let items: RetroItem[] = [];
  let selectedId = "";

  $: ticker = ($params?.ticker || "").toUpperCase();

  $: selectedItem = items.find((i) => String(i.id) === selectedId) || null;

  $: selectOptions = items.map((item) => {
    const seq = `${item.position_sequence}회차`;
    const status = item.position_status === "open" ? "진행중" : "종료";
    const outcome = item.pos_status === "closed" && item.return_pct != null
      ? (item.return_pct >= 0 ? `승 +${item.return_pct.toFixed(1)}%` : `패 ${item.return_pct.toFixed(1)}%`)
      : "";
    const label = [seq, status, outcome].filter(Boolean).join(" · ");
    return { value: String(item.id), label };
  });

  const loadData = async (t: string) => {
    if (!t) return;
    loading = true;
    error = "";
    items = [];
    selectedId = "";
    try {
      const res = (await fetchRetroByTicker(t)) as RetroItem[];
      items = res.filter((r) => r.status === "completed");
      if (items.length > 0) {
        selectedId = String(items[0].id);
      }
    } catch (err) {
      error = formatErrorMessage(err, "회고분석을 불러오지 못했습니다.");
    } finally {
      loading = false;
    }
  };

  const handleSelectChange = (event: CustomEvent<string>) => {
    selectedId = event.detail;
  };

  const renderMd = (text?: string | null): string => {
    if (!text) return "<em>분석 결과 없음</em>";
    const raw = marked.parse(text, { async: false }) as string;
    return DOMPurify.sanitize(raw);
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return "진행중";
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

  const displayName = (): string => {
    if (!ticker) return "";
    return $tickerNames[ticker] || "";
  };

  onMount(() => {
    if (ticker) loadData(ticker);
  });

  $: if (ticker) loadData(ticker);
</script>

<section class="page" id="page-retro-detail">
  <div class="page-container">
    <div class="page-header" style="display:flex;align-items:center;gap:8px">
      <a href="#/retrospective" class="back-link" aria-label="뒤로">&larr;</a>
      <h2>AI분석</h2>
    </div>
    <AnalysisTabs />

    <div class="retro-detail-header">
      <span class="ticker-badge">{ticker}</span>
      {#if displayName()}
        <span class="ticker-tag">{displayName()}</span>
      {/if}
    </div>

    {#if loading}
      <div class="card" style="padding:16px">불러오는 중...</div>
    {:else if error}
      <div class="card error-text" style="padding:16px">{error}</div>
    {:else if items.length === 0}
      <div class="card" style="padding:16px;color:var(--text-dim)">완료된 회고분석이 없습니다.</div>
    {:else}
      <label class="form-label">
        회차
        <SelectMenu
          value={selectedId}
          options={selectOptions}
          placeholder="회차 선택"
          on:change={handleSelectChange}
        />
      </label>

      {#if selectedItem}
        <div class="retro-meta" style="margin:12px 0;display:flex;gap:12px;flex-wrap:wrap;font-size:0.8125rem;color:var(--text-dim)">
          <span>{formatDate(selectedItem.position_open_date)} ~ {formatDate(selectedItem.position_close_date)}</span>
          {#if selectedItem.pos_status === "closed" && selectedItem.return_pct != null}
            <span class={selectedItem.return_pct >= 0 ? "text-gain" : "text-loss"}>
              {selectedItem.return_pct >= 0 ? "승" : "패"} ({selectedItem.return_pct >= 0 ? "+" : ""}{selectedItem.return_pct.toFixed(2)}%)
            </span>
          {:else}
            <span>진행중</span>
          {/if}
          <span>분석 {selectedItem.analysis_count}회</span>
        </div>

        <div class="card retro-result-card">
          <div class="md-content retro-result-body">
            {@html renderMd(selectedItem.analysis_content)}
          </div>
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .back-link {
    color: var(--text-dim);
    text-decoration: none;
    font-size: 1.25rem;
    line-height: 1;
  }
  .back-link:hover {
    color: var(--text-primary);
  }
  .retro-detail-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  .retro-result-card {
    margin-top: 8px;
  }
  .retro-result-body {
    padding: 16px;
    font-size: 0.8125rem;
    line-height: 1.8;
    color: var(--text-secondary);
  }
</style>
