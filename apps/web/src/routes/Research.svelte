<script lang="ts">
  import { location } from "svelte-spa-router";
  import { isPublicViewer } from "../lib/workspace";
  import { onDestroy } from "svelte";

  let viewer: HTMLIFrameElement;
  let height = 1;
  let observer: ResizeObserver | undefined;

  $: caseId = isPublicViewer && $location.match(/^\/research\/([1-9]\d*)$/)?.[1];
  $: resultTab = isPublicViewer && ["/results", "/performance"].includes($location);
  $: source = "/research/?embedded=1" + (caseId ? "&case=" + caseId : "") + (resultTab ? "#results" : "");

  function fitViewer() {
    observer?.disconnect();
    const body = viewer.contentDocument?.body;
    if (!body) return;
    function measure() {
      if (body) height = Math.ceil(body.getBoundingClientRect().height);
    }
    measure();
    observer = new ResizeObserver(measure);
    observer.observe(body);
  }
  onDestroy(() => observer?.disconnect());
</script>

<iframe
  bind:this={viewer}
  title="예측 연구 관측 및 성과"
  src={source}
  style:height={height + "px"}
  on:load={fitViewer}
></iframe>

<style>
  iframe {
    display: block;
    width: 100%;
    border: 0;
    background: var(--fl-bg);
  }
</style>
