<script lang="ts">
  import PendingState from "./PendingState.svelte";
  import { onMount, onDestroy } from "svelte";
  import {
    articleUrl,
    timeLabel,
    researchGet,
    type Issues,
  } from "../lib/researchEvidence";
  export let id: number;
  export let ticker: string;
  type Archive = {
    id: number;
    ticker: string;
    as_of: string;
    issues?: Issues;
    last30days?: Issues;
  };
  let archive: Archive | null = null;
  let error = "";
  let expanded: Record<string, boolean> = {};
  let controller: AbortController;
  async function load(refresh = false) {
    controller?.abort();
    const req = new AbortController();
    controller = req;
    error = "";
    try {
      const data = await researchGet<Archive>(
        "report-sources/" + id,
        req.signal,
        {refresh},
      );
      if (data.id !== id || data.ticker.toUpperCase() !== ticker.toUpperCase())
        throw Error();
      if (!req.signal.aborted) archive = data;
    } catch (e) {
      if (!req.signal.aborted) error = e instanceof Error ? e.message : "당시 자료를 확인하지 못했습니다.";
    }
  }
  onMount(() => {
    load();
  });
  onDestroy(() => controller?.abort());
  const notices: Record<string, string> = {
    uncollected: "이 회차 발행 전 수집 기록이 없습니다.",
    empty: "수집했지만 기간과 시점 조건을 충족한 자료가 없습니다.",
    failed: "확인하지 못한 출처가 있습니다. 발행 시점까지 확보한 자료를 표시합니다.",
  };
</script>

<section class="archive" aria-label="리포트 발행 시점의 30일 자료">
  <h3>발행 전 30일 자료</h3>
  {#if error}<p role="alert">
      {error} <button on:click={() => load(true)}>다시 조회</button
      >
    </p>
  {:else if !archive}<p><PendingState label="수집 기록을 확인하는 중입니다."/></p>
  {:else}
    <p>
      {timeLabel(archive.as_of)} 발행 시점까지 {archive.issues?.provenance === "v3_archive_as_of" || archive.last30days?.provenance === "v3_archive_as_of" ? "같은 종목에 대해 별도로 수집된 참고 자료입니다." : "보관된 자료입니다."} 이 자료가 매매
      판단에 사용됐는지는 기록되지 않았습니다.
    </p>
    {#each [{ label: "last30days 조사 자료", data: archive.last30days }, { label: "뉴스", data: archive.issues }] as group}
      {@const items = group.data?.items || []}
      <section class="source">
        <h4>
          {group.label}
          <span>{group.data ? items.length + "건" : "확인 불가"}</span>
        </h4>
        {#if notices[group.data?.status || ""]}<p>
            {notices[group.data?.status || ""]}
          </p>{/if}
        {#each expanded[group.label] ? items : items.slice(0, 1) as item}
          <div class="item">
            {#if articleUrl(item.url)}<a
                href={articleUrl(item.url)}
                target="_blank"
                rel="noopener noreferrer">{item.title}</a
              >{:else}<strong>{item.title}</strong>{/if}
            <small
              >{item.publisher} · 공개 {item.published_precision === "day"
                ? item.published_day + " (시간 미상)"
                : timeLabel(item.published_at)} · 최초 관측 {timeLabel(
                item.first_seen_at,
              )}</small
            >
          </div>
        {/each}
        {#if items.length > 1}
          <button
            aria-expanded={Boolean(expanded[group.label])}
            on:click={() =>
              (expanded = {
                ...expanded,
                [group.label]: !expanded[group.label],
              })}
          >
            {expanded[group.label]
              ? "접기"
              : "나머지 " + (items.length - 1) + "건 보기"}
          </button>
        {/if}
      </section>
    {/each}
  {/if}
</section>

<style>
  .archive {
    background: var(--fl-surface, #202124);
    color: var(--fl-ink, #f4f2e9);
    border-block: 1px solid var(--fl-line, #3b3d41);
    margin: 1rem 0;
    padding: 1rem;
  }
  h3 {
    margin: 0;
    font-size: 1.08rem;
  }
  p,
  small {
    color: var(--fl-muted, #b5b4ad);
    font-size: 0.86rem;
    line-height: 1.5;
  }
  .source {
    padding: 0.5rem 0;
    border-top: 1px solid var(--fl-line, #3b3d41);
  }
  h4 {
    margin: 0;
    font-weight: 600;
  }
  h4 span {
    font-weight: normal;
  }
  .item {
    padding: 0.65rem 0;
    max-width: 76ch;
    overflow-wrap: anywhere;
  }
  a {
    color: var(--fl-forecast, #c3a9ff);
    text-underline-offset: 0.15em;
  }
  small {
    display: block;
  }
</style>
