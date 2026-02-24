---
id: reinforce
name: reinforce
description: |
  Add new requirements to spec.md or fill gaps in documents.
  Primary: Add features (replaces /enhance). Secondary: Fill gaps after /reverse.
  Triggers: reinforce, add requirements, new feature
user-invocable: true
version: 3.0.0
triggers: ["reinforce", "add requirements", "new feature", "supplement document", "fill gaps"]
requires: []
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Req ID `FR-{number}` Rule**: Always use `max(existing number) + 1`. NEVER reuse deleted numbers.

**Model**: Sonnet (document merging). Opus for complex reasoning.

# Reinforce Workflow

Add new requirements or fill gaps in existing documents.

## Enhancement Workflow (replaces deleted /enhance)

```
New Proposal → /reinforce (spec.md) → /arch → /check → /build
```

## When to Use

- **Add new requirements**: new features to spec.md, then run /arch
- **After /reverse**: fill gaps marked with ❓
- **New information**: reflect later-acquired info
- **Error correction**: fix incorrect inferences

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request file from user → ask for copy-paste |
| AskQuestion | "Select: 1) A 2) B" format |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md    # ← Input/Output
  ├── arch.md    # ← Input/Output
  └── trace.md
```

---

## Phase 0: Skill Entry

### 0-1. Document Input

```json
{
  "title": "Start Document Reinforcement",
  "questions": [
    {
      "id": "has_docs",
      "prompt": "Do you have documents to reinforce?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide file paths with @"},
        {"id": "no", "label": "No - I don't have documents"}
      ]
    }
  ]
}
```

- `no` → guide to /reverse
- `yes` → request spec.md, arch.md paths

### 0-2. Extract serviceName

From path: `docs/alert/spec.md` → `serviceName = "alert"`

---

## Phase 1: Analyze Existing Documents

### 1-1. Load Documents

Read spec.md and arch.md.

### 1-2. Identify Unconfirmed Items

Extract items marked with:
- `❓ Needs confirmation` — requires user to provide content (delete and rewrite)
- `❓ Unconfirmed` — not yet verified by user
- `❓ Inferred` — AI-inferred, keep content but needs user confirmation to become `✅ Confirmed`
- Items with "low" confidence
- Empty sections

**NOTE**: These three ❓ variants have different handling logic in Phase 4-3.

### 1-3. Report Current Status

```markdown
## Current Document Status

### spec.md
| Section | Status |
|---------|--------|
| Goal | ✅ Confirmed / ❓ Inferred / ❌ Unconfirmed |
| Non-goals | {status} |
| Feature Specification | {status} |
| Priority | {status} |

### arch.md
| Section | Status |
|---------|--------|
| Summary | {status} |
| Code Mapping | ✅ Extracted |
| API Spec | ✅ Extracted |
| Risks & Tradeoffs | {status} |

### Items Needing Reinforcement
1. {Item 1} - {current status}
2. {Item 2} - {current status}
```

---

## Phase 2: Collect New Information

### 2-1. Select Reinforcement Type

```json
{
  "title": "What information do you want to add?",
  "questions": [
    {
      "id": "reinforce_type",
      "prompt": "Select the type of content to reinforce",
      "options": [
        {"id": "add_requirement", "label": "Add new requirements - New feature to spec.md (then run arch)"},
        {"id": "fill_blank", "label": "Fill gaps - Items marked with ❓"},
        {"id": "correct", "label": "Fix errors - Correct incorrect inferences"},
        {"id": "add_new", "label": "Add new info - Later-acquired information"},
        {"id": "guided", "label": "Guided mode - Ask me questions one by one"}
      ]
    }
  ]
}
```

### 2-2. Process by Type

**add_requirement (PRIMARY USE):**

1. Ask user for new requirement description
2. Read current Requirement Summary and find max Req ID:
   ```markdown
   | Req ID | Category | Requirement | Priority | Status |
   |--------|----------|-------------|----------|--------|
   | FR-001 | Auth | ... | High | Designed |
   | FR-002 | Auth | ... | Medium | Implemented |
   ```
3. Assign new ID = max + 1 (e.g., FR-003). NEVER reuse deleted numbers.
4. Add row: `| FR-003 | {category} | {new requirement} | {priority} | Draft |`
5. Update related sections (Feature Specification, Non-Functional, etc.)
6. Inform: "Requirement FR-003 added. Next: run `/arch` to update design."

**fill_blank**: For each ❓ item, ask user (provide / skip).
**correct**: User specifies section + correct content.
**add_new**: User describes freely, classify to appropriate section.
**guided**: Ask about unconfirmed items in sequence.

---

## Phase 3: Classify Information

### 3-1. Analyze User Input

| Information Type | Target Document |
|-----------------|----------------|
| Business purpose/intent | spec.md - Goal, Non-goals |
| Feature description/behavior | spec.md - Feature Specification |
| Priority/importance | spec.md - Priority |
| Technical decision rationale | arch.md - Risks & Tradeoffs |
| Architecture changes | arch.md - Architecture, Code Mapping |
| API changes | arch.md - API Spec |

### 3-2. Confirm Classification (If Ambiguous)

```json
{
  "title": "Classify Information",
  "questions": [
    {
      "id": "classify",
      "prompt": "Your input:\n\"{user input summary}\"\n\nWhere should this be reflected?",
      "options": [
        {"id": "requirements", "label": "Requirements (spec.md)"},
        {"id": "arch", "label": "Architecture (arch.md)"},
        {"id": "both", "label": "Both"},
        {"id": "auto", "label": "You decide"}
      ]
    }
  ]
}
```

---

## Phase 4: Update Documents

### 4-1. Update spec.md

| Section | Update Method |
|---------|--------------|
| Goal | Inferred → Confirmed (remove ❓) |
| Non-goals | Empty → Fill with content |
| Feature Specification | Add/modify |
| Priority | Empty → Fill with content |
| Unclear Items | Remove resolved items |

### 4-2. Update arch.md

| Section | Update Method |
|---------|--------------|
| Summary | Confirm Goal/Non-goals |
| Scope | Clarify scope |
| Risks & Tradeoffs | Empty → Fill with content |
| Code Mapping | See rules below |

**Code Mapping `Impl` column rules:**
- Existing rows: keep `Impl` status unchanged (do not modify `[x]` or `[ ]`)
- New rows: set `Impl = [ ]` and continue `#` numbering
- Content modification: keep `Impl` as-is

### 4-3. Update Status Markers

Three ❓ variants have **different** transformation rules:

1. `❓ Needs confirmation` → **Content replacement** (delete existing content, rewrite with user-provided info)
2. `❓ Inferred` → `✅ Confirmed` (keep content as-is, change status marker only)
3. Confidence `low` → `high` (metadata change only, if user confirmed)

### 4-4. Add Reinforcement Record

```markdown
## Reinforcement History
| Date | Type | Changes |
|------|------|---------|
| {date} | fill_blank | Confirmed Goal, Non-goals |
| {date} | add_new | Added Risks section |
```

---

## Phase 5: Save and Complete

### 5-1. Confirm Changes

```markdown
## Changes to be Applied
### spec.md
| Section | Before | After |
|---------|--------|-------|
| {section} | {previous} | {new} |

### arch.md
| Section | Before | After |
|---------|--------|-------|
| {section} | {previous} | {new} |
```

Ask user: "I will update the documents with these changes. Proceed?"

### 5-2. Save

`docs/{serviceName}/spec.md` and `docs/{serviceName}/arch.md`

### 5-3. Completion Report

Report: changed sections, change type, completion rate before/after, remaining unconfirmed items. Next: need more → re-run /reinforce; complete → use sync/build.

---

# Integration Flow

```
[reverse] → Incomplete documents
               ↓
         [reinforce] ←──┐
               │        │ (repeat)
               ↓        │
         Reinforced ────┘
         documents
               ↓ (when complete)
         Use sync/build
```

## Important Notes

1. **Works without /reverse** — also for manual documents (but "fill gaps" unavailable without ❓ markers)
2. **Incremental** — re-run when new info available, no need to fill all at once
3. **No code analysis** — only processes docs + user input (token-efficient)
4. **History logged** — all reinforcements tracked in Reinforcement History section
