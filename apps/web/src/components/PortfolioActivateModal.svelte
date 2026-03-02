<script lang="ts">
  import { createPortfolioConfig } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { portfolioRefreshTrigger } from "../stores/mode";

  export let onClose: () => void;
  export let onActivated: () => void;

  let capital = 100000000;
  let currency: "KRW" | "USD" = "KRW";
  let loading = false;
  let error = "";

  async function handleActivate() {
    if (capital <= 0) {
      error = "초기 자본을 입력해 주세요.";
      return;
    }
    loading = true;
    error = "";
    try {
      await createPortfolioConfig({
        initial_capital: capital,
        base_currency: currency,
        fee_enabled: true,
        reset_fund_to_initial: true,
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

<div class="modal-backdrop" on:click={onClose} on:keydown={(e) => e.key === "Escape" && onClose()} role="button" tabindex="-1">
  <div class="modal" on:click|stopPropagation>
    <h3>포트폴리오 모드 활성화</h3>
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
      <label>기준 통화</label>
      <div class="currency-options">
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
        {loading ? "처리 중..." : "활성화"}
      </button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 16px;
  }
  .modal {
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
  .form-group label {
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
    color: #fff;
  }
</style>
