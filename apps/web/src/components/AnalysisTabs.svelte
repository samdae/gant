<script lang="ts">
  import { location } from "svelte-spa-router";

  type TabItem = {
    label: string;
    route: string;
    description: string;
  };

  const tabs: TabItem[] = [
    {
      label: "레포트",
      route: "/reports",
      description: "일정에 등록된 종목을 매일 장 마감 후 분석한 결과입니다. 각 사이클의 분석 에이전트들의 의견과 매매결정 에이전트의 최종 결정을 확인할 수 있습니다.",
    },
    {
      label: "매매검증",
      route: "/reflections",
      description: "거래 종료 시 자동으로 생성되는 회고 기록입니다. 승패 결과와 핵심 교훈이 정리되며, 이 데이터는 RAG 경험 저장소에 반영되어 이후 매매결정 에이전트의 판단에 활용됩니다.",
    },
    {
      label: "회고분석",
      route: "/retrospective",
      description: "매매의 판단 근거를 복기하여 사후 평가합니다. 포지션을 선택하고 분석을 요청하면, 각 사이클에서 매매결정 에이전트가 내린 결정과 근거데이터로 AI가 검증합니다.",
    },
  ];

  const getBaseRoute = (loc: string): string => {
    const parts = loc.split("/");
    return parts.length > 1 && parts[1] ? `/${parts[1]}` : "/";
  };

  $: activeBase = getBaseRoute($location);
  $: activeTab = tabs.find((t) => t.route === activeBase) || tabs[0];
</script>

<div class="analysis-tabs">
  <div class="analysis-tab-row">
    <div class="analysis-tab-bar">
      {#each tabs as tab}
        <a
          href={`#${tab.route}`}
          class="analysis-tab"
          class:active={tab.route === activeBase}
        >
          {tab.label}
        </a>
      {/each}
    </div>
    <slot name="action" />
  </div>
  <p class="analysis-tab-desc">{activeTab.description}</p>
</div>

<style>
  .analysis-tabs {
    margin-bottom: 20px;
  }
  .analysis-tab-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 12px;
  }
  .analysis-tab-bar {
    display: flex;
    gap: 0;
  }
  .analysis-tab {
    padding: 10px 16px;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-dim);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: color 0.15s, border-color 0.15s;
    cursor: pointer;
  }
  .analysis-tab:hover {
    color: var(--text-secondary);
  }
  .analysis-tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .analysis-tab-desc {
    font-size: 0.75rem;
    color: var(--text-dim);
    line-height: 1.6;
    margin: 0;
    padding: 0 2px;
  }
</style>
