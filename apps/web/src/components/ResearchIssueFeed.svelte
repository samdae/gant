<script lang="ts">
  import { articleUrl, timeLabel, type Issues } from "../lib/researchEvidence";
  export let feed: Issues | null | undefined;
  export let title: string;
  export let lead = false;
  let expanded = false;
  $: items = feed?.items ?? [];
  $: note = !feed
    ? "당시 수집 기록이 없습니다."
    : ({
        uncollected: "관측 시점까지 수집 기록이 없습니다.",
        empty: "시점 조건을 충족한 자료가 없습니다.",
        failed: "최근 수집에 실패했습니다. 이전에 확보한 자료만 표시합니다.",
        available: items.length
          ? ""
          : "이 구분에 해당하는 당시 자료가 없습니다.",
      }[feed.status] ?? "수집 상태 미확인");
</script>

<section class="feed" class:lead>
  <header>
    <h4>{title}</h4>
    {#if feed}<small>{items.length}건</small>{/if}
  </header>
  {#if note}<p class="note">{note}</p>{/if}
  {#each expanded ? items : items.slice(0, 1) as item}
    <article class="news">
      <small
        >{item.publisher || "매체 미기록"}{#if item.in_frozen_list}
          · 동결 목록에 포함{/if}</small
      >
      <strong
        >{#if articleUrl(item.url)}<a
            href={articleUrl(item.url)}
            target="_blank"
            rel="noopener noreferrer">{item.title} ↗</a
          >{:else}{item.title}{/if}</strong
      >
      <small
        >공개 {item.published_precision === "day" && item.published_day
          ? item.published_day + " (시간 미상)"
          : timeLabel(item.published_at)}</small
      >
      <details>
        <summary>수집 근거</summary>
        <p>
          최초 관측 {timeLabel(item.first_seen_at)} · {item.source ||
            (lead ? "last30days" : title)}<br />사례 기준 {timeLabel(
            feed?.as_of,
          )} · 최근 수집 {timeLabel(feed?.collected_at)}
        </p>
      </details>
    </article>
  {/each}
  {#if items.length > 1}<button
      aria-expanded={expanded}
      on:click={() => (expanded = !expanded)}
      >{expanded ? "접기" : "나머지 " + (items.length - 1) + "건 보기"}</button
    >{/if}
</section>

<style>
  .feed {
    padding: 2px 0 12px 16px;
    border-left: 1px solid var(--fl-line);
    min-width: 0;
  }
  .feed header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 8px;
    padding: 0 0 6px;
    border-bottom: 1px solid var(--fl-line);
  }
  .feed h4,
  .feed p {
    margin: 0;
  }
  .feed h4 {
    font-size: 0.9rem;
    color: var(--fl-ink);
    font-weight: 650;
  }
  .feed header small {
    font-variant-numeric: tabular-nums;
  }
  .news {
    padding: 10px 0;
    overflow-wrap: anywhere;
    border-bottom: 1px solid var(--fl-line);
  }
  .news strong,
  .news small {
    display: block;
  }
  .news strong {
    font-size: 1.05rem;
    line-height: 1.45;
    margin: 3px 0;
  }
  .feed small,
  .feed details,
  .note {
    color: var(--fl-muted);
    font-size: 0.78rem;
  }
  .feed summary {
    cursor: pointer;
    padding: 4px 0;
  }
  .news a {
    color: var(--fl-ink);
    text-decoration: none;
  }
  .news a:hover,
  .news a:focus-visible {
    color: var(--fl-accent);
    text-decoration: underline;
  }
  .feed button {
    padding: 8px 0;
    background: none;
    border: 0;
    font: 600 0.8rem var(--fl-font, sans-serif);
    color: var(--fl-accent);
    cursor: pointer;
  }
  @media (max-width: 760px) {
    .feed {
      border-left: 0;
      padding: 12px 0 4px;
    }
  }
</style>
