---
id: spec
name: spec
description: |
  Transform unstructured materials into refined requirements document.
  Triggers: spec, specification, requirements
user-invocable: true
version: 2.0.0
triggers: ["spec", "specification", "requirements", "define requirements"]
requires: []
platform: all
recommended_model: opus
allowed-tools: [Read, Write, Glob, Grep, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Req ID `FR-{number}` Rule**: Always use `max(existing number) + 1`. NEVER reuse deleted numbers.

**Model**: Opus recommended (affects design quality). Sonnet acceptable for cost savings.
**Output location**: `docs/{serviceName}/spec.md`

# Spec Workflow

Transform unstructured materials into refined requirements documentation.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read/Grep | Request file from user → ask for copy-paste |
| AskQuestion | "Select: 1) A 2) B" format |
| Task | Use step-by-step checklist, proceed phase by phase |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md    # ← This skill's output
  ├── arch.md
  └── trace.md
```

## Supported Input Types

| Type | Method |
|------|--------|
| Markdown/Notion | MD file |
| Chat history | Text copy-paste |
| Images | Attach separately via @path |
| Mixed | MD + separate image attachments |

**WARNING**: Embedded images in MD cannot be analyzed. Must attach separately using @path.

---

## Phase 0: Skill Entry

### 0-1. Collect Service Name and Input

When invoked without input, use AskQuestion:

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
      "prompt": "What domain does this feature belong to?",
      "options": [
        {"id": "ecommerce", "label": "E-commerce"},
        {"id": "fintech", "label": "Fintech"},
        {"id": "manufacturing", "label": "Manufacturing"},
        {"id": "saas", "label": "SaaS/B2B"},
        {"id": "healthcare", "label": "Healthcare"},
        {"id": "other", "label": "Other (specify)"}
      ]
    }
  ]
}
```

### 0-2. Service Name Input

Ask for service name (lowercase, hyphen/underscore). Output: `docs/{serviceName}/spec.md`.

**serviceName rules**: lowercase English, hyphen(-) or underscore(_). Examples: `alert`, `user-auth`, `order_management`

After response → request file path or direct input → Phase 1.

## Phase 1: Input Collection

Confirm: materials path/content, brief feature purpose. If file already provided → Phase 2.

## Phase 2: Draft Analysis

1. Read all materials (vision for images)
2. Extract core features
3. Identify unclear areas
4. Organize draft structure

## Phase 3: Q&A Loop

```
Loop:
  1. Ask 1-2 highest priority questions
  2. Receive answers
  3. Update document
  4. Check remaining unclear points
  Terminate when: all resolved OR user says "sufficient"
```

Rules: 1-2 questions at a time, provide options when possible, business perspective over technical.

## Phase 4: User Review

```json
{
  "title": "Requirements Document Review",
  "questions": [
    {
      "id": "review_result",
      "prompt": "Please review the requirements document. How would you like to proceed?",
      "options": [
        {"id": "approve", "label": "Approve - Save as is"},
        {"id": "modify", "label": "Modify - Need changes"},
        {"id": "add", "label": "Add - Missing content"},
        {"id": "restart", "label": "Restart - Wrong direction"}
      ]
    }
  ]
}
```

- approve → Phase 5
- modify/add → return to Phase 3
- restart → return to Phase 2

## Phase 5: Save

Path: `docs/{serviceName}/spec.md`. Create folder if needed.

> **Document Complete.** Next: Run `/arch` with `@docs/{serviceName}/spec.md`.

---

# Output Template

```markdown
# Requirements Definition: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Source Material: {input file path}
> Domain: {domain}

## 0. Requirement Summary

| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | {category} | {description} | High/Medium/Low | Draft |

> **Req ID Rule**: `FR-{number}` format. New = max + 1. Never reuse deleted numbers.
> **Status**: `Draft` → `Designed` (after arch) → `Implemented` (after build)

## 0.5. Development Target
- [ ] Backend
- [ ] Frontend
- [ ] Both

## 1. Business Context
### Purpose
### Users
### Problem to Solve

## 2. Feature Specification
### 2-1. Backend Perspective
### 2-2. Frontend Perspective

## 3. Related Existing Modules
| Type | Name | Impact |
|------|------|--------|

## 4. Non-Functional Requirements
| Item | Requirement |
|------|-------------|
| Performance | |
| Security | |
| Concurrency | |

## 4.5. Data Contract
### Input Data
| Field | Type | Required | Validation | Source |
### Output Data
| Field | Type | Description | Consumer |
### Data Permissions
| Data | Read | Write | Conditions |

## 4.6. Exception and Error Policy
### Expected Scenarios
| Scenario | Handling | User Message |
### Error Response Format
| HTTP Code | Error Code | Scenario |
### Recovery Strategy
- Retry Possible / Rollback Required / Notification Required

## 5. Unclear Items
- [ ] ...

## 6. Development Priority
### MVP (Must Have)
### Should Have
### Nice to Have

## 7. Completion Criteria
- [ ] ...
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
