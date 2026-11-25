<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import { tokenStore } from "../stores/auth";
  import { isForecastLab } from "../lib/workspace";
  import { onMount } from "svelte";
  import { createPortfolioConfig } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { portfolioRefreshTrigger } from "../stores/mode";

  export let onClose: () => void;
  export let onActivated: () => void;

  let dialog: HTMLDialogElement;
  const draftKey = "forecast-lab:portfolio-setup-draft";
  onMount(() => {
    if (isForecastLab && new URLSearchParams(window.location.hash.split("?")[1]).get("setup") === "1") {
      try {
        const raw = sessionStorage.getItem(draftKey);
        sessionStorage.removeItem(draftKey);
        const draft = raw && JSON.parse(raw);
        if (draft && Number.isFinite(draft.capital) && draft.capital > 0 && ["KRW","USD"].includes(draft.currency)) {
          capital = draft.capital;
          currency = draft.currency;
        }
      } catch { /* The form works with defaults if browser storage is unavailable. */ }
    }
    dialog.showModal();
  });

  let capital = 100000000;
  let currency: "KRW" | "USD" = "KRW";
  let loading = false;
  let error = "";

  async function handleActivate() {
    if (!Number.isFinite(capital) || capital <= 0) {
      error = "초기 자본을 입력해 주세요.";
      return;
    }
    if (isForecastLab && !$tokenStore) {
      try {
        sessionStorage.setItem(draftKey, JSON.stringify({ capital, currency }));
      } catch { /* Continue to authentication even if the browser cannot retain a draft. */ }
      window.location.hash = "#/auth?return=" + encodeURIComponent("#/portfolio?setup=1");
      return;
    }
    loading = true;
    error = "";
    try {
      await createPortfolioConfig({
        initial_capital: capital,
        base_currency: currency,
        fee_enabled: true,
        reset_fund_to_initial: false,
      });
      portfolioRefreshTrigger.set(Date.now());
      onActivated();
    } catch (err) {
      error = formatErrorMessage(err, "포트폴리오 활성화에 실패했습니다.");
    } finally {
      loading = false;
    }
  }
</script>

<dialog bind:this={dialog} class="modal" aria-labelledby="activate-title"
  on:cancel={(event) => { event.preventDefault(); if (!loading) onClose(); }}>
    <h3 id="activate-title">포트폴리오 모드 활성화</h3>
    <p class="modal-desc">공유 자금 풀로 전체 티커를 리밸런싱합니다. 활성화하시겠습니까?</p>

    <div class="form-group">
      <label for="capital">초기 자본</label>
      <input
        id="capital"
        type="number"
        min="1"
        step={currency === "KRW" ? 100000 : 100}
        bind:value={capital}
        disabled={loading}
      />
    </div>

    <div class="form-group">
      <span id="currency-label">기준 통화</span>
      <div class="currency-options" role="group" aria-labelledby="currency-label">
        <button
          class="currency-opt"
          class:active={currency === "KRW"}
          on:click={() => (currency = "KRW")}
          disabled={loading}
        >KRW</button>
        <button
          class="currency-opt"
          class:active={currency === "USD"}
          on:click={() => (currency = "USD")}
          disabled={loading}
        >USD</button>
      </div>
    </div>

    {#if error}
      <p class="error-text">{error}</p>
    {/if}

    <div class="modal-actions">
      <button class="btn-secondary" on:click={onClose} disabled={loading}>취소</button>
      <button class="btn-primary" on:click={handleActivate} disabled={loading}>
        {#if loading}<PendingState label="처리 중"/>{:else}{isForecastLab && !$tokenStore ? "관리자 인증 후 활성화" : "활성화"}{/if}
      </button>
    </div>
</dialog>

<style>
  .modal::backdrop { background: rgba(0, 0, 0, 0.6); }
  .modal {
    margin: auto;
    color: inherit;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    max-width: 360px;
    width: 100%;
  }
  .modal h3 {
    margin: 0 0 8px 0;
    font-size: 1.1rem;
  }
  .modal-desc {
    margin: 0 0 20px 0;
    font-size: 0.875rem;
    color: var(--text-dim);
  }
  .form-group {
    margin-bottom: 16px;
  }
  .form-group label, #currency-label {
    display: block;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-dim);
    margin-bottom: 6px;
  }
  .form-group input {
    width: 100%;
    padding: 10px 12px;
    font-size: 0.9rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    color: var(--text);
  }
  .currency-options {
    display: flex;
    gap: 8px;
  }
  .currency-opt {
    padding: 8px 16px;
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-dim);
    cursor: pointer;
  }
  .currency-opt.active {
    background: rgba(255, 255, 255, 0.08);
    color: var(--text);
    border-color: var(--primary);
  }
  .error-text {
    color: var(--color-loss);
    font-size: 0.8rem;
    margin: 0 0 12px 0;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 20px;
  }
  .btn-secondary, .btn-primary {
    padding: 10px 20px;
    font-size: 0.9rem;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
  }
  .btn-secondary {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--border);
    color: var(--text);
  }
  .btn-primary {
    background: var(--primary);
    border: 1px solid var(--primary);
    color: var(--fl-on-accent, #fff);
  }
</style>
