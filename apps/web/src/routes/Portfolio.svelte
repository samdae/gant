<script lang="ts">
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
      const response = await fetchPortfolioConfig() as { config?: unknown };
      if (id !== request) return;
      if (response?.config === null) {
        state = "empty";
        setup = true;
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
  onDestroy(() => { request += 1; });
</script>

{#if $viewMode !== "portfolio" || state === "ready"}
  <Dashboard />
{:else}
  <section class="page" id="page-portfolio-setup">
    <div class="page-container">
      <div class="page-header"><h2>포트폴리오</h2></div>
      {#if state === "loading"}
        <p role="status">계좌 설정을 확인하고 있습니다.</p>
      {:else if state === "error"}
        <div class="card card-body">
          <p role="alert">{error}</p>
          <button class="btn btn-secondary" on:click={() => load($viewMode)}>다시 조회</button>
        </div>
      {:else}
        <div class="card card-body">
          <h3>가상 포트폴리오 시작</h3>
          <p>이 콘솔에는 아직 포트폴리오가 없습니다. 초기 자본과 기준 통화를 설정하세요.</p>
          <button class="btn btn-primary" on:click={() => setup = true}>초기 자본·통화 설정</button>
        </div>
      {/if}
    </div>
  </section>
{/if}

{#if setup && $viewMode === "portfolio" && state === "empty"}
  <PortfolioActivateModal onClose={() => setup = false} onActivated={() => load($viewMode)} />
{/if}

<style>
  .card p { margin: .6rem 0 1rem; color: var(--text-secondary); }
</style>
