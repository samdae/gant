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
        available: items.length ? "" : "이 구분에 해당하는 당시 자료가 없습니다.",
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
      <small>{item.publisher || "매체 미기록"}{#if item.in_frozen_list} · 동결 목록에 포함{/if}</small>
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
          최초 관측 {timeLabel(item.first_seen_at)} · {item.source || (lead ? "last30days" : title)}<br
          />사례 기준 {timeLabel(feed?.as_of)} · 최근 수집 {timeLabel(
            feed?.collected_at,
          )}
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
    padding: 10px 0;
    border-top: 1px solid #ddd8d0;
    min-width: 0;
  }
  .feed header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 10px;
  }
  .feed h4,
  .feed p {
    margin: 0;
  }
  .feed h4 {
    font-size: 0.88rem;
    color: #4b4541;
  }
  .lead h4 {
    color: #852641;
  }
  .news {
    padding: 7px 0;
    overflow-wrap: anywhere;
  }
  .news strong,
  .news small {
    display: block;
  }
  .news strong {
    font-size: 0.92rem;
    line-height: 1.4;
  }
  .feed small,
  .note,
  .feed summary,
  .feed details p {
    color: #685f59;
    font-size: 0.76rem;
  }
  .feed summary {
    cursor: pointer;
  }
  .news a {
    color: inherit;
    text-decoration: none;
  }
  .news a:hover {
    text-decoration: underline;
  }
  .feed button {
    padding: 3px 0;
    background: none;
    border: 0;
    font: inherit;
    color: #852641;
    font-size: 0.78rem;
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }
</style>
