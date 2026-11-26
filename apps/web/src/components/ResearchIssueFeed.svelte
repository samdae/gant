<script lang="ts">
  import { articleUrl, timeLabel, type Issues } from "../lib/researchEvidence";
  import SourceGroup from "./SourceGroup.svelte";
  export let feed: Issues | null | undefined;
  export let title: string;
  export let lead = false;
  $: items = feed?.items ?? [];
  $: note = !feed
    ? "당시 수집 기록이 없습니다."
    : ({
        uncollected: "관측 시점까지 수집 기록이 없습니다.",
        empty: "시점 조건을 충족한 자료가 없습니다.",
        failed: "확인하지 못한 출처가 있습니다. 관측 시점까지 확보한 자료를 표시합니다.",
        available: items.length
          ? ""
          : "이 구분에 해당하는 당시 자료가 없습니다.",
      }[feed.status] ?? "수집 상태 미확인");
</script>

<section class="feed" class:lead>
  <SourceGroup {title} {items} known={Boolean(feed)} let:item>
    <svelte:fragment slot="notice">
      {#if note}<p class="note">{note}</p>{/if}
    </svelte:fragment>
    <article class="news">
      <small
        >{item.publisher || "매체 미기록"}{#if item.in_frozen_list && feed?.provenance !== "v3_archive_as_of"}
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
  </SourceGroup>
</section>

<style>
  .feed {
    padding: 2px 0 12px 16px;
    border-left: 1px solid var(--fl-line);
    min-width: 0;
  }
  .feed p {
    margin: 0;
  }
  .news {
    padding: 4px 0 10px;
    overflow-wrap: anywhere;
  }
  .news:not(:first-child) {
    border-block-start: 1px solid var(--fl-line);
    padding-block-start: 10px;
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
  @media (max-width: 760px) {
    .feed {
      border-left: 0;
      padding: 12px 0 4px;
    }
  }
</style>
