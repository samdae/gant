---
id: sync
name: Sync
description: |
  Synchronize changelog/enhancement results to arch document.
  Filters design-impacting changes and updates arch.md.

  Triggers: sync, synchronize, 동기화, 설계 동기화
user-invocable: true
version: 2.0.0
triggers:
  - "sync"
  - "synchronize"
  - "design sync"
requires: ["debug", "enhance"]
platform: all
recommended_model: sonnet
allowed-tools:
  - Read
  - Write
  - Glob
  - LS
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Sync Workflow

Synchronize design-impacting items from changelog or enhancement design results to existing arch.md.

## 💡 Recommended Model

**Sonnet recommended** (document merging task)

→ For complex conflicts, Opus recommended

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read** | Request file path from user → ask for copy-paste |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB" format |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md      # ← Reference (Requirement Drift Check) & Optional Target
              ├── arch.md      # ← Sync target
              └── trace.md      # ← Input (design-impacting items)
```

## ⚠️ Execution Timing

Run in following situations:
1. **After debug completion** - When "Design Impact: Yes" items added to changelog (Smart Sync triggered)
2. **After /enhance completion** - When integrating enhancement design to existing arch

---

## Phase 0: Skill Entry

### 0-0. Model Guidance

> 💡 **This skill recommends the Sonnet model.**
> Document merging task, so high-performance model unnecessary.
>
> **Input**: trace.md (design-impacting items) or enhancement result
> **Reference**: spec.md (to check for requirement drift)
> **Output**: Updated arch.md (and optionally spec.md)

### 0-1. Verify Sync Type

```json
{
  "title": "Architect Synchronization",
  "questions": [
    {
      "id": "sync_type",
      "prompt": "What content will you synchronize?",
      "options": [
        {"id": "debug", "label": "Bug fix - Design-impacting items from changelog"},
        {"id": "enhance", "label": "Feature enhancement - enhance results"}
      ]
    }
  ]
}
```

### 0-2. Collect File Input

**When debug selected:**
```json
{
  "title": "File Input",
  "questions": [
    {
      "id": "has_changelog",
      "prompt": "Please provide changelog file path (docs/{serviceName}/trace.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"}
      ]
    },
    {
      "id": "has_arch",
      "prompt": "Please provide arch file path (docs/{serviceName}/arch.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"}
      ]
    }
  ]
}
```

**When enhance selected:**
> "Please provide enhancement design result and existing arch.md path."

### 0-3. Infer serviceName

Extract serviceName from input file path:
- Input: `docs/alert/trace.md`
- Extract: `serviceName = "alert"`

---

## Phase 1: Analyze Changes

### 1-1. Debug Sync (trace → arch)

Filter **`Synced = [ ]`** rows from trace's Code Mapping Changes grid.

**Smart Sync Logic (3-way Sync):**

```
Analyze trace.md and arch.md:
  for each changelog entry:
    for each row in "Code Mapping Changes" table:
      if Synced == "[ ]":
        1. Identify arch row using `#`
        2. Extract `Spec Ref` (FR-xxx) from arch row
        3. If `Spec Ref` exists:
             Read related requirement from spec.md (FR-xxx)
             Compare requirement vs implementation change
             Flag if "Requirement Drift" detected
        4. Add to sync targets
```

**Sync target example:**
```markdown
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| 3 | Auth | auth/svc.py | AuthSvc | validate() | Add null check | MODIFY | [ ] | ← target
| 6 | Auth | auth/svc.py | AuthSvc | refresh() | Token refresh | ADD | [ ] | ← target
```

### 1-2. Enhancement Sync (enhancement result → arch)

Identify changes/additions from enhancement design results:
- New APIs
- Modified APIs
- New components
- DB schema changes

### 1-3. Report Changes & Drift

```markdown
## Sync Target Analysis

### Code Mapping Changes to Apply
| # | Spec Ref | Change | Current in arch | New Value | Drift Risk |
|---|---|---|---|---|---|
| 3 | FR-001 | MODIFY | validate() - Check user | validate() - Add null check | Low |
| 6 | FR-002 | MODIFY | limit=10 | limit=100 | **HIGH (Req says 10)** |

> **Drift Risk**:
> - **High**: Contradicts explicit requirement in spec.md
> - **Medium**: changes specific values defined in spec
> - **Low**: Implementation detail only
```

```markdown
## Sync Target Analysis

### Code Mapping Changes to Apply
| # | Change | Current in arch | New Value |
|---|--------|-----------------|-----------|
| 3 | MODIFY | validate() - Check user | validate() - Add null check |
| 6 | ADD | (not exists) | refresh() - Token refresh |

### Summary
- Total rows to sync: {count}
- ADD: {count} rows
- MODIFY: {count} rows
- DELETE: {count} rows
```

### 1-4. Git Commit Strategy

```json
{
  "title": "Git Commit Before Modification",
  "questions": [
    {
      "id": "git_strategy",
      "prompt": "Do you want to Git commit the current state before modifying arch.md?",
      "options": [
        {"id": "commit", "label": "Yes - Commit then proceed (recommended)"},
        {"id": "skip", "label": "No - Proceed immediately"}
      ]
    }
  ]
}
```

- When `commit` selected:
  ```bash
  git add docs/{serviceName}/arch.md
  git commit -m "backup: arch.md before sync"
  ```
- When `skip` selected: Proceed directly to Phase 2

---

## Phase 2: Conflict Verification

### 2-1. Check for Conflicts

Compare existing arch content with new changes:

| Conflict Type | Example | Resolution |
|--------------|---------|------------|
| Duplicate modification in same section | Same endpoint in API Spec | Request user selection |
| Logical inconsistency | References deleted API | Warn and confirm with user |
| None | Adding new item | Auto-proceed |

### 2-2. When Conflict Occurs

```json
{
  "title": "Sync Conflict Detected",
  "questions": [
    {
      "id": "conflict_resolution",
      "prompt": "Existing content conflicts with new changes.\n\nExisting: {existing content}\nNew: {new content}\n\nHow to proceed?",
      "options": [
        {"id": "keep_old", "label": "Keep existing - Ignore new changes"},
        {"id": "use_new", "label": "Replace with new content"},
        {"id": "merge", "label": "Merge - Reflect both"},
        {"id": "manual", "label": "Manual handling - I will modify directly"}
      ]
    }
  ]
}
```

---

## Phase 2.5: Spec Update (Smart Sync)

If **Review Drift** is detected or user wants to update requirements:

### 2.5-1. Confirm Spec Update

```json
{
  "title": "Requirement Drift Detected",
  "questions": [
    {
      "id": "spec_update",
      "prompt": "Some changes seem to affect Requirements (FR-xxx).\n\nExample: {Drift Item}\n\nDo you want to update spec.md as well?",
      "options": [
        {"id": "yes", "label": "Yes - Update spec.md to match reality"},
        {"id": "no", "label": "No - Keep spec.md as is (Implementation divergence)"}
      ]
    }
  ]
}
```

### 2.5-2. Update spec.md (if Yes)

1. Find target Requirement ID (FR-xxx) in `spec.md`
2. Update description to match implementation reality
3. Add note: `(Updated via sync on {date})`

---

## Phase 3: Update arch.md

### 3-1. Update Code Mapping by Change Type

**Process each row from trace's Code Mapping Changes grid:**

| Change Type | Action in arch.md |
|-------------|-------------------|
| `ADD` | Insert new row with same `#`, set `Impl = [x]` |
| `MODIFY` | Find row by `#` in arch, update content, keep `Impl` status |
| `DELETE` | Find row by `#` in arch, remove entire row |

**Example:**

```
trace.md (source):
| # | Feature | ... | Change | Synced |
| 3 | Auth | ... | MODIFY | [ ] |
| 6 | Auth | ... | ADD | [ ] |

arch.md (before):
| # | Feature | ... | Impl |
| 1 | Login | ... | [x] |
| 2 | Logout | ... | [x] |
| 3 | Auth | ... | [x] |  ← will be modified
| 4 | Profile | ... | [x] |
| 5 | Settings | ... | [x] |

arch.md (after):
| # | Feature | ... | Impl |
| 1 | Login | ... | [x] |
| 2 | Logout | ... | [x] |
| 3 | Auth (MODIFIED) | ... | [x] |  ← modified
| 4 | Profile | ... | [x] |
| 5 | Settings | ... | [x] |
| 6 | Auth (NEW) | ... | [x] |  ← added
```

**After DELETE, renumber `#` if needed (optional - can leave gaps)**

### 3-1.5. Update Other Sections (if applicable)

| Section | Update Method |
|---------|--------------|
| API Spec | Add/modify endpoints |
| DB Schema | Modify table/column definitions |
| Sequence Diagram | Modify diagram |
| Risks & Tradeoffs | Add new tradeoffs |

### 3-2. Add Sync History

Add/update sync history section at bottom of arch.md:

```markdown
---

## Sync History

| Date | Type | Source | Changes |
|------|------|--------|---------|
| {date} | debug | changelog {date} | {change summary} |
| {date} | enhance | requirements v2 | {change summary} |
```

### 3-3. Save arch.md

Save updated arch.md (overwrite existing file)

### 3-4. Update trace Synced Status

After arch.md update, update trace.md:

1. Find all synced rows in Code Mapping Changes grid
2. Change `Synced` from `[ ]` to `[x]`

**Example:**
```markdown
# Before
| # | Feature | ... | Change | Synced |
| 3 | Auth | ... | MODIFY | [ ] |
| 6 | Auth | ... | ADD | [ ] |

# After
| # | Feature | ... | Change | Synced |
| 3 | Auth | ... | MODIFY | [x] |  ← updated
| 6 | Auth | ... | ADD | [x] |  ← updated
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
- **If implementation needed**: Run `build` skill
- **If additional modifications needed**: Edit arch.md directly
- **If spec updated**: Review `docs/{serviceName}/spec.md`
```


---

# Integration Flow

```
[debug] → Analysis/fix complete
                ↓
         [trace] → Write Code Mapping Changes (Synced=[ ])
                ↓
         [sync] → Filter Synced=[ ] rows
                ↓
                ├─→ Update arch.md (apply ADD/MODIFY/DELETE)
                │
                └─→ Update trace.md (Synced=[ ] → [x])
                ↓
           [build] (if needed)

[enhance] → Enhancement design
                ↓
         [sync] → Update arch
                ↓
           [build]
                │
                ▼ (Smart Sync)
 [spec] ← (Update if Drift) ─┘
```


---

# Important Notes

1. **Only sync `Synced = [ ]` rows**
   - Already synced rows (`[x]`) are skipped
   - Empty Code Mapping Changes = nothing to sync

2. **`#` column is the key**
   - `MODIFY` and `DELETE` use `#` to find target row in arch
   - `ADD` inserts new row with the `#` from trace
   - Keep `#` numbers consistent between trace and arch

3. **Always update trace after arch**
   - Mark synced rows as `[x]` in trace.md
   - This prevents duplicate syncing

4. **Sync History management**
   - Record all synchronizations in arch.md
   - Enable future change tracking
