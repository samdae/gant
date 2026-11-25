<script context="module" lang="ts">
  let instanceCount = 0;
</script>

<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";

  export let id: string | undefined = undefined;
  export let value = "";
  export let options: { value: string; label: string }[] = [];
  export let ariaLabel: string | undefined = undefined;
  export let placeholder = "선택";
  export let compact = false;
  export let minimal = false;
  export let disabled = false;
  export let panelAlign: "start" | "end" = "start";

  const listId = "gant-options-" + ++instanceCount;
  const dispatch = createEventDispatcher<{ change: string }>();
  let trigger: HTMLButtonElement;
  let panel: HTMLDivElement;
  let open = false;
  let active = 0;
  let search = "";
  let lastTyped = 0;
  $: selected = options.find(option => option.value === value);
  $: if (open && (disabled || options.length === 0)) open = false;

  function place() {
    if (!open || !panel || !trigger) return;
    const bounds = trigger.getBoundingClientRect();
    const gap = 5, margin = 8;
    const view = window.visualViewport;
    const top = view?.offsetTop ?? 0, left = view?.offsetLeft ?? 0;
    const width = view?.width ?? document.documentElement.clientWidth;
    const height = view?.height ?? window.innerHeight;
    const below = height + top - bounds.bottom - margin - gap;
    const above = bounds.top - top - margin - gap;
    const flip = below < Math.min(288, panel.scrollHeight + 2) && above > below;
    panel.style.maxHeight = Math.max(24, Math.min(288, flip ? above : below)) + "px";
    panel.style.minWidth = Math.min(width - margin * 2, bounds.width) + "px";
    panel.style.maxWidth = width - margin * 2 + "px";
    const x = panelAlign === "end" ? bounds.right - panel.offsetWidth : bounds.left;
    panel.style.left = Math.max(left + margin, Math.min(x, left + width - margin - panel.offsetWidth)) + "px";
    panel.style.top = (flip ? bounds.top - gap - panel.offsetHeight : bounds.bottom + gap) + "px";
  }

  function attach(node: HTMLDivElement) {
    // Top-layer placement preserves the owning dialog and escapes overflow clipping.
    node.setAttribute("popover", "manual");
    node.showPopover?.();
    function outside(event: Event) {
      if (!node.contains(event.target as Node) && !trigger.contains(event.target as Node)) open = false;
    }
    document.addEventListener("pointerdown", outside, true);
    document.addEventListener("focusin", outside);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    window.visualViewport?.addEventListener("resize", place);
    window.visualViewport?.addEventListener("scroll", place);
    return { destroy() {
      document.removeEventListener("pointerdown", outside, true);
      document.removeEventListener("focusin", outside);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      window.visualViewport?.removeEventListener("resize", place);
      window.visualViewport?.removeEventListener("scroll", place);
    }};
  }

  function reveal() {
    const row = panel?.children[active] as HTMLElement | undefined;
    if (!row) return;
    if (row.offsetTop < panel.scrollTop) panel.scrollTop = row.offsetTop;
    if (row.offsetTop + row.offsetHeight > panel.scrollTop + panel.clientHeight)
      panel.scrollTop = row.offsetTop + row.offsetHeight - panel.clientHeight;
  }

  async function show() {
    if (disabled || !options.length || open) return;
    active = Math.max(0, options.findIndex(option => option.value === value));
    open = true;
    await tick();
    place();
    reveal();
  }

  function choose(index: number) {
    const option = options[index];
    if (!option) return;
    open = false;
    trigger.focus({ preventScroll: true });
    value = option.value;
    dispatch("change", value);
  }

  function keyboard(event: KeyboardEvent) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.isComposing) return;
    const key = event.key;
    if (key === "Tab") { open = false; return; }
    if (key === "Escape" && !open) return;
    if (!["ArrowDown", "ArrowUp", "Home", "End", "Enter", " ", "Escape"].includes(key) && key.length !== 1) return;
    event.preventDefault();
    event.stopPropagation();
    if (key === "Escape") { open = false; return; }
    if (key === "Enter" || key === " ") {
      if (open) choose(active); else show();
      return;
    }
    const previouslyOpen = open;
    show();
    if (key === "Home") active = 0;
    else if (key === "End") active = options.length - 1;
    else if (key === "ArrowUp" || key === "ArrowDown") {
      if (previouslyOpen) active = Math.min(options.length - 1, Math.max(0, active + (key === "ArrowDown" ? 1 : -1)));
    } else {
      const now = performance.now();
      search = (now - lastTyped < 650 ? search : "") + key.toLocaleLowerCase();
      lastTyped = now;
      const prefix = [...search].every(letter => letter === search[0]) ? search[0] : search;
      for (let offset = 1; offset <= options.length; offset++) {
        const i = (active + offset) % options.length;
        if (options[i].label.toLocaleLowerCase().startsWith(prefix)) { active = i; break; }
      }
    }
    tick().then(reveal);
  }
</script>

<div class="select-menu" class:compact class:minimal>
  <button {id} type="button" role="combobox" class="select-trigger"
    aria-label={ariaLabel} aria-expanded={open} aria-controls={listId} aria-haspopup="listbox"
    aria-activedescendant={open ? listId + "-" + active : undefined}
    disabled={disabled || !options.length} bind:this={trigger}
    on:keydown={keyboard} on:click={() => open ? open = false : show()}>
    <span>{selected?.label ?? placeholder}</span>
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
  </button>
  {#if open}
    <div class="choice-list" id={listId} role="listbox" aria-label={ariaLabel ?? placeholder}
      use:attach bind:this={panel}>
      {#each options as option, i}
        <div class="select-option" role="option" tabindex="-1" id={listId + "-" + i} aria-selected={option.value === value}
          class:highlight={i === active} on:pointermove={() => active = i}
          on:mousedown|preventDefault on:click={() => choose(i)} on:keydown={keyboard}>
          <span>{option.label}</span>
          {#if option.value === value}<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="m3 8 3 3 7-7" /></svg>{/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .select-menu { min-width:0; max-width:100%; }
  .select-menu .select-trigger {
    box-sizing:border-box; display:inline-flex; align-items:center; justify-content:space-between;
    gap:var(--fl-control-gap,8px); width:100%; min-width:0; height:var(--fl-control-height,40px);
    padding:0 var(--fl-control-padding-inline,12px); border:1px solid var(--fl-line,var(--border)); border-radius:var(--fl-control-radius,7px);
    background:var(--fl-backdrop,var(--bg-header)); color:var(--fl-ink,var(--text));
    font:inherit; font-size:14px; cursor:pointer;
  }
  .select-trigger span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .select-menu svg { flex:none; fill:none; stroke:currentColor; stroke-width:1.7; stroke-linecap:round; stroke-linejoin:round; }
  .select-trigger:focus-visible { outline:2px solid var(--fl-accent,var(--primary)); outline-offset:2px; }
  .select-trigger:disabled { opacity:.55; cursor:default; }
  .select-trigger[aria-expanded=true] svg { transform:rotate(180deg); }
  .choice-list {
    position:fixed; inset:auto; z-index:11000; margin:0; padding:4px; box-sizing:border-box;
    width:max-content; overflow:auto; overscroll-behavior:contain;
    background:var(--fl-surface,var(--bg-header)); color:var(--fl-ink,var(--text));
    border:1px solid var(--fl-line,var(--border)); border-radius:var(--fl-control-radius,7px);
    box-shadow:0 8px 22px #0006; font-size:14px;
  }
  .choice-list [role=option] { display:flex; align-items:center; justify-content:space-between; gap:16px;
    min-height:var(--fl-control-height,40px); box-sizing:border-box; padding:6px 10px; border-radius:4px; cursor:pointer; }
  .choice-list .highlight { background:var(--fl-surface-subtle,var(--bg-card)); outline:1px solid var(--fl-muted,var(--border)); outline-offset:-1px; }
  .choice-list [aria-selected=true] svg { color:var(--fl-accent,var(--primary)); }
  @media(max-width:767px){ .select-menu .select-trigger,.choice-list [role=option] { min-height:44px; } }
</style>
