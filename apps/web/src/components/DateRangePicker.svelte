<script lang="ts">
  import { createEventDispatcher, tick } from "svelte";
  import WorkspaceIcon from "./WorkspaceIcon.svelte";
  import {
    currentDay,
    dateName,
    monthDays,
    rangeLabel,
    shiftDays,
    shiftMonths,
    validDay,
    type DateRange,
  } from "../lib/researchDates";
  export let from = "";
  export let to = "";
  const dispatch = createEventDispatcher<{ change: DateRange }>();
  let modal: HTMLDialogElement;
  let trigger: HTMLButtonElement;
  let yearField: HTMLInputElement;
  let today = currentDay();
  let focusDay = today;
  let first = "";
  let hover = "";
  $: preview = hover || focusDay;
  $: low = first ? (first <= preview ? first : preview) : from;
  $: high = first ? (first > preview ? first : preview) : to;
  let jump = false;
  let targetYear = new Date().getFullYear();
  $: page = monthDays(focusDay);
  $: label = rangeLabel({ from, to });

  async function focusCalendar(value: string) {
    hover = "";
    focusDay = value;
    await tick();
    modal
      .querySelector<HTMLButtonElement>('[data-day="' + value + '"]')
      ?.focus();
  }
  function open() {
    today = currentDay();
    hover = "";
    first = "";
    jump = false;
    focusDay = validDay(from) ? from : validDay(to) ? to : today;
    modal.showModal();
    focusCalendar(focusDay);
  }
  function handleDialogKey(event: KeyboardEvent) {
    if (!modal?.open || event.key !== "Escape") return;
    event.preventDefault();
    event.stopPropagation();
    dismiss();
  }
  function dismiss() {
    modal.close();
    trigger.focus({ preventScroll: true });
  }
  function commit(next: DateRange) {
    dismiss();
    if (next.from !== from || next.to !== to) dispatch("change", next);
  }
  function choose(day: string) {
    if (!first) {
      first = day;
      focusCalendar(day);
    } else {
      commit(day < first ? { from: day, to: first } : { from: first, to: day });
    }
  }
  function navigate(e: KeyboardEvent, day: string) {
    const idx = page.days.indexOf(day);
    const weekday = (page.offset + idx) % 7;
    const offsets: Record<string, number> = {
      ArrowLeft: -1,
      ArrowRight: 1,
      ArrowUp: -7,
      ArrowDown: 7,
      Home: -weekday,
      End: 6 - weekday,
    };
    if (typeof offsets[e.key] === "number") {
      e.preventDefault();
      focusCalendar(shiftDays(day, offsets[e.key]));
    } else if (e.key === "PageUp" || e.key === "PageDown") {
      e.preventDefault();
      focusCalendar(
        shiftMonths(day, (e.key === "PageUp" ? -1 : 1) * (e.shiftKey ? 12 : 1)),
      );
    }
  }
  async function showJump() {
    targetYear = page.year;
    jump = true;
    await tick();
    yearField.focus();
    yearField.select();
  }
  function jumpMonth(month: number) {
    if (!Number.isInteger(targetYear) || targetYear < 1 || targetYear > 9999) {
      yearField.reportValidity();
      return;
    }
    jump = false;
    focusCalendar(
      String(targetYear).padStart(4, "0") +
        "-" +
        String(month).padStart(2, "0") +
        "-01",
    );
  }
</script>

<button
  class="range-trigger"
  type="button"
  bind:this={trigger}
  aria-haspopup="dialog"
  aria-label={"관측 기간: " + label}
  on:click={open}
>
  <svg
    viewBox="0 0 20 20"
    aria-hidden="true"
    width="17"
    height="17"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    ><rect x="3" y="5" width="14" height="12" rx="2" /><path
      d="M6 3v4m8-4v4M3 9h14"
    /></svg
  ><span>{label}</span>
</button>
<svelte:window on:keydown={handleDialogKey} />
<dialog
  class="range-dialog"
  bind:this={modal}
  aria-label="관측 기간 선택"
  on:cancel|preventDefault|stopPropagation={dismiss}
>
  <header>
    <h3>관측 기간</h3>
    <button type="button" aria-label="관측 기간 선택 닫기" on:click={dismiss}
      >닫기</button
    >
  </header>
  {#if from || to}<p class="current-range">적용 기간 · {label}</p>{/if}
  <p class="instruction" aria-live="polite">
    {first
      ? dateName(first) + " 선택 · 두 번째 날짜를 선택하세요."
      : "범위로 볼 두 날짜를 선택하세요."}
  </p>
  {#if jump}
    <div class="year">
      <label
        >연도 <input
          type="number"
          bind:this={yearField}
          bind:value={targetYear}
          min="1"
          max="9999"
          step="1"
          required
        /></label
      >
    </div>
    <div class="months">
      {#each Array.from({ length: 12 }, (_, i) => i + 1) as month}<button
          type="button"
          on:click={() => jumpMonth(month)}>{month}월</button
        >{/each}
    </div>
  {:else}
    <div class="navigation">
      <button
        type="button"
        aria-label="이전 달"
        disabled={focusDay.startsWith("0001-01")}
        on:click={() => (focusDay = shiftMonths(focusDay, -1))}
        ><span class="previous"><WorkspaceIcon name="chevron" size={16} /></span
        ></button
      >
      <button type="button" aria-label="연도와 월 선택" on:click={showJump}
        >{page.year}년 {page.month}월
        <span class="down"><WorkspaceIcon name="chevron" size={15} /></span
        ></button
      >
      <button
        type="button"
        aria-label="다음 달"
        disabled={focusDay.startsWith("9999-12")}
        on:click={() => (focusDay = shiftMonths(focusDay, 1))}
        ><WorkspaceIcon name="chevron" size={16} /></button
      >
    </div>
    <div
      class="days"
      role="group"
      aria-label={page.year + "년 " + page.month + "월 날짜"}
    >
      {#each ["일", "월", "화", "수", "목", "금", "토"] as weekday}<span
          class="weekday"
          aria-hidden="true">{weekday}</span
        >{/each}
      {#each Array(page.offset) as _}<span></span>{/each}
      {#each page.days as day}
        <button
          type="button"
          data-day={day}
          aria-label={dateName(day)}
          aria-current={day === today ? "date" : undefined}
          aria-pressed={first ? day === first : day === from || day === to}
          class:inside={low && high && day > low && day < high}
          class:preview-end={first && day === preview && day !== first}
          on:pointerenter={() => {
            if (first) hover = day;
          }}
          on:pointerleave={() => (hover = "")}
          tabindex={day === focusDay ? 0 : -1}
          on:keydown={(e) => navigate(e, day)}
          on:click={() => choose(day)}>{Number(day.slice(-2))}</button
        >
      {/each}
    </div>
  {/if}
  <footer>
    <button
      type="button"
      disabled={!from && !to}
      on:click={() => commit({ from: "", to: "" })}>기간 초기화</button
    ><button type="button" on:click={dismiss}>취소</button>
  </footer>
</dialog>

<style>
  .range-trigger,
  .range-dialog {
    color: var(--fl-ink);
    font: inherit;
  }
  .range-trigger {
    display: flex;
    align-items: center;
    gap: 8px;
    text-align: left;
    background: var(--fl-surface-subtle);
    border: 1px solid var(--fl-line);
    border-radius: var(--fl-control-radius, 7px);
    min-height: var(--fl-control-height, 40px);
    padding: 5px 12px;
    cursor: pointer;
  }
  .range-trigger > span {
    white-space: nowrap;
  }
  .range-trigger svg {
    color: var(--fl-muted);
    flex: none;
  }
  .range-dialog {
    width: min(340px, calc(100% - 20px));
    max-width: 100%;
    max-height: calc(100dvh - 18px);
    overflow: auto;
    margin: auto;
    padding: 16px;
    background: var(--fl-surface);
    border: 1px solid var(--fl-line);
    border-radius: 12px;
    box-shadow: 0 10px 40px #0009;
    color-scheme: dark;
  }
  .range-dialog::backdrop {
    background: #0008;
  }
  .range-dialog header,
  .range-dialog footer,
  .navigation {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
  }
  .range-dialog h3,
  .instruction {
    margin: 0;
  }
  .instruction {
    padding: 6px 0;
    color: var(--fl-muted);
    font-size: 0.82rem;
  }
  .range-dialog button {
    min-height: 36px;
    padding: 4px 8px;
    color: inherit;
    background: transparent;
    border: 0;
    border-radius: 5px;
    font: inherit;
    cursor: pointer;
  }
  .range-dialog button:disabled {
    opacity: 0.45;
    cursor: default;
  }
  .range-dialog button:hover:not(:disabled),
  .days .inside {
    background: var(--fl-surface-subtle);
  }
  .range-dialog button[aria-pressed="true"] {
    color: var(--fl-on-accent);
    background: var(--fl-accent);
  }
  .range-dialog button:focus-visible,
  .range-trigger:focus-visible,
  .year input:focus-visible {
    outline: 2px solid var(--fl-accent);
    outline-offset: -2px;
  }
  .days,
  .months {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    text-align: center;
  }
  .days button {
    font-variant-numeric: tabular-nums;
    padding: 0;
  }
  .weekday {
    color: var(--fl-muted);
    font-size: 0.75rem;
    padding: 5px 0;
  }
  .months {
    grid-template-columns: repeat(3, 1fr);
  }
  .year input {
    max-width: 8em;
    margin: 6px;
    background: var(--fl-surface-subtle);
    color: inherit;
    border: 1px solid var(--fl-line);
    padding: 8px;
  }
  .previous,
  .down {
    display: inline-flex;
    vertical-align: middle;
  }
  .previous {
    transform: rotate(180deg);
  }
  .down {
    transform: rotate(90deg);
  }
  .current-range {
    margin: 2px 0;
    color: var(--fl-muted);
    font-size: 0.78rem;
  }
  .days .inside {
    border-radius: 0;
    background: var(--fl-accent-soft, #313621);
  }
  .days .preview-end {
    box-shadow: inset 0 0 0 1px var(--fl-accent);
  }
  .range-dialog header button,
  .range-dialog footer button {
    min-height: var(--fl-control-height, 40px);
    border-radius: var(--fl-control-radius, 7px);
  }
  .range-dialog footer {
    border-top: 1px solid var(--fl-line);
    margin-top: 8px;
    padding-top: 4px;
  }
  @media (max-width: 600px) {
    .range-dialog button {
      min-height: 44px;
    }
    .range-trigger {
      min-height: var(--fl-control-height, 44px);
    }
  }
</style>
