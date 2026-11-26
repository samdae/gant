<script lang="ts">
  import { onMount } from "svelte";
  import { pendingReads } from "../stores/pendingReads";

  let indicator: HTMLElement;
  let visible = false;

  onMount(() => {
    let nodes: HTMLElement[] = [];
    let timer: number | undefined;
    let mounted = true;
    const supported = typeof indicator.showPopover === "function";

    function busy() {
      const modal = document.activeElement?.closest("dialog:modal") ?? document.querySelector("dialog:modal");
      return nodes.some(node => node.getClientRects().length > 0 && (!modal || modal.contains(node)));
    }
    function sync() {
      if (busy()) {
        if (!visible && timer === undefined) {
          // A warm cache should never flash the indicator.
          timer = window.setTimeout(() => {
            timer = undefined;
            if (!busy()) return;
            visible = true;
            if (supported) indicator.showPopover();
          }, 140);
        }
      } else {
        clearTimeout(timer);
        timer = undefined;
        if (visible && supported) indicator.hidePopover();
        visible = false;
      }
    }
    function dialogChanged(event: Event) {
      if (!(event.target instanceof HTMLDialogElement)) return;
      sync();
      if (visible && supported && event.target.matches("dialog:modal")) {
        indicator.hidePopover();
        indicator.showPopover();
      }
    }
    const unsubscribe = pendingReads.subscribe(value => {
      nodes = value;
      // Actions may run while a route's subtree is being attached.
      queueMicrotask(() => { if (mounted) sync(); });
    });
    document.addEventListener("toggle", dialogChanged, true);
    window.addEventListener("resize", sync);
    return () => {
      mounted = false;
      unsubscribe();
      clearTimeout(timer);
      document.removeEventListener("toggle", dialogChanged, true);
      window.removeEventListener("resize", sync);
    };
  });
</script>

<span class="viewport-progress" class:visible bind:this={indicator} popover="manual" aria-hidden="true">
  <span class="ring"></span>
</span>

<style>
  .viewport-progress {
    display:none; position:fixed; inset:0; margin:auto; width:36px; height:36px;
    border:0; border-radius:50%; padding:0; z-index:11001; pointer-events:none;
    background:var(--fl-glass-raised,var(--fl-surface)); color:var(--fl-accent, #d5f65e);
    box-shadow:var(--fl-glass-shadow); align-items:center; justify-content:center;
  }
  .viewport-progress.visible { display:flex; }
  .viewport-progress::backdrop { background:transparent; pointer-events:none; }
  .ring {
    box-sizing:border-box; width:22px; height:22px; border:2px solid var(--fl-line, #44464b);
    border-top-color:currentColor; border-right-color:currentColor; border-radius:50%;
  }
  @media (prefers-reduced-motion:no-preference) {
    .visible .ring { animation:turn .8s linear infinite; }
    @keyframes turn { to { transform:rotate(360deg); } }
  }
</style>
