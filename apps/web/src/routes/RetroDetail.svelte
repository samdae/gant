<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import InstrumentLabel from "../components/InstrumentLabel.svelte";
  import { isForecastLab } from "../lib/workspace";
  import { params } from "svelte-spa-router";
  import { fetchRetroByTicker } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { tickerNames } from "../stores/tickerNames";
  import { renderNarrative } from "../lib/utils/researchMarkdown";
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
    const status = item.pos_status === "reset" ? "리셋" : item.position_status === "open" ? "진행중" : "종료";
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
      if (ticker !== t) return;
      items = res.filter((r) => r.status === "completed");
      if (items.length > 0) {
        selectedId = String(items[0].id);
      }
    } catch (err) {
      if (ticker !== t) return;
      error = formatErrorMessage(err, "회고분석을 불러오지 못했습니다.");
    } finally {
      if (ticker === t) loading = false;
    }
  };

  const handleSelectChange = (event: CustomEvent<string>) => {
    selectedId = event.detail;
  };

  const renderMd = (text?: string | null) => renderNarrative(text, "분석 결과 없음");

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


  $: if (ticker) loadData(ticker);
</script>

<section class="page" id="page-retro-detail">
  <div class="page-container">
    <div class="page-header" style="display:flex;align-items:center;gap:8px">
      <a href="#/retrospective" class="back-link" aria-label="뒤로">&larr;</a>
      <h2>{#if isForecastLab}<InstrumentLabel {ticker} /><small>회고 분석 상세</small>{:else}AI분석{/if}</h2>
    </div>
    {#if !isForecastLab}<AnalysisTabs />{/if}

    <div class="retro-detail-shell">
      {#if !isForecastLab}<div class="retro-detail-header">
        <span class="ticker-badge">{ticker}</span>
        {#if displayName()}
          <span class="ticker-tag">{displayName()}</span>
        {/if}
      </div>{/if}

      {#if loading}
        <div class="card" style="padding:16px"><PendingState label="회고 분석 조회 중"/></div>
      {:else if error}
        <div class="card error-text" style="padding:16px">{error}</div>
      {:else if items.length === 0}
        <div class="card" style="padding:16px;color:var(--text-dim)">완료된 회고분석이 없습니다. {#if isForecastLab}<a href="#/retrospective">회고 분석 목록</a>{/if}</div>
      {:else}
        <div class="form-label"><label for="cycle-select">회차</label>
            <SelectMenu id="cycle-select"
            value={selectedId}
            options={selectOptions}
            placeholder="회차 선택"
            on:change={handleSelectChange}
          />
        </div>

        {#if selectedItem}
          {#if isForecastLab}
          <dl class="review-facts">
            <div>
              <dt>포지션</dt>
              <dd>
                {selectedItem.pos_status === "open"
                  ? "보유 중"
                  : selectedItem.pos_status === "reset"
                    ? "초기화"
                    : selectedItem.pos_status === "closed"
                      ? "종료"
                      : "미기록"}
              </dd>
            </div>
            <div>
              <dt>보유 시작</dt>
              <dd>
                {selectedItem.position_open_date ? formatDate(selectedItem.position_open_date) : "미기록"}
              </dd>
            </div>
            <div>
              <dt>보유 종료</dt>
              <dd>{selectedItem.position_close_date ? formatDate(selectedItem.position_close_date) : "—"}</dd>
            </div>
            <div>
              <dt>종료 수익률</dt>
              <dd>
                {selectedItem.pos_status === "closed" && selectedItem.return_pct != null
                  ? selectedItem.return_pct.toFixed(2) + "%"
                  : "—"}
              </dd>
            </div>
            <div>
              <dt>분석 횟수</dt>
              <dd>{selectedItem.analysis_count}회</dd>
            </div>
          </dl>
          {:else}
          <div class="retro-meta" style="margin:12px 0;display:flex;gap:12px;flex-wrap:wrap;font-size:0.8125rem;color:var(--text-dim)">
            <span>{formatDate(selectedItem.position_open_date)} ~ {formatDate(selectedItem.position_close_date)}</span>
            {#if selectedItem.pos_status === "closed" && selectedItem.return_pct != null}
              <span class={selectedItem.return_pct >= 0 ? "text-gain" : "text-loss"}>
                {selectedItem.return_pct >= 0 ? "승" : "패"} ({selectedItem.return_pct >= 0 ? "+" : ""}{selectedItem.return_pct.toFixed(2)}%)
              </span>
            {:else}
              <span>{selectedItem.pos_status === "closed" ? "종료 · 수익률 미기록" : "진행 중"}</span>
            {/if}
            <span>분석 {selectedItem.analysis_count}회</span>
          </div>

          {/if}
          <div class="card retro-result-card">
            {#if isForecastLab}<div class="card-header"><h3>회차별 판단 평가</h3></div>{/if}
            <div class="md-content retro-result-body">
              {@html renderMd(selectedItem.analysis_content)}
            </div>
          </div>
        {/if}
      {/if}
    </div>
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
  .retro-detail-shell {
    max-width: 444px;
    margin: 0 auto;
    padding: 0 2px;
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
    padding: 18px;
    font-size: 0.8125rem;
    line-height: 1.85;
    color: var(--text-secondary);
  }
</style>
