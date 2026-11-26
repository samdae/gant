<script lang="ts">
  import PendingState from "../components/PendingState.svelte";
  import { isForecastLab, isPublicViewer } from "../lib/workspace";
  import { onDestroy } from "svelte";
  import { location } from "svelte-spa-router";
  import Dashboard from "./Dashboard.svelte";
  import PortfolioActivateModal from "../components/PortfolioActivateModal.svelte";
  import { fetchPortfolioConfig } from "../lib/api/endpoints";
  import { formatErrorMessage } from "../lib/utils/format";
  import { viewMode } from "../stores/mode";

  let state: "loading" | "empty" | "ready" | "error" = "loading";
  let error = "";
  let setup = false;
  let request = 0;

  async function load(mode: string) {
    const id = ++request;
    setup = false;
    if (mode !== "portfolio") return;
    state = "loading";
    try {
      const response = (await fetchPortfolioConfig()) as { config?: unknown };
      if (id !== request) return;
      if (response?.config === null) {
        state = "empty";
        setup =
          !isPublicViewer &&
          (!isForecastLab ||
            new URLSearchParams(window.location.hash.split("?")[1]).get(
              "setup",
            ) === "1");
      } else if (response?.config && typeof response.config === "object") {
        state = "ready";
      } else {
        throw new Error("포트폴리오 설정 응답을 확인할 수 없습니다.");
      }
    } catch (e) {
      if (id !== request) return;
      error = formatErrorMessage(e, "포트폴리오 설정을 불러오지 못했습니다.");
      state = "error";
    }
  }

  $: if ($location === "/portfolio") viewMode.set("portfolio");
  $: load($viewMode);
  onDestroy(() => {
    request += 1;
  });
</script>

{#if $viewMode !== "portfolio" || state === "ready"}
  <Dashboard />
{:else}
  <section class="page" id="page-portfolio-setup">
    <div class="page-container">
      <div class="page-header"><h2>포트폴리오</h2></div>
      {#if state === "loading"}
        <p><PendingState label="계좌 설정을 확인하고 있습니다."/></p>
      {:else if state === "error"}
        <div class="card card-body">
          <p role="alert">{error}</p>
          <button class="btn btn-secondary" on:click={() => load($viewMode)}
            >다시 조회</button
          >
        </div>
      {:else if isPublicViewer}
        <section class="account-register">
          <div class="register-title">
            <svg aria-hidden="true" viewBox="0 0 48 48"><path d="M8 17v-5c0-2 1-3 3-3h24v8M9 16h30a2 2 0 0 1 2 2v18a2 2 0 0 1-2 2H10a3 3 0 0 1-3-3V19a3 3 0 0 1 2-3Z"/><path d="M41 23h-9a3 3 0 0 0 0 6h9"/></svg>
            <h3>모의 계좌 미개설</h3>
            <p>초기 자본이 설정되면 잔액과 보유 종목을 확인할 수 있습니다.</p>
          </div>
          <nav aria-label="관련 거래 기록">
            <a href="#/research">예측 사례 읽기</a>
            <a href="#/dashboard" on:click={() => viewMode.set("analysis")}
              >종목별 대시보드</a
            >
            <a href="#/positions">보유·종료 명세</a>
          </nav>
        </section>
      {:else}
        <div class="card card-body portfolio-welcome">
          {#if isForecastLab}
            <span class="desk-wallet" aria-hidden="true"
              ><svg
                viewBox="0 0 48 48"
                fill="none"
                stroke="currentColor"
                stroke-width="2.2"
                stroke-linecap="round"
                stroke-linejoin="round"
                ><path d="M8 16V12a3 3 0 0 1 3-3h25v7" /><rect
                  x="7"
                  y="15"
                  width="34"
                  height="24"
                  rx="4"
                /><path d="M41 23H30v8h11" /><circle
                  cx="33.5"
                  cy="27"
                  r="1"
                  fill="currentColor"
                  stroke="none"
                /></svg
              ></span
            >
          {/if}
          <div class="setup-action">
            <h3>가상 포트폴리오 시작</h3>
            <p>
              이 콘솔에는 아직 포트폴리오가 없습니다. 초기 자본과 기준 통화를
              설정하세요.
            </p>
            <button class="btn btn-primary" on:click={() => (setup = true)}
              >초기 자본·통화 설정</button
            >
            {#if isForecastLab}<a class="setup-research" href="#/research"
                >예측 연구 먼저 보기</a
              >{/if}
          </div>
          {#if isForecastLab}
            <dl class="desk-setup-facts">
              <div>
                <dt>기준 통화</dt>
                <dd>원화(KRW) · 미국 달러(USD)</dd>
              </div>
              <div>
                <dt>운용 방식</dt>
                <dd>공유 자금으로 종목 간 비중 조정</dd>
              </div>
              <div>
                <dt>변경 권한</dt>
                <dd>관리자 인증 필요</dd>
              </div>
            </dl>
          {/if}
        </div>
      {/if}
    </div>
  </section>
{/if}

{#if setup && $viewMode === "portfolio" && state === "empty"}
  <PortfolioActivateModal
    onClose={() => (setup = false)}
    onActivated={() => load($viewMode)}
  />
{/if}

<style>
  .account-register { display:grid; grid-template-columns:minmax(0,1.25fr) minmax(160px,.75fr); gap:20px 44px; max-width:850px; padding:clamp(22px,4vw,44px); background:var(--fl-surface); border:1px solid var(--fl-line); border-radius:var(--fl-radius,16px); color:var(--fl-ink); }
  .register-title svg { width:34px; height:34px; fill:none; stroke:var(--fl-accent); stroke-width:1.8; stroke-linejoin:round; stroke-linecap:round; margin-bottom:16px; }
  .register-title h3 { font:700 1.6rem/1.25 var(--fl-display); letter-spacing:-.03em; margin:0; }
  .account-register p { font-size:.92rem; margin:.6rem 0 0; color:var(--fl-muted); }
  .account-register nav { display:grid; align-content:center; min-width:0; }
  .account-register nav a { display:flex; justify-content:space-between; align-items:center; min-height:44px; border-bottom:1px solid var(--fl-line); text-decoration:none; }
  .account-register nav a:last-child { border:0; }
  .account-register nav a::after { content:""; width:7px; height:7px; border:solid currentColor; border-width:1.5px 1.5px 0 0; transform:rotate(45deg); margin-right:3px; }
  @media(max-width:620px) { .account-register { grid-template-columns:1fr; } .account-register nav { border-top:1px solid var(--fl-line); } }
  .account-register a,
  .setup-research {
    color: var(--fl-accent, #d5f65e);
    font-weight: 600;
    font-size: 0.86rem;
    text-underline-offset: 0.15em;
  }
  .setup-research {
    display: inline-block;
    margin: 0.45rem 0.75rem;
  }
  .card p {
    margin: 0.6rem 0 1rem;
    color: var(--text-secondary);
  }
</style>
