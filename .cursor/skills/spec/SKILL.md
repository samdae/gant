---
id: spec
name: Spec
description: |
  Transform unstructured materials into refined requirements document.
  Collects service name and input materials, creates Q&A loop to clarify unclear points.

  Triggers: spec, specification, define requirements, 요구사항 정의, 명세
user-invocable: true
version: 2.0.0
triggers:
  - "spec"
  - "specification"
  - "requirements"
  - "define requirements"
requires: []
platform: all
recommended_model: opus
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - LS
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Spec Workflow

Transform unstructured materials into refined requirements documentation.

## 💡 Recommended Model

**Opus** recommended (quality priority) / Sonnet acceptable (cost savings)

→ Affects design quality, so prefer high-performance model when possible

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user → ask for copy-paste |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |
| **Task** | Use step-by-step checklist, proceed phase by phase |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md   # ← This skill's output
              ├── arch.md           # arch skill output
              └── trace.md      # debug skill output
```


## Supported Input Types

| Type | Recommended | Not Recommended |
|------|------------|-----------------|
| Notion/Markdown | MD file | - |
| Chat history | Text copy-paste or include in MD | - |
| Images | **Attach as separate file** (@reference) | Embed in MD ❌ |
| Mixed | MD + separate image attachments | - |

⚠️ **Image Warning**: Embedded images in MD cannot be analyzed. Must attach separately using `@imagePath` format.

## Phase 0: Skill Entry

### 0-0. Model Recommendation (Display at start)

> 💡 **This skill performs best with the Opus model.**
> Sonnet is acceptable if cost savings are needed, but may impact design quality.
>
> **Output location**: `docs/{serviceName}/spec.md`

### 0-1. Collect Service Name and Input Information

When skill is invoked without input, **use AskQuestion to guide information collection**:

```json
{
  "title": "Start Requirements Refinement",
  "questions": [
    {
      "id": "input_type",
      "prompt": "What type of material do you have?",
      "options": [
        {"id": "md", "label": "Markdown/Notion (MD file)"},
        {"id": "chat", "label": "Chat history (text)"},
        {"id": "image", "label": "Images (Figma, etc.)"},
        {"id": "mixed", "label": "Mixed (MD + images)"}
      ]
    },
    {
      "id": "has_file",
      "prompt": "Do you have the file ready?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide the file path"},
        {"id": "no", "label": "No - I will input directly"}
      ]
    },
    {
      "id": "domain",
      "prompt": "What domain/industry does this feature belong to?",
      "options": [
        {"id": "ecommerce", "label": "E-commerce/Shopping"},
        {"id": "fintech", "label": "Fintech/Finance"},
        {"id": "manufacturing", "label": "Manufacturing/Production"},
        {"id": "saas", "label": "SaaS/B2B"},
        {"id": "healthcare", "label": "Healthcare/Medical"},
        {"id": "other", "label": "Other (specify)"}
      ]
    }
  ]
}
```

### 0-2. Service Name Input

After AskQuestion, ask for service name:

> "Please enter the service/feature name (e.g., alert, auth, payment)"
> This name will be used to save documents in `docs/{serviceName}/` folder.

**serviceName rules:**
- Lowercase English letters
- Use hyphen (-) or underscore (_) instead of spaces
- Examples: `alert`, `user-auth`, `order_management`

After user responds → Request file path or direct input → Proceed to Phase 1

## Phase 1: Input Collection

Confirm with user:
- Path or content of unstructured materials
- Brief purpose of feature (one line)

**If file is already provided** → Proceed directly to Phase 2

## Phase 2: Draft Analysis

Analyze input materials and create draft:

1. Read all materials (use vision analysis for images)
2. Extract core features
3. Identify unclear areas
4. Organize according to draft structure

## Phase 3: Q&A Loop

Resolve unclear points using **AskQuestion**:

```
Loop:
  1. Ask 1-2 highest priority questions about unclear points
  2. Receive user answers
  3. Update document reflecting answers
  4. Check remaining unclear points

Termination conditions:
  - All required items resolved
  - OR user selects "This is sufficient"
```

**Question rules:**
- Only 1-2 questions at a time (manage user fatigue)
- Provide options when possible (selection faster than free input)
- Avoid technical questions, prioritize business perspective

## Phase 4: User Review

Present completed draft to user:

**Confirm with AskQuestion:**

```json
{
  "title": "Requirements Document Review",
  "questions": [
    {
      "id": "review_result",
      "prompt": "Please review the requirements document. How would you like to proceed?",
      "options": [
        {"id": "approve", "label": "Approve - Save as is"},
        {"id": "modify", "label": "Modify - Need changes to specific parts"},
        {"id": "add", "label": "Add - Missing content"},
        {"id": "restart", "label": "Restart - Wrong direction"}
      ]
    }
  ]
}
```

**Processing by response:**
- `approve` → Proceed to Phase 5 (save)
- `modify` / `add` → Receive modification details, return to Phase 3 and iterate
- `restart` → Return to Phase 2 and rewrite draft

## Phase 5: Save Final Document

Save as MD file upon approval:
- **Path**: `docs/{serviceName}/spec.md`
- Create folder if it doesn't exist

### Post-Completion Guidance

After saving document, inform user:

> ✅ **Requirements Document Complete**
>
> Saved to: `docs/{serviceName}/spec.md`
>
> **Next Step**: Run the `arch` skill to begin design.
> → Pass `@docs/{serviceName}/spec.md` file.

---

# Output Document Template

```markdown
# Requirements Definition: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Source Material: {input file path}
> Domain: {domain}

## 0. Requirement Summary

| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | {category} | {requirement description} | High/Medium/Low | Draft |
| FR-002 | {category} | {requirement description} | High/Medium/Low | Draft |

> **Req ID Rule**: `FR-{number}` format. New = max + 1. Never reuse deleted numbers.
> **Status**: `Draft` → `Designed` (after arch) → `Implemented` (after build)

## 0.5. Development Target

- [ ] Backend
- [ ] Frontend
- [ ] Both

## 1. Business Context

### Purpose
(Why is this feature needed?)

### Users
(Who will use it?)

### Problem to Solve
(What pain points does it address?)

## 2. Feature Specification

### 2-1. Backend Perspective
- ...

### 2-2. Frontend Perspective
- ...

## 3. Related Existing Modules

| Type | Name | Impact |
|------|------|--------|
| Table | | |
| API | | |
| Service | | |

## 4. Non-Functional Requirements

| Item | Requirement |
|------|-------------|
| Performance | |
| Security | |
| Concurrency | |

## 4.5. Data Contract

### Input Data
| Field | Type | Required | Validation | Source |
|-------|------|----------|------------|--------|
| | | | | |

### Output Data
| Field | Type | Description | Consumer |
|-------|------|-------------|----------|
| | | | |

### Data Permissions
| Data | Read | Write | Conditions |
|------|------|-------|------------|
| | | | |

## 4.6. Exception and Error Policy

### Expected Exception Scenarios
| Scenario | Handling Method | User Message |
|----------|----------------|--------------|
| | | |

### Error Response Format
| HTTP Code | Error Code | Scenario |
|-----------|-----------|----------|
| | | |

### Recovery Strategy
- **Retry Possible**: (Which operations can be retried)
- **Rollback Required**: (When rollback is needed)
- **Notification Required**: (When to send alerts for errors)

## 5. Unclear Items

(Items not resolved through Q&A)

- [ ] ...

## 6. Development Priority

### MVP (Must Have)
1. ...

### Should Have
1. ...

### Nice to Have
1. ...

## 7. Completion Criteria

- [ ] Criterion 1
- [ ] Criterion 2
```

---

# Integration Flow

```
[spec] → docs/{serviceName}/spec.md
        ↓
[arch] → docs/{serviceName}/arch.md
        ↓
[build] → Implementation
        ↓
(Bug occurs)
        ↓
[debug] → docs/{serviceName}/trace.md
```
