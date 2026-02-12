---
id: reverse
name: Reverse
description: |
  Reverse-engineer requirements and design documents from existing code.
  Analyzes codebase and generates incomplete docs that need reinforcement.

  Triggers: reverse, reverse engineer, document existing code, 역설계
user-invocable: true
version: 2.0.0
triggers:
  - "reverse"
  - "reverse engineer"
  - "code to document"
  - "documentation"
  - "legacy documentation"
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

# Reverse Workflow

Analyze codebase to reverse-engineer spec.md and arch.md documents.

## 💡 Recommended Model

**Opus Required** - Must infer intent from code

→ Particularly for requirements, inferring the "why" requires a high-performance model

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user → ask for copy-paste |
| **Glob** | Request file list from user |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB" format |
| **Task** | Use sequential analysis without sub-agents, request user confirmation at checkpoints |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md       # ← This skill's output 1
              ├── arch-be.md    # ← This skill's output 2 (Backend)
              ├── arch-fe.md    # ← This skill's output 2 (Frontend)
              └── trace.md      # (generated later by debug)
```

## ⚠️ Warnings

- **spec.md is inference**: The "why" is not directly visible in code. May be incomplete.
- **arch-be/fe.md is extraction**: Code Mapping, API Spec, DB Schema (BE) or Component Structure, Routes, State (FE) are directly extracted from code.
- **Reinforce for enhancement**: Use reinforce skill to progressively enhance incomplete parts.

---

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> ⚠️ **This skill strongly recommends using the Opus model.**
> Must infer business intent from code, so high-performance model is required.
>
> **Input**: serviceName + code scope + code type (BE/FE)
> **Output**:
> - `docs/{serviceName}/spec.md`
> - `docs/{serviceName}/arch-be.md` (Backend) or `docs/{serviceName}/arch-fe.md` (Frontend)
>
> ⚠️ Generated documents may be incomplete. Enhance with `reinforce` skill.

### 0-1. Basic Information Input

When skill is invoked alone, **use AskQuestion to guide information collection**:

```json
{
  "title": "Start Legacy Documentation",
  "questions": [
    {
      "id": "service_name",
      "prompt": "Please enter the service name (e.g., alert, issue, worker-assign)",
      "options": [
        {"id": "input", "label": "I will provide directly"}
      ]
    },
    {
      "id": "code_type",
      "prompt": "What type of code are you analyzing?",
      "options": [
        {"id": "be", "label": "Backend - API server, business logic, database"},
        {"id": "fe", "label": "Frontend - Web app, SPA, components"}
      ]
    }
  ]
}
```

**Load Profile based on code_type:**
- `be` → **Read `profiles/be.md`** from this skill folder
- `fe` → **Read `profiles/fe.md`** from this skill folder

> ⚠️ **MUST read the profile file before proceeding.**
> The profile defines file patterns, extraction methods, and output templates.

### 0-2. Code Scope Specification

```json
{
  "title": "Code Scope to Analyze",
  "questions": [
    {
      "id": "scope_type",
      "prompt": "What scope of code should be analyzed?",
      "options": [
        {"id": "folder", "label": "Specific folder - I will provide via @folderpath"},
        {"id": "files", "label": "Specific files - I will provide via @filepath"},
        {"id": "pattern", "label": "Pattern specification - Like apps/{serviceName}/**"}
      ]
    }
  ]
}
```

### 0-3. Additional Context (Optional)

```json
{
  "title": "Additional Information",
  "questions": [
    {
      "id": "has_context",
      "prompt": "Do you have any information about this service?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide brief description"},
        {"id": "no", "label": "No - Analyze from code only"}
      ]
    }
  ]
}
```

- `yes` → Use context provided by user in analysis
- `no` → Analyze from code only

---

## Phase 1: Code Analysis

### 1-1. Understand File Structure

Collect file list from specified scope:

```
Collect file list using Glob:
  - *.py, *.ts, *.js, etc. source files
  - Directory structure: models/, schemas/, routers/, etc.
  - Configuration files (config, .env.example, etc.)
```

### 1-2. Identify Core Files

> ⚠️ **Use the file patterns from the loaded profile (profiles/be.md or profiles/fe.md).**

**For Backend (profiles/be.md):**
| File Type | Extraction Target |
|----------|------------------|
| Router/Controller | API endpoints |
| Model/Entity | DB schema |
| Service/Usecase | Business logic |
| Repository/DAO | Data access |
| Schema/DTO | Data structures |
| Config files | Tech Stack |

**For Frontend (profiles/fe.md):**
| File Type | Extraction Target |
|----------|------------------|
| Pages/Routes | Route structure |
| Components | Component hierarchy |
| Hooks | Custom logic |
| Store/State | State management |
| API Layer | API integration |
| Types | Type definitions |

### 1-3. Read Code

Analyze core files using Read:
- Class/function signatures
- Main logic flow
- Dependency relationships
- Comments (if any)

---

## Phase 2: Information Extraction

### 2-1. Direct Extraction (for architect)

> ⚠️ **Use extraction methods from the loaded profile.**

**For Backend (profiles/be.md):**
| Item | Extraction Method |
|------|------------------|
| Tech Stack | Analyze import statements, dependency files |
| Code Mapping | File/class/method structure |
| API Spec | Router decorators, endpoint definitions |
| DB Schema | Model classes, migration files |
| Sequence Flow | Track function call relationships |

**For Frontend (profiles/fe.md):**
| Item | Extraction Method |
|------|------------------|
| Tech Stack | Analyze package.json, config files |
| Component Structure | File/component hierarchy |
| State Management | Store files, hooks |
| Route Definition | Router config, file-based routing |
| API Integration | API hooks, service files |

### 2-2. Inference Required (for requirements)

| Item | Inference Method |
|------|------------------|
| **Goal** | Infer from API names (BE) / UI patterns (FE), comments |
| **Feature specs** | Infer from endpoint behavior (BE) / route structure (FE) |
| **Data contracts** | Infer from schemas/DTOs (BE) / types (FE) |
| **Exception policy** | Infer from try-catch, error handlers |

### 2-3. Cannot Extract (collect via Q&A)

| Item | Question |
|------|------|
| **Non-goals** | "What does this service intentionally NOT do?" |
| **Priority** | "Which feature is most important?" |
| **Tradeoff reasons** | "Why was this approach chosen?" |
| **Business context** | "Who are the users of this service?" |

---

## Phase 3: Q&A Loop (Max 5 rounds)

### 3-1. Report Extraction Results

```markdown
## Code Analysis Results

### Directly Extracted Information
| Item | Content |
|------|------|
| Tech Stack | {extraction results} |
| API count | {N} endpoints |
| DB tables | {N} tables |
| Main components | {list} |

### Inferred Information (requires verification)
| Item | Inferred Content | Confidence |
|------|----------|--------|
| Goal | {inference} | High/Medium/Low |
| Main features | {inference} | High/Medium/Low |

### Unknown Information (questions needed)
- {item 1}
- {item 2}
```

### 3-2. Questions

```json
{
  "title": "Collect Additional Information (1/5)",
  "questions": [
    {
      "id": "goal",
      "prompt": "What is the business purpose of this service?",
      "options": [
        {"id": "answer", "label": "I will provide"},
        {"id": "skip", "label": "Don't know - Skip"},
        {"id": "confirm", "label": "Inference is correct: {inferred Goal}"}
      ]
    }
  ]
}
```

**Repeat**: Ask about unknown information, proceed with blanks when user selects "Don't know"

### 3-3. Q&A Termination Conditions

- All core questions completed
- User selects "That's enough"
- 5 rounds reached

---

## Phase 4: Generate spec.md

### 4-1. Template

```markdown
# {serviceName} Requirements

> ⚠️ This document was reverse-engineered from code. Enhance with `reinforce` skill.

## 0. Requirement Summary

| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | {category} | {inferred from code} | Medium | Implemented |
| FR-002 | {category} | {inferred from code} | Medium | Implemented |

> **Status = `Implemented`**: Reverse-engineered from existing code (already built)
> **Req ID Rule**: `FR-{number}` format. New = max + 1. Never reuse deleted numbers.

## 1. Overview

### 1.1 Service Name
{serviceName}

### 1.2 Domain
{inferred or user input}

### 1.3 Development Focus
- [x] Backend
- [ ] Frontend

## 2. Purpose

### 2.1 Goal
{inferred or user input or "❓ Requires verification"}

### 2.2 Non-goals
{user input or "❓ Requires verification"}

## 3. Feature Specifications

### 3.1 Core Features
| Feature | Description | Confidence |
|------|------|--------|
| {inferred from API} | {description} | High/Medium/Low |

### 3.2 Detailed Features
{inferred from API behavior}

## 4. Data Contracts

### 4.1 Main Entities
| Entity | Fields | Source |
|--------|------|------|
| {extracted from models} | {field list} | Code |

## 5. Exception/Error Policy

{inferred from try-catch, error handlers}

## 6. Unclear Items

| Item | Status | Notes |
|------|------|------|
| {unknown items} | ❓ Requires verification | Enhance with reinforce |

## 7. Priority

{user input or "❓ Requires verification"}

---

## Reverse Extraction Info

| Item | Content |
|------|------|
| Generated | {date} |
| Analysis scope | {code scope} |
| Skill version | reverse 2.0.0 |
```

---

## Phase 5: Generate arch.md

### 5-1. Generate in FEATURE_DESIGN_DOC_TEMPLATE format

Generate in same format as arch skill output template, with:

| Section | Status |
|------|------|
| Summary | Inference (Goal/Non-goals) |
| Scope | Inference |
| Architecture Impact | **Extraction** (Components, DB Schema) |
| Sequence Diagram | Generate if can be inferred |
| **Code Mapping** | **Extraction** (Core) - with `#` and `Impl = [x]` |
| **API Spec** | **Extraction** (Core) |
| Implementation Plan | Already implemented → Skip or describe current structure |
| Risks & Tradeoffs | User input or "❓ Requires verification" |

### 5-1.5. Code Mapping Generation Rules

When generating Code Mapping from existing code:
- Include `#` column (sequential row numbers)
- Include `Spec Ref` column linking to spec.md Requirement IDs
- Include `Impl` column = `[x]` for ALL rows (code already exists = implemented)
- Example:

```markdown
| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 1 | FR-001 | User Auth | auth/service.py | AuthService | login() | Handle login | [x] |
| 2 | FR-001 | User Auth | auth/service.py | AuthService | logout() | Handle logout | [x] |
| 3 | FR-002 | User CRUD | user/repo.py | UserRepo | create() | Create user | [x] |
```

> **Spec Ref must match Req IDs in spec.md Requirement Summary**
> This creates traceability: spec.md (FR-xxx) ↔ arch.md (Spec Ref)

### 5-2. Reverse Extraction Indicator

Display at top of document:

```markdown
> ⚠️ This document was reverse-engineered from code.
> - **Extracted**: Code Mapping, API Spec, DB Schema (reliable)
> - **Inferred**: Goal, Scope, Sequence (requires verification)
> - **Unconfirmed**: Risks, Tradeoffs (enhance with reinforce)
```

---

## Phase 6: Save and Complete

### 6-1. Save Files

```
docs/{serviceName}/spec.md
docs/{serviceName}/arch-be.md  (if Backend)
docs/{serviceName}/arch-fe.md  (if Frontend)
```

### 6-2. Completion Report

```markdown
## Legacy Documentation Complete

### Generated Documents
| Document | Path | Completeness |
|------|------|--------|
| spec.md | docs/{serviceName}/spec.md | {N}% |
| arch-be/fe.md | docs/{serviceName}/arch-be.md or arch-fe.md | {N}% |

### Completeness Details (Backend)
| Item | Status |
|------|------|
| Goal | ✅ Confirmed / ❓ Inferred / ❌ Unconfirmed |
| Code Mapping | ✅ Extracted |
| API Spec | ✅ Extracted |
| DB Schema | ✅ Extracted |
| Risks | ❓ Unconfirmed |

### Completeness Details (Frontend)
| Item | Status |
|------|------|
| Goal | ✅ Confirmed / ❓ Inferred / ❌ Unconfirmed |
| Component Structure | ✅ Extracted |
| Routes | ✅ Extracted |
| State Management | ✅ Extracted |
| User Flows | ❓ Inferred |

### Unconfirmed Items (require reinforce enhancement)
- {item 1}
- {item 2}

### Next Steps
1. Review generated documents
2. Enhance unconfirmed items with `reinforce` skill
3. After enhancement, can use standard pipeline (sync/enhance)
```

---

# Integration Flow

```
[Legacy Code]
      │
      ▼ (Select BE or FE profile)
  [reverse] → spec.md (incomplete)
      │      → arch-be.md or arch-fe.md (incomplete)
      ▼
  [reinforce] → spec.md (enhanced)
      │        → arch.md (enhanced)
      ▼
   (Documents complete)
      │
      ▼
  Can use sync/enhance/build afterwards
```

---

# Important Notes

1. **requirements is inference result**
   - The "why" is not visible in code
   - Distinguish reliability with confidence indicators
   - Verification is mandatory

2. **arch is extraction + inference**
   - Code Mapping, API Spec, DB Schema are reliable
   - Goal, Scope, Risks are inference, require verification

3. **Progressive enhancement with reinforce**
   - Do not expect perfect documents at once
   - Enhance with reinforce when additional information is acquired

4. **Token awareness**
   - Wide code scope consumes many tokens
   - Specify scope appropriately
