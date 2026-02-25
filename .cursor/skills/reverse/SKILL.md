---
id: reverse
name: reverse
description: |
  Reverse-engineer spec.md and arch.md from existing code.
  Triggers: reverse, reverse engineer, legacy documentation
user-invocable: true
version: 2.0.0
triggers: ["reverse", "reverse engineer", "code to document", "legacy documentation"]
requires: []
platform: all
recommended_model: opus
allowed-tools: [Read, Write, Glob, Grep, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Code Mapping `#` Rule**: Always use `max(existing #) + 1`. NEVER reuse deleted numbers.
> **Document Version Control**: After changes, commit recommended. Message: `docs({serviceName}): reverse - {summary}`. If git unavailable, skip.

# Reverse Workflow

Analyze codebase to reverse-engineer spec.md and arch.md documents.
**Model**: Opus Required - Must infer intent from code.

## Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user -> ask for copy-paste |
| **Glob** | Request file list from user |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB" format |
| **Task** | Sequential analysis without sub-agents, user confirmation at checkpoints |

## Document Structure

```
docs/{serviceName}/
  spec.md       <- output 1
  arch-be.md    <- output 2 (Backend)
  arch-fe.md    <- output 2 (Frontend)
  trace.md      (generated later by debug)
```

## Warnings

- **spec.md is inference**: The "why" is not visible in code. May be incomplete.
- **arch-be/fe.md is extraction**: Code Mapping, API Spec, DB Schema (BE) or Component Structure, Routes, State (FE) directly extracted.
- **Reinforce for enhancement**: Use reinforce skill to progressively enhance.

---

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> WARNING: **Strongly recommends Opus model.** Must infer business intent from code.
> Input: serviceName + code scope + code type (BE/FE). Output: `spec.md` + `arch-be/fe.md`
> Generated documents may be incomplete. Enhance with `reinforce`.

### 0-1. Basic Information Input

```json
{"title":"Start Legacy Documentation","questions":[
  {"id":"service_name","prompt":"Please enter the service name (e.g., alert, issue, worker-assign)","options":[{"id":"input","label":"I will provide directly"}]},
  {"id":"code_type","prompt":"What type of code are you analyzing?","options":[{"id":"be","label":"Backend - API server, business logic, database"},{"id":"fe","label":"Frontend - Web app, SPA, components"}]}
]}
```

**Load Profile**: `be` -> `profiles/be.md` / `fe` -> `profiles/fe.md`

> WARNING: **MUST read the profile file before proceeding.** Defines file patterns, extraction methods, output templates.

### 0-2. Code Scope Specification

```json
{"title":"Code Scope to Analyze","questions":[{"id":"scope_type","prompt":"What scope of code should be analyzed?","options":[
  {"id":"folder","label":"Specific folder - via @folderpath"},
  {"id":"files","label":"Specific files - via @filepath"},
  {"id":"pattern","label":"Pattern - Like apps/{serviceName}/**"}
]}]}
```

### 0-3. Additional Context (Optional)

```json
{"title":"Additional Information","questions":[{"id":"has_context","prompt":"Do you have any information about this service?","options":[{"id":"yes","label":"Yes - I will provide brief description"},{"id":"no","label":"No - Analyze from code only"}]}]}
```

- `yes` -> Use context provided by user in analysis
- `no` -> Analyze from code only

---

## Phase 1: Code Analysis

1. **File Structure**: Collect via Glob (source files, directory structure, configs)
2. **Identify Core Files** (use loaded profile patterns):

**Backend (profiles/be.md):**
| File Type | Extraction Target |
|----------|------------------|
| Router/Controller | API endpoints |
| Model/Entity | DB schema |
| Service/Usecase | Business logic |
| Repository/DAO | Data access |
| Schema/DTO | Data structures |
| Config files | Tech Stack |

**Frontend (profiles/fe.md):**
| File Type | Extraction Target |
|----------|------------------|
| Pages/Routes | Route structure |
| Components | Component hierarchy |
| Hooks | Custom logic |
| Store/State | State management |
| API Layer | API integration |
| Types | Type definitions |

3. **Read Code**: Analyze signatures, logic flow, dependencies, comments

---

## Phase 2: Information Extraction

**Direct extraction** (for arch, use profile methods):

**Backend:**
| Item | Extraction Method |
|------|------------------|
| Tech Stack | Import statements, dependency files |
| Code Mapping | File/class/method structure |
| API Spec | Router decorators, endpoint definitions |
| DB Schema | Model classes, migration files |
| Sequence Flow | Function call relationships |

**Frontend:**
| Item | Extraction Method |
|------|------------------|
| Tech Stack | package.json, config files |
| Component Structure | File/component hierarchy |
| State Management | Store files, hooks |
| Route Definition | Router config, file-based routing |
| API Integration | API hooks, service files |

**Inference** (for spec):

| Item | Inference Method |
|------|------------------|
| **Goal** | API names (BE) / UI patterns (FE), comments |
| **Feature specs** | Endpoint behavior (BE) / route structure (FE) |
| **Data contracts** | Schemas/DTOs (BE) / types (FE) |
| **Exception policy** | try-catch, error handlers |

**Cannot extract** (Q&A): Non-goals, priority, tradeoff reasons, business context.

---

## Phase 3: Q&A Loop (Max 5 rounds)

### 3-1. Report Extraction Results

```markdown
### Directly Extracted
| Item | Content |
|------|---------|
| Tech Stack | {results} |
| API count | {N} endpoints |
| DB tables | {N} tables |

### Inferred (requires verification)
| Item | Content | Confidence |
|------|---------|------------|
| Goal | {inference} | High/Medium/Low |

### Unknown (questions needed)
- {item list}
```

### 3-2. Questions

```json
{"title":"Collect Additional Information (1/5)","questions":[{"id":"goal","prompt":"What is the business purpose of this service?","options":[
  {"id":"answer","label":"I will provide"},{"id":"skip","label":"Don't know - Skip"},{"id":"confirm","label":"Inference is correct: {inferred Goal}"}
]}]}
```

Repeat for unknowns. Terminate: all done, user says enough, or 5 rounds.

---

## Phase 4: Generate spec.md

```markdown
# {serviceName} Requirements
> WARNING: Reverse-engineered from code. Enhance with `reinforce`.

## 0. Requirement Summary
| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | {cat} | {inferred} | Medium | Implemented |

> Status = `Implemented` (reverse-engineered). Req ID: `FR-{N}`, new = max+1, never reuse.

## 1. Overview
### 1.1 Service Name
{serviceName}
### 1.2 Domain
{inferred or user input}
### 1.3 Development Focus
- [x] Backend / - [ ] Frontend

## 2. Purpose
### 2.1 Goal
{inferred or user input or "Requires verification"}
### 2.2 Non-goals
{user input or "Requires verification"}

## 3. Feature Specifications
### 3.1 Core Features
| Feature | Description | Confidence |
|---------|-------------|------------|
| {from API} | {desc} | High/Medium/Low |
### 3.2 Detailed Features
{inferred from API behavior}

## 4. Data Contracts
### 4.1 Main Entities
| Entity | Fields | Source |
|--------|--------|--------|
| {from models} | {fields} | Code |

## 5. Exception/Error Policy
{from error handlers}

## 6. Unclear Items
| Item | Status | Notes |
|------|--------|-------|
| {unknown} | Requires verification | Enhance with reinforce |

## 7. Priority
{user input or "Requires verification"}

## Reverse Extraction Info
| Item | Content |
|------|---------|
| Generated | {date} |
| Analysis scope | {code scope} |
| Skill version | reverse 2.0.0 |
```

---

## Phase 5: Generate arch.md

### 5-1. Use FEATURE_DESIGN_DOC_TEMPLATE format

| Section | Status |
|---------|--------|
| Summary / Scope | Inference |
| Architecture Impact | **Extraction** (Components, DB Schema) |
| **Code Mapping** | **Extraction** - with `#` and `Impl = [x]` |
| **API Spec** | **Extraction** |
| Sequence Diagram | Generate if inferable |
| Risks & Tradeoffs | User input or "Requires verification" |

### 5-1.5. Code Mapping Generation Rules

- Include `#` (sequential), `Spec Ref` (links to FR-xxx), `Impl = [x]` for ALL rows

```markdown
| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 1 | FR-001 | User Auth | auth/service.py | AuthService | login() | Handle login | [x] |
| 2 | FR-001 | User Auth | auth/service.py | AuthService | logout() | Handle logout | [x] |
| 3 | FR-002 | User CRUD | user/repo.py | UserRepo | create() | Create user | [x] |
```

> **Spec Ref must match Req IDs in spec.md** -> traceability: spec.md (FR-xxx) <-> arch.md (Spec Ref)

### 5-2. Reverse Extraction Indicator (top of document)

```markdown
> WARNING: Reverse-engineered from code.
> - **Extracted**: Code Mapping, API Spec, DB Schema (reliable)
> - **Inferred**: Goal, Scope, Sequence (requires verification)
> - **Unconfirmed**: Risks, Tradeoffs (enhance with reinforce)
```

---

## Phase 6: Save and Complete

Save: `docs/{serviceName}/spec.md`, `arch-be.md` or `arch-fe.md`

### Completion Report

```markdown
## Legacy Documentation Complete
### Generated Documents
| Document | Path | Completeness |
|----------|------|--------------|
| spec.md | docs/{serviceName}/spec.md | {N}% |
| arch-*.md | docs/{serviceName}/arch-*.md | {N}% |

### Completeness (per item)
| Item | BE Status | FE Status |
|------|-----------|-----------|
| Goal | Confirmed/Inferred/Unconfirmed | same |
| Code Mapping / Components | Extracted | Extracted |
| API Spec / Routes | Extracted | Extracted |
| DB Schema / State | Extracted | Extracted |
| Risks / User Flows | Unconfirmed | Inferred |

### Next Steps
1. Review docs -> 2. Enhance with /reinforce -> 3. Use standard pipeline
```

---

# Integration Flow

```
[Legacy Code] -> (Select BE or FE profile)
  [reverse] -> spec.md + arch-be/fe.md (incomplete)
  [reinforce] -> spec.md + arch.md (enhanced)
  (Complete) -> Can use sync/enhance/build
```

# Important Notes

1. **Requirements is inference** - "Why" not visible in code. Use confidence indicators. Verify.
2. **Arch is extraction + inference** - Code Mapping/API/DB reliable. Goal/Scope/Risks need verification.
3. **Progressive enhancement** - Don't expect perfection. Enhance with /reinforce.
4. **Token awareness** - Wide scope = high tokens. Specify scope appropriately.
