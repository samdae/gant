---
id: sync
name: sync
description: |
  Synchronize trace/enhancement results to arch document.
  Filters design-impacting changes and updates arch.md.
  Triggers: sync, synchronize
user-invocable: true
version: 2.0.0
triggers: ["sync", "synchronize", "design sync"]
requires: ["debug", "reinforce"]
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, LS]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Code Mapping `#` Rule**: Always use `max(existing #) + 1` for new rows. NEVER reuse deleted numbers.
> **Document Version Control**: After changes, commit recommended. Message: `docs({serviceName}): sync - {summary}`. If git unavailable, skip.

**Model**: Sonnet (document merging). Opus for complex conflicts.

# Sync Workflow

Synchronize design-impacting items from trace.md or enhancement results to arch.md.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request file path from user -> ask for copy-paste |
| AskQuestion | "Please select: 1) OptionA 2) OptionB" format |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md    # Reference (Requirement Drift Check) & Optional Target
  ├── arch.md    # Sync target
  └── trace.md   # Input (design-impacting items)
```

## When to Run

1. After debug completion - when "Design Impact: Yes" items in trace (Smart Sync)
2. After enhancement - integrating new design to existing arch

---

## Phase 0: Skill Entry

### 0-1. Verify Sync Type

```json
{"title":"Architect Synchronization","questions":[{"id":"sync_type","prompt":"What content will you synchronize?","options":[{"id":"debug","label":"Bug fix - Design-impacting items from changelog"},{"id":"enhance","label":"Feature enhancement - enhance results"}]}]}
```

### 0-2. Collect File Input

**When debug selected:**

```json
{"title":"File Input","questions":[{"id":"has_changelog","prompt":"Please provide changelog file path (docs/{serviceName}/trace.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"}]},{"id":"has_arch","prompt":"Please provide arch file path (docs/{serviceName}/arch.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"}]}]}
```

**When enhance selected:**
> "Please provide enhancement design result and existing arch.md path."

### 0-3. Infer serviceName

From file path: `docs/alert/trace.md` -> serviceName = "alert"

---

## Phase 1: Analyze Changes

### 1-1. Debug Sync (trace -> arch)

Filter `Synced = [ ]` rows from trace's Code Mapping Changes grid.

**Smart Sync Logic (3-way):**
```
for each changelog entry:
  for each row in "Code Mapping Changes" where Synced == "[ ]":
    1. Identify arch row using `#`
    2. Extract `Spec Ref` (FR-xxx) from arch row
    3. If Spec Ref exists: read requirement from spec.md, compare vs change, flag if "Requirement Drift"
    4. Add to sync targets
```

**Sync target example:**
```markdown
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| 3 | Auth | auth/svc.py | AuthSvc | validate() | Add null check | MODIFY | [ ] |
| 6 | Auth | auth/svc.py | AuthSvc | refresh() | Token refresh | ADD | [ ] |
```

### 1-2. Enhancement Sync

Identify from enhancement results: new APIs, modified APIs, new components, DB schema changes.

### 1-3. Report Changes & Drift

```markdown
## Sync Target Analysis

### Code Mapping Changes to Apply
| # | Spec Ref | Change | Current in arch | New Value | Drift Risk |
|---|---|---|---|---|---|
| 3 | FR-001 | MODIFY | validate() - Check user | validate() - Add null check | Low |
| 6 | FR-002 | MODIFY | limit=10 | limit=100 | **HIGH (Req says 10)** |

### Summary
- Total rows to sync: {count}
- ADD: {count}, MODIFY: {count}, DELETE: {count}
```

> **Drift Risk**: High = contradicts spec, Medium = changes spec values, Low = implementation detail only

### 1-4. Git Commit Strategy

```json
{"title":"Git Commit Before Modification","questions":[{"id":"git_strategy","prompt":"Do you want to Git commit the current state before modifying arch.md?","options":[{"id":"commit","label":"Yes - Commit then proceed (recommended)"},{"id":"skip","label":"No - Proceed immediately"}]}]}
```

If commit: `git add docs/{serviceName}/arch.md && git commit -m "backup: arch.md before sync"`

---

## Phase 2: Conflict Verification

### 2-1. Check for Conflicts

| Conflict Type | Example | Resolution |
|--------------|---------|------------|
| Duplicate modification | Same endpoint in API Spec | Request user selection |
| Logical inconsistency | References deleted API | Warn and confirm with user |
| None | Adding new item | Auto-proceed |

### 2-2. When Conflict Occurs

```json
{"title":"Sync Conflict Detected","questions":[{"id":"conflict_resolution","prompt":"Existing content conflicts with new changes.\n\nExisting: {existing}\nNew: {new}\n\nHow to proceed?","options":[{"id":"keep_old","label":"Keep existing - Ignore new changes"},{"id":"use_new","label":"Replace with new content"},{"id":"merge","label":"Merge - Reflect both"},{"id":"manual","label":"Manual handling - I will modify directly"}]}]}
```

---

## Phase 2.5: Spec Update (Smart Sync)

If Requirement Drift detected:

```json
{"title":"Requirement Drift Detected","questions":[{"id":"spec_update","prompt":"Some changes affect Requirements (FR-xxx).\n\nExample: {Drift Item}\n\nUpdate spec.md as well?","options":[{"id":"yes","label":"Yes - Update spec.md to match reality"},{"id":"no","label":"No - Keep spec.md as is (Implementation divergence)"}]}]}
```

If Yes: find FR-xxx in spec.md, update description, add note `(Updated via sync on {date})`.

---

## Phase 3: Update arch.md

### 3-1. Update Code Mapping by Change Type

| Change | Action in arch.md |
|--------|-------------------|
| ADD | Insert new row with same `#`, set `Impl = [x]` |
| MODIFY | Find row by `#`, update content, keep Impl |
| DELETE | Find row by `#`, remove row (gaps in `#` OK, no renumber needed) |

**Example:**
```
trace.md: | 3 | MODIFY | [ ] |  | 6 | ADD | [ ] |
arch.md (before): rows 1-5
arch.md (after): row 3 modified, row 6 added with [x]
```

### 3-1.5. Update Other Sections

API Spec, DB Schema, Sequence Diagram, Risks & Tradeoffs as applicable.

### 3-2. Add Sync History

```markdown
## Sync History
| Date | Type | Source | Changes |
|------|------|--------|---------|
| {date} | debug | trace {date} | {summary} |
| {date} | enhance | requirements v2 | {summary} |
```

### 3-3. Save arch.md

### 3-4. Update trace Synced Status

After arch.md update, change `Synced` from `[ ]` to `[x]` for all synced rows in trace.md.

```markdown
# Before: | 3 | Auth | ... | MODIFY | [ ] |
# After:  | 3 | Auth | ... | MODIFY | [x] |
```

---

## Phase 4: Completion Report

```markdown
## Architect Synchronization Complete

### Sync Summary
| Item | Content |
|------|---------|
| Type | debug / enhance |
| Source | {changelog date or requirements} |
| Code Mapping Changes | ADD: {n}, MODIFY: {n}, DELETE: {n} |

### Change History
| # | Change Type | Before | After |
|---|------------|--------|-------|
| {#} | ADD/MODIFY/DELETE | {before} | {after} |

### Files
- Updated: `docs/{serviceName}/arch-be.md` or `arch-fe.md`
- Updated: `docs/{serviceName}/trace.md` (Synced status)

### Next Steps
- If implementation needed: Run `/build`
- If spec updated: Review `docs/{serviceName}/spec.md`
```

---

## Integration Flow

```
[debug] -> trace.md (Code Mapping Changes, Synced=[ ])
  -> [sync] -> Filter Synced=[ ] rows
    -> Update arch.md (ADD/MODIFY/DELETE)
    -> Update trace.md (Synced [ ] -> [x])
      -> [build] (if needed)

[enhance] -> enhancement design -> [sync] -> Update arch -> [build]
  (Smart Sync) -> spec.md (update if drift)
```

## Important Notes

1. **Only sync `Synced = [ ]` rows** - `[x]` are skipped; empty grid = nothing to sync
2. **`#` column is the key** - MODIFY/DELETE use `#` to find target row; ADD inserts with `#` from trace; keep consistent between trace and arch
3. **Always update trace after arch** - Mark `[x]` to prevent duplicate syncing
4. **Sync History** - Record all syncs in arch.md for future change tracking
5. **Drift Risk levels** - High: contradicts spec, Medium: changes spec values, Low: implementation detail only
