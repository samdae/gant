---
id: trace
name: trace
description: |
  Record bug fixes, changes, and design impact to trace.md.
  Triggers: trace, log, record, changelog
user-invocable: true
version: 2.0.0
triggers: ["trace", "log", "record", "changelog"]
requires: ["debug"]
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Code Mapping `#` Rule**: Always use `max(existing #) + 1` for new rows. NEVER reuse deleted numbers.
> **Document Version Control**: After changes, commit recommended. Message: `docs({serviceName}): trace - {summary}`. If git unavailable, skip.

**Model**: Sonnet (document writing).

# Trace Workflow

Records bug fixes, analysis results, and changes in trace.md.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request user to copy-paste existing changelog content |
| AskQuestion | "Please select one of the following" format |

## Invocation

1. Automatically from debug skill (after fix)
2. Manually by user

---

## Phase 0: Skill Entry

### 0-1. Context Verification

**From debug session:** Use context as-is (cause, fix, etc.).

**Independent:**

```json
{"title":"Changelog Writing","questions":[{"id":"has_context","prompt":"Do you have content to record?","options":[{"id":"debug","label":"Bug fix result - I analyzed/fixed in this session"},{"id":"manual","label":"Manual record - I will explain directly"}]}]}
```

### 0-2. serviceName Verification

```json
{"title":"Service Confirmation","questions":[{"id":"service_name","prompt":"Which service's changelog should this be recorded in?","options":[{"id":"input","label":"I will tell you the service name"}]}]}
```

---

## Phase 1: Result Type Classification

```json
{"title":"Result Type","questions":[{"id":"result_type","prompt":"What type of result are you recording?","options":[{"id":"fix_complete","label":"Code fix completed - Bug was fixed"},{"id":"external_cause","label":"External cause identified - Not my code's problem"},{"id":"investigation","label":"Investigation result - Cause identification in progress/failed"},{"id":"other","label":"Other changes"}]}]}
```

---

## Phase 2: Information Gathering

### 2-1. From debug context

Extract: symptom, cause, fix content, impact scope.

### 2-2. Manual input

> "Please provide: 1) Symptom 2) Cause 3) Action taken/plan 4) Impact scope"

### 2-3. Code Mapping Changes Verification

```json
{"title":"Code Mapping Changes","questions":[{"id":"has_mapping_changes","prompt":"Did this fix change the Code Mapping in arch.md?","options":[{"id":"yes","label":"Yes - Added/Modified/Deleted methods or files"},{"id":"no","label":"No - Bug fix only (no structural changes)"}]}]}
```

- `yes` -> Extract from debug context, write to grid with `Synced = [ ]`
- `no` -> Leave empty or "No structural changes"

**When extracting:** Get arch.md Code Mapping table, identify added/modified/deleted rows, write with `Synced = [ ]`.

---

## Phase 3: Write Changelog

If exists: add new entry at top. If not: create new.

### Template

```markdown
# Changelog

## {date} - {result type}

### Code Mapping Changes
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| {#} | {feature} | {file path} | {class name} | {method name} | {action} | ADD/MODIFY/DELETE | [ ] |

> **Change**: ADD = new row to arch, MODIFY = existing row modified, DELETE = row to remove
> **Synced**: [ ] = not yet synced, [x] = synced. Run `/sync` to apply.

**WARNING**: Run `sync` skill to apply these changes to arch.md

---

### Basic Information
| Item | Content |
|------|---------|
| Symptom | {user-reported symptom} |
| Cause | {identified cause} |
| Severity | Critical / High / Medium / Low |

### Change Reasoning
- **Why problem occurred**: {root cause analysis}
- **Why this action**: {reason for action choice}

### Action Details
| File | Changes | Change Type |
|------|---------|-------------|
| {file path} | {change description} | Fixed/Added/Deleted/None |

### Impact Scope
- **Direct**: {modified features/APIs}
- **Indirect**: {other features potentially affected}
- **No Impact Confirmed**: {areas confirmed unaffected}

### Verification
| Verification Item | Method | Expected Result |
|------------------|--------|-----------------|
| Problem resolution | {test method} | {normal operation} |
| Regression test | {related feature test} | {existing features normal} |

### Related Documents
- Requirements: docs/{serviceName}/spec.md
- Design: docs/{serviceName}/arch-be.md or arch-fe.md
```

### Adjustment by Result Type

- **Fix completed**: Fill Code Mapping grid (all `Synced = [ ]`), record actual changed files
- **External cause**: Empty grid, Action = "No code changes - External cause", record cause + recommended actions
- **Investigation**: Empty grid, Action = "Investigation in progress", record next steps

---

## Phase 4: Save and Complete

Path: `docs/{serviceName}/trace.md`

```markdown
## Changelog Writing Complete

### Summary
| Item | Content |
|------|---------|
| Service | {serviceName} |
| Result Type | {Code fix/External cause/Investigation} |
| Code Mapping Changes | {count} rows (ADD: {n}, MODIFY: {n}, DELETE: {n}) |

### Files
- Updated: `docs/{serviceName}/trace.md`

### Next Steps
- If Code Mapping Changes exist: Run `/sync` to apply to arch.md
- If testing needed: Proceed with verification method
```

---

## Integration Flow

```
[debug] -> Extract Code Mapping changes
  -> [trace] -> Write trace.md (Code Mapping Changes grid)
    -> (when changes exist) -> [sync] -> Apply to arch.md (filter Synced=[ ])
      -> Update trace.md (Synced [ ] -> [x])
```

## Important Notes

1. **Best called in same session** - Auto-extract Code Mapping changes from debug context; manual input required if different session
2. **Code Mapping `#`** - Must match arch.md row numbers; new rows = last_arch_number + 1; all start `Synced = [ ]`; sync updates to `[x]`
3. **External causes worth recording** - "Not our code's problem" is also important; reference for future similar issues
