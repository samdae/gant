---
id: trace
name: Trace
description: |
  Record bug fixes, changes, and their design impact to changelog.
  Trace changes for future reference.

  Triggers: trace, log, record, 추적, 변경 기록
user-invocable: true
version: 2.0.0
triggers:
  - "trace"
  - "log"
  - "record"
  - "changelog"
requires: ["debug"]
platform: all
recommended_model: sonnet
allowed-tools:
  - Read
  - Write
  - Glob
  - LS
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Trace Workflow

Records bug fixes, analysis results, and changes in trace.md.

## 💡 Recommended Model

**Sonnet** (document writing)

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read** | Request user to copy-paste existing changelog content |
| **AskQuestion** | "Please select one of the following" format |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              └── trace.md   # ← This skill's output
```

## ⚠️ Invocation Timing

1. **Automatically called from debug skill** - After analysis/fix completion
2. **Manually called by user** - When not called from debug, or when recording independently

---

## Phase 0: Skill Entry

### 0-1. Context Verification

**When called from debug session:**
> Use context from previous conversation (cause, fix content, etc.) as is

**When called independently:**
```json
{
  "title": "Changelog Writing",
  "questions": [
    {
      "id": "has_context",
      "prompt": "Do you have content to record?",
      "options": [
        {"id": "debug", "label": "Bug fix result - I analyzed/fixed in this session"},
        {"id": "manual", "label": "Manual record - I will explain directly"}
      ]
    }
  ]
}
```

### 0-2. serviceName Verification

```json
{
  "title": "Service Confirmation",
  "questions": [
    {
      "id": "service_name",
      "prompt": "Which service's changelog should this be recorded in?",
      "options": [
        {"id": "input", "label": "I will tell you the service name"}
      ]
    }
  ]
}
```

---

## Phase 1: Result Type Classification

### 1-1. Result Type Verification

```json
{
  "title": "Result Type",
  "questions": [
    {
      "id": "result_type",
      "prompt": "What type of result are you recording?",
      "options": [
        {"id": "fix_complete", "label": "Code fix completed - Bug was fixed"},
        {"id": "external_cause", "label": "External cause identified - Not my code's problem"},
        {"id": "investigation", "label": "Investigation result - Cause identification in progress/failed"},
        {"id": "other", "label": "Other changes"}
      ]
    }
  ]
}
```

---

## Phase 2: Information Gathering

### 2-1. Extract from Context (debug session)

Extract the following information from previous conversation:
- Symptom (user-reported issue)
- Cause (analysis result)
- Fix content (if any)
- Impact scope

### 2-2. Manual Input (independent invocation)

> "Please provide the following information:
> 1. Symptom (What was the problem?)
> 2. Cause (Why did it happen?)
> 3. Action (How was it resolved? Or resolution plan)
> 4. Impact scope (Which features/files are affected?)"

### 2-3. Code Mapping Changes Verification

```json
{
  "title": "Code Mapping Changes",
  "questions": [
    {
      "id": "has_mapping_changes",
      "prompt": "Did this fix change the Code Mapping in arch.md?",
      "options": [
        {"id": "yes", "label": "Yes - Added/Modified/Deleted methods or files"},
        {"id": "no", "label": "No - Bug fix only (no structural changes)"}
      ]
    }
  ]
}
```

- `yes` → Extract Code Mapping changes from debug context and write to grid
- `no` → Leave Code Mapping Changes section empty or with "No structural changes"

**When extracting from debug context:**
1. Get arch.md Code Mapping table (passed from debug skill)
2. Identify which rows were added/modified/deleted
3. Write to Code Mapping Changes grid with `Synced = [ ]`

---

## Phase 3: Changelog Writing

### 3-1. Check Existing Changelog

- If exists → Add new entry at the top
- If not exists → Create new

### 3-2. Template

```markdown
# Changelog

## {date} - {result type}

### Code Mapping Changes
| # | Feature | File | Class | Method | Action | Change | Synced |
|---|---------|------|-------|--------|--------|--------|--------|
| {#} | {feature} | {file path} | {class name} | {method name} | {action description} | {ADD/MODIFY/DELETE} | [ ] |

> **Change**: `ADD` = new row to arch, `MODIFY` = existing row modified, `DELETE` = row to remove from arch
> **Synced**: `[ ]` = not yet synced to arch, `[x]` = synced

⚠️ **Run `sync` skill to apply these changes to arch.md**

---

### Basic Information
| Item | Content |
|------|---------|
| Symptom | {user-reported symptom} |
| Cause | {identified cause} |
| Severity | Critical / High / Medium / Low |

### Change Reasoning
- **Why did this problem occur**: {root cause analysis}
- **Why was this action taken**: {reason for action choice}

### Action Details
| File | Changes | Change Type |
|------|---------|-------------|
| {file path} | {change description} | Fixed/Added/Deleted/None |

### Impact Scope
- **Direct Impact**: {modified features/APIs}
- **Indirect Impact**: {other features that may be affected by this fix}
- **No Impact Confirmed**: {areas confirmed to not be affected by changes}

### Verification Method
| Verification Item | Method | Expected Result |
|------------------|--------|-----------------|
| Problem resolution | {test method} | {normal operation} |
| Regression test | {related feature test} | {existing features normal} |

### Related Documents
- Requirements: docs/{serviceName}/spec.md
- Design: docs/{serviceName}/arch-be.md or arch-fe.md

---

(Previous changelog entries...)
```

### 3-3. Adjustment by Result Type

**Code fix completed:**
- Record actual changed files/content in Action Details
- Fill Code Mapping Changes grid with ADD/MODIFY/DELETE rows
- All rows start with `Synced = [ ]`

**External cause identified:**
- Code Mapping Changes: Leave empty or "No structural changes"
- Action Details: "No code changes - External cause"
- Record detailed external cause in Change Reasoning
- Add recommended actions (contact external team, configuration changes, etc.)

**Investigation result:**
- Severity: "Under investigation"
- Code Mapping Changes: Leave empty
- Action Details: "Investigation in progress" or "Cause identification failed"
- Record next steps

---

## Phase 4: Save and Complete

### 4-1. Save

```
docs/{serviceName}/trace.md
```

### 4-2. Completion Report

```markdown
## Changelog Writing Complete

### Summary
| Item | Content |
|------|---------|
| Service | {serviceName} |
| Result Type | {Code fix/External cause/Investigation record} |
| Code Mapping Changes | {count} rows (ADD: {n}, MODIFY: {n}, DELETE: {n}) |

### Files
- Updated: `docs/{serviceName}/trace.md`

### Next Steps
- **When Code Mapping Changes exist**: Execute `sync` skill to apply changes to arch.md
- **When testing needed**: Proceed with testing according to verification method
```

---

# Integration Flow

```
[debug] → Analysis/fix complete
              │
              ├─→ Extract Code Mapping changes
              │
              ▼
        [trace] → Write trace.md (with Code Mapping Changes grid)
              │
              ▼ (when Code Mapping Changes exist)
        [sync] → Apply changes to arch.md
              │   (filter Synced=[ ] rows)
              │
              └─→ Update trace.md (Synced=[ ] → [x])
```

---

# Important Notes

1. **Recommended to call in same session**
   - Automatic extraction of Code Mapping changes when debug context exists
   - Manual input required if different session

2. **Code Mapping Changes Grid**
   - `#` column must match arch.md row numbers
   - New rows: `# = last_arch_number + 1`
   - All rows start with `Synced = [ ]`
   - `sync` skill updates to `[x]` after applying

3. **External causes are also worth recording**
   - "Not our code's problem" is also important information
   - Reference for when same problem occurs later
   - Code Mapping Changes can be left empty
