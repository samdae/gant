---
id: check
name: Check
description: |
  Verify design document completeness before implementation.
  Identifies missing details based on defined components and asks user to fill gaps.

  Triggers: check, verify, validate design, 설계 검증, 검증
user-invocable: true
version: 1.0.0
triggers:
  - "check"
  - "verify"
  - "validate"
  - "design review"
requires: ["arch"]
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

# Architect Review Workflow

Verify design document completeness and identify missing details that will be needed during implementation.

## 💡 Recommended Model

**Sonnet** recommended (analysis task) / Opus for complex designs

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read** | Request file path from user → ask for copy-paste |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md      # Input (optional)
              ├── arch-be.md   # Input & Output (Backend)
              └── arch-fe.md   # Input & Output (Frontend)
```

---

## Phase -1: Service Discovery

1. **Scan `docs/`** for service directories.
2. **Select Service** (Auto or User selection).
3. **Resolve Paths**:
   - `arch-be.md` = `docs/{serviceName}/arch-be.md`
   - `arch-fe.md` = `docs/{serviceName}/arch-fe.md`

## Phase 0: Skill Entry

### 0-1. Model Recommendation

> 💡 **Sonnet is sufficient for this skill.**
> This is an analysis task, not a creative design task.

### 0-2. Collect Design Document

**If Service Discovery successful:**
- Loop through available arch files (`arch-be.md`, `arch-fe.md`).
- If only one exists, auto-select.
- If both exist, ask: "Check verification target: 1) Backend 2) Frontend".
- **Skip manual path input.**

**If Service Discovery failed:**
**Use AskQuestion:**

```json
{
  "title": "Architecture Review",
  "questions": [
    {
      "id": "design_doc",
      "prompt": "Which design document do you want to review?",
      "options": [
        {"id": "be", "label": "Backend (arch-be.md)"},
        {"id": "fe", "label": "Frontend (arch-fe.md)"},
        {"id": "filepath", "label": "I will provide via @filepath"}
      ]
    }
  ]
}
```

Or detect from context if user provides file path.

### 0-3. Load Design Document and Profile

**Detect from file path or user selection:**
- `arch-be.md` → **Read `profiles/be.md`** from this skill folder
- `arch-fe.md` → **Read `profiles/fe.md`** from this skill folder

> ⚠️ **MUST read the profile file before proceeding.**
> The profile defines component detection checklist and gap analysis items.

Read `docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`

If not found → Error: "Design document not found. Run /arch first."

---

## Phase 1: Component Detection

Scan the design document and detect which components are defined.

> ⚠️ **Use the checklist from the loaded profile (profiles/be.md or profiles/fe.md).**
> The profile contains component-specific detection methods and triggers.

### Detection Checklist (Profile Reference)

**For Backend (profiles/be.md):**
- Authentication, Database, REST API, External API
- Async processing, Real-time, File storage
- Caching, K8s/Docker, LLM/AI

**For Frontend (profiles/fe.md):**
- Component Structure, State Management, Routing
- Form Handling, API Integration, Authentication UI
- UX States, Accessibility, Responsive Design, Performance

---

## Phase 2: Gap Analysis

For each detected component, check if required details are defined.

> ⚠️ **Use the gap analysis checklists from the loaded profile.**
> Each profile contains component-specific gap checklists.

### Gap Analysis (Profile Reference)

**For Backend (profiles/be.md):**
- Authentication Gaps (token refresh, expiration, session)
- Database Gaps (soft delete, indexes, migration)
- REST API Gaps (pagination, rate limiting, versioning)
- External API Gaps (retry, caching, fallback, timeout)
- Async Processing Gaps (error handling, DLQ, idempotency)
- Real-time Gaps (timeout, reconnection, heartbeat)
- Infrastructure Gaps (health check, probes, logging)
- LLM/AI Gaps (cost tracking, limits, fallback)

**For Frontend (profiles/fe.md):**
- Component Structure Gaps (prop types, composition)
- State Management Gaps (scope, persistence, initialization)
- Routing Gaps (guards, 404 handling, lazy loading)
- Form Handling Gaps (validation, error display, submit)
- API Integration Gaps (loading, error, empty states)
- UX States Gaps (skeleton, error boundary, feedback)
- Accessibility Gaps (keyboard, focus, ARIA)
- Responsive Gaps (breakpoints, mobile layout)
- Performance Gaps (code splitting, memoization)

---

## Phase 3: Q&A Loop

For each gap found, ask user to fill:

**Use AskQuestion for choices:**

```json
{
  "title": "Missing Detail: Token Refresh",
  "questions": [
    {
      "id": "token_refresh",
      "prompt": "Token refresh logic is not defined. How should expired tokens be handled?",
      "options": [
        {"id": "refresh_token", "label": "Use refresh token (recommended)"},
        {"id": "re_login", "label": "Require re-login"},
        {"id": "long_expiry", "label": "Use long expiry (24h+)"},
        {"id": "skip", "label": "Skip for now (decide during implementation)"}
      ]
    }
  ]
}
```

**For open-ended questions:**

> "Pagination is not defined for list APIs. What should be the default page size?"
>
> Suggested: 20 items per page, max 100

### Skip Handling

If user selects "Skip for now":
- Mark as `⚠️ TBD` in document
- Continue to next gap
- List all skipped items at the end

---

## Phase 4: Document Update

Update `docs/{serviceName}/arch.md` with filled gaps.

### Update Location

Add new section or update existing sections:

```markdown
## 12. Additional Design Details (from Review)

### Authentication Details
- Token expiration: 1 hour
- Refresh token expiration: 7 days
- Refresh flow: POST /api/v1/auth/refresh with refresh_token

### API Details
- Pagination: 20 items default, 100 max
- Rate limiting: 100 requests/minute per user

### Infrastructure Details
- Health check: GET /health (returns 200 OK)
- Graceful shutdown: 30 second timeout

### ⚠️ TBD (Skipped)
- Monitoring strategy
- Log aggregation
```

### Sync History Update

Add to Sync History section:

```markdown
| {date} | review | check | 설계 완성도 검증 - {N}개 항목 추가 |
```

---

## Phase 5: Summary Report

Present review summary to user:

```markdown
## Architect Review Complete

### Components Detected
- ✅ Authentication (Google OAuth + JWT)
- ✅ Database (PostgreSQL, 10 tables)
- ✅ REST API (15 endpoints)
- ✅ Async Processing (Celery)
- ✅ Real-time (SSE)
- ✅ External APIs (4 services)
- ✅ LLM (OpenAI GPT-4)

### Gaps Filled: 8
| Item | Decision |
|------|----------|
| Token refresh | Use refresh token |
| Pagination | 20 items default |
| Health check | GET /health added |
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

> ✅ **Architecture Review Complete**
>
> Output: `docs/{serviceName}/arch-be.md` or `arch-fe.md` (updated)
>
> - Gaps filled: {N}
> - Skipped (TBD): {M}
>
> **Next Step**: Run `/build` to start implementation.

---

# Review Checklist Reference

Quick reference for common gaps by component:

| Component | Common Gaps |
|-----------|-------------|
| Auth | Token refresh, Session timeout, Logout flow |
| DB | Soft delete, Indexes, Cascade rules |
| API | Pagination, Rate limit, Versioning, Validation |
| External API | Retry, Cache, Timeout, Fallback |
| Async | Error handling, Retry, DLQ, Idempotency |
| Real-time | Timeout, Reconnect, Heartbeat |
| Infra | Health check, Probes, Graceful shutdown, Logging |
| LLM | Cost tracking, Limits, Fallback, Prompt versioning |
