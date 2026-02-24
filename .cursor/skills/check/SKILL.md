---
id: check
name: check
description: |
  Verify design document completeness before implementation.
  Triggers: check, verify, validate design
user-invocable: true
version: 1.0.0
triggers: ["check", "verify", "validate", "design review"]
requires: ["arch"]
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, LS, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.

**Model**: Sonnet (analysis task). Opus for complex designs.

# Check Workflow

Verify design document completeness and identify missing details for implementation.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request file path from user -> ask for copy-paste |
| AskQuestion | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |

## Document Structure

```
docs/{serviceName}/
  ├── spec.md      # Input (optional)
  ├── arch-be.md   # Input & Output (Backend)
  └── arch-fe.md   # Input & Output (Frontend)
```

---

## Phase -1: Service Discovery

Scan `docs/` for service directories. Auto-resolve `arch-be.md`, `arch-fe.md`.

## Phase 0: Skill Entry

### 0-1. Model Recommendation

Sonnet is sufficient for this analysis task.

### 0-2. Collect Design Document

**If Service Discovery successful:**
- If only one arch file exists, auto-select.
- If both exist, ask: "Check target: 1) Backend 2) Frontend".
- Skip manual path input.

**If Service Discovery failed:**

```json
{"title":"Architecture Review","questions":[{"id":"design_doc","prompt":"Which design document do you want to review?","options":[{"id":"be","label":"Backend (arch-be.md)"},{"id":"fe","label":"Frontend (arch-fe.md)"},{"id":"filepath","label":"I will provide via @filepath"}]}]}
```

### 0-3. Load Design Document and Profile

- `arch-be.md` -> Read `profiles/be.md` from this skill folder
- `arch-fe.md` -> Read `profiles/fe.md` from this skill folder

**WARNING**: MUST read the profile file before proceeding. The profile defines component detection checklist and gap analysis items.

Read `docs/{serviceName}/arch-be.md` or `arch-fe.md`. If not found -> Error: "Design document not found. Run /arch first."

---

## Phase 1: Component Detection

Scan the design document for defined components using the profile checklist.

**BE (profiles/be.md)**: Auth, DB, REST API, External API, Async, Real-time, File storage, Caching, K8s/Docker, LLM/AI.
**FE (profiles/fe.md)**: Component Structure, State, Routing, Forms, API Integration, Auth UI, UX States, A11y, Responsive, Performance.

---

## Phase 2: Gap Analysis

For each detected component, check if required details exist (per profile).

**BE gaps**: token refresh/expiration/session, soft delete/indexes/migration, pagination/rate limiting/versioning, retry/caching/fallback/timeout, error DLQ/idempotency, reconnection/heartbeat, health check/probes/logging, cost tracking/limits/fallback.
**FE gaps**: prop types/composition, state scope/persistence, route guards/404/lazy loading, validation/error display, loading/error/empty states, skeleton/error boundary, keyboard/focus/ARIA, breakpoints/mobile, code splitting/memoization.

---

## Phase 3: Q&A Loop

For each gap, ask user to fill. Use AskQuestion for choices:

```json
{"title":"Missing Detail: Token Refresh","questions":[{"id":"token_refresh","prompt":"Token refresh logic is not defined. How should expired tokens be handled?","options":[{"id":"refresh_token","label":"Use refresh token (recommended)"},{"id":"re_login","label":"Require re-login"},{"id":"long_expiry","label":"Use long expiry (24h+)"},{"id":"skip","label":"Skip for now (decide during implementation)"}]}]}
```

**For open-ended questions:**
> "Pagination is not defined for list APIs. What should be the default page size?"
> Suggested: 20 items per page, max 100

### Skip Handling

If user selects "Skip for now":
- Mark as `[TBD]` in document
- Continue to next gap
- List all skipped items at the end

---

## Phase 4: Document Update

Update `docs/{serviceName}/arch.md` with filled gaps.

```markdown
## 12. Additional Design Details (from Review)

### Authentication Details
- Token expiration: 1 hour
- Refresh flow: POST /api/v1/auth/refresh with refresh_token

### API Details
- Pagination: 20 items default, 100 max
- Rate limiting: 100 requests/minute per user

### Infrastructure Details
- Health check: GET /health (returns 200 OK)
- Graceful shutdown: 30 second timeout

### [TBD] (Skipped)
- Monitoring strategy
- Log aggregation
```

### Sync History Update

```markdown
| {date} | review | check | Design completeness review - {N} items added |
```

---

## Phase 5: Summary Report

```markdown
## Architect Review Complete

### Components Detected
- [x] Authentication (Google OAuth + JWT)
- [x] Database (PostgreSQL, 10 tables)
- [x] REST API (15 endpoints)
- [x] Async Processing (Celery)

### Gaps Filled: 8
| Item | Decision |
|------|----------|
| Token refresh | Use refresh token |
| Pagination | 20 items default |
| ... | ... |

### Skipped (TBD): 2
- Monitoring strategy
- Log aggregation

### Document Updated
`docs/{serviceName}/arch-be.md` or `arch-fe.md` - Section 12 added

### Next Step
Run `/build` to start implementation.
```

---

## Completion Message

> **Architecture Review Complete** - Output: `docs/{serviceName}/arch-be.md` or `arch-fe.md` (updated)
> Gaps filled: {N}, Skipped (TBD): {M}. **Next Step**: Run `/build`.

## Quick Reference

| Component | Common Gaps |
|-----------|-------------|
| Auth | Token refresh, session timeout, logout flow |
| DB | Soft delete, indexes, cascade rules |
| API | Pagination, rate limit, versioning, validation |
| External API | Retry, cache, timeout, fallback |
| Async | Error handling, DLQ, idempotency |
| Real-time | Timeout, reconnect, heartbeat |
| Infra | Health check, probes, graceful shutdown, logging |
| LLM | Cost tracking, limits, fallback, prompt versioning |
