<script lang="ts">
  import SourceGroup from "./SourceGroup.svelte";
  import { articleUrl, timeLabel, type ReportNewsEvidence } from "../lib/researchEvidence";

  export let packet: ReportNewsEvidence;
  $: analyst = new Set(packet.analyst_cited);
  $: decision = new Set(packet.decision_cited);
  $: refs = new Map(packet.items.map(item => [item.url, item.ref]));
  $: articles = [...packet.items].sort((a, b) =>
    Number(decision.has(b.ref)) - Number(decision.has(a.ref)) ||
    Number(analyst.has(b.ref)) - Number(analyst.has(a.ref)));
</script>

<section class="news-input" aria-label="뉴스 분석가 입력">
  <h4>뉴스 분석가 입력</h4>
  <p>입력 기준 {timeLabel(packet.as_of)}</p>
  {#if packet.status === "unavailable"}
    <p>자료를 조회할 수 없어 이번 분석에는 보관된 기사 제목이 전달되지 않았습니다.</p>
  {:else}
    {#if packet.status === "partial"}<p>일부 출처의 수집이 완료되지 않았습니다.</p>{/if}
    {#if articles.length}
      <p class="citations">분석가 인용 {analyst.size}건 · 최종 판단 인용 {decision.size}건</p>
      <SourceGroup title="전달한 기사 제목" items={articles} let:item>
        {@const ref = refs.get(item.url) ?? ""}
        <article>
          <small>{ref} · {item.source === "last30days agent export" ? "last30days" : "뉴스"}
            {#if analyst.has(ref)} · 뉴스 분석가 인용{/if}{#if decision.has(ref)} · 최종 판단 인용{/if}</small>
          {#if articleUrl(item.url)}<a href={articleUrl(item.url)} target="_blank" rel="noopener noreferrer">{item.title}</a>
          {:else}<strong>{item.title}</strong>{/if}
          <small>{item.publisher} · 공개 {item.published_day ? item.published_day + " (시간 미상)" : timeLabel(item.published_at)}
            · 최초 관측 {timeLabel(item.first_seen_at)}</small>
        </article>
      </SourceGroup>
    {:else}
      <p>입력 기준 시각까지 전달할 기사가 없었습니다.</p>
    {/if}
  {/if}
</section>

<style>
  .news-input { margin: .8rem 0 1rem; }
  h4 { margin: 0; color: var(--fl-ink); font-size: 1rem; }
  p, small { color: var(--fl-muted); font-size: .86rem; line-height: 1.5; }
  p { margin: .25rem 0; }
  .citations { margin-bottom: .55rem; color: var(--fl-ink); }
  article { padding: .45rem 0 .65rem; overflow-wrap: anywhere; max-width: 76ch; }
  article:not(:first-child) { border-block-start: 1px solid var(--fl-line); }
  a { color: var(--fl-forecast); text-underline-offset: .15em; }
  small { display: block; }
</style>
