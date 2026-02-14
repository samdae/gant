---
id: pre-build
name: Pre-build
description: |
  Verify implementation readiness before build.
  Checks external services, infrastructure, business logic details, and mock data preparation.

  Triggers: pre-build, prepare, ready check, 준비, 사전점검
user-invocable: true
version: 1.0.0
triggers:
  - "pre-build"
  - "prepare"
  - "ready"
  - "사전점검"
requires: ["arch", "check"]
platform: all
recommended_model: sonnet
allowed-tools:
  - Read
  - Write
  - Glob
  - LS
  - Grep
  - Shell
  - AskQuestion
---

> 🚫 **NO APPLICATION CODE GENERATION**
> This skill MUST NOT generate any **application source code**.
> Forbidden: routers, services, models, components, hooks, pages, controllers, repositories — anything under `src/`.
>
> ✅ **Allowed outputs:**
> - Updating the design document (arch-be.md / arch-fe.md) with `## Pre-build Preparation` section
> - Asking the user questions to fill gaps
> - Generating **dev infrastructure files** only:
>   - `docker-compose.yml` (DB, Redis, etc.)
>   - `.env.example` / `.env.local.example`
>   - `scripts/generate_mock.py` (data generation scripts)
>   - `Dockerfile` (if needed)
>
> Application code is the `/build` skill's responsibility.

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Pre-build Workflow

Verify implementation readiness by checking external services, infrastructure, business logic details, and data preparation before running `/build`.

## 💡 Recommended Model

**Sonnet** recommended (analysis + light generation task)

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read** | Request file path from user → ask for copy-paste |
| **Shell** | Ask user to run command and paste result |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |

## 📁 Document Structure

```
projectRoot/
  ├── docs/
  │     └── {serviceName}/
  │           ├── arch-be.md   # Input (Backend)
  │           └── arch-fe.md   # Input (Frontend)
  ├── .env.example             # Output (if missing)
  ├── docker-compose.yml       # Output (if needed)
  └── scripts/                 # Output (if needed)
```

---

## Phase -1: Service Discovery

1. **Scan `docs/`** for service directories.
2. **Select Service** (Auto or User selection).
3. **Resolve Paths**:
   - `arch-be.md` = `docs/{serviceName}/arch-be.md`
   - `arch-fe.md` = `docs/{serviceName}/arch-fe.md`

## Phase 0: Skill Entry

### 0-1. Collect Design Document

**If Service Discovery successful:**
- Loop through available arch files.
- If only one exists, auto-select.
- If both exist, ask: "Pre-build target: 1) Backend 2) Frontend 3) Both".

**If Service Discovery failed:**

```json
{
  "title": "Pre-build Check",
  "questions": [
    {
      "id": "design_doc",
      "prompt": "Which design document to check?",
      "options": [
        {"id": "be", "label": "Backend (arch-be.md)"},
        {"id": "fe", "label": "Frontend (arch-fe.md)"},
        {"id": "filepath", "label": "I will provide via @filepath"}
      ]
    }
  ]
}
```

### 0-2. Load Profile

- `arch-be.md` → **Read `profiles/be.md`** from this skill folder
- `arch-fe.md` → **Read `profiles/fe.md`** from this skill folder

> ⚠️ **MUST read the profile file before proceeding.**
> The profile defines check categories and generation templates.

---

## Phase 1: Parse Design Document

Extract the following sections from design document:

| Section | Extract Information |
|---------|---------------------|
| **Tech Stack** | `third_party` list, `database`, `cache`, `infra` |
| **Dependencies** | Package list with `status: approved` |
| **Implementation Plan** | Steps mentioning calculations, scoring, conversions |
| **Environment Variables** | Listed env vars |
| **Project Type** | `new` or `existing` |

---

## Phase 2: Dynamic Checklist Generation

Based on parsed content, generate checklist for each category:

### 2-1. External Services (from `third_party`)

**Trigger**: Any item in `third_party` section

| Detected Item | Check | Output if Missing |
|---------------|-------|-------------------|
| OAuth (Google, Kakao, etc.) | Client ID/Secret defined in .env? | Add to .env.example |
| LLM (OpenAI, Anthropic, etc.) | API Key defined? Usage limits known? | Add to .env.example + note limits |
| Payment (Stripe, etc.) | API Key + Webhook secret? | Add to .env.example |
| SMS/Email (Twilio, SendGrid) | API credentials ready? | Add to .env.example |

**Question Format:**

```json
{
  "title": "External Service: {service_name}",
  "questions": [
    {
      "id": "{service}_ready",
      "prompt": "{service_name} is listed in tech stack. Have you obtained the required credentials?",
      "options": [
        {"id": "yes", "label": "Yes - credentials ready"},
        {"id": "no", "label": "No - need to set up"},
        {"id": "skip", "label": "Skip (will set up later)"}
      ]
    }
  ]
}
```

### 2-2. Infrastructure (from `database`, `cache`, `infra`)

**Trigger**: Database, Redis, or infrastructure mentioned

| Detected Item | Check | Output if Missing |
|---------------|-------|-------------------|
| PostgreSQL/MySQL/MongoDB | docker-compose.yml exists? Connection test? | Generate docker-compose.yml |
| Redis | docker-compose.yml includes redis? | Add redis service |
| Docker mentioned | Dockerfile exists? | Note for manual creation |

**Shell Check (if available):**
```bash
# Check if docker is running
docker ps

# Check if compose file exists
test -f docker-compose.yml && echo "exists"
```

### 2-3. Business Logic Details (from Code Mapping)

**Trigger**: Code Mapping features containing:
- "계산", "calculate", "compute"
- "점수", "score", "rating"
- "변환", "convert", "transform"
- "평균", "average", "weighted"

**For each detected logic:**

```json
{
  "title": "Business Logic: {feature_name}",
  "questions": [
    {
      "id": "{feature}_formula",
      "prompt": "'{feature_name}' requires calculation logic. Is the formula/algorithm defined in the document?",
      "options": [
        {"id": "defined", "label": "Yes - already in document"},
        {"id": "define_now", "label": "No - I'll define it now"},
        {"id": "skip", "label": "Skip (decide during implementation)"}
      ]
    }
  ]
}
```

**If "define_now" selected:**
- Ask for formula/algorithm details
- Append to `## Business Logic Definitions` section in arch document

### 2-4. Mock/Seed Data (from Implementation Plan)

**Trigger**: Mentions of "mock", "seed", "fixture", "sample data", "test data"

| Check | Output if Missing |
|-------|-------------------|
| Mock data schema defined? | Generate schema template |
| Generation script exists? | Generate `scripts/generate_mock.py` or `.ts` |
| Sample data files exist? | Note required files |

### 2-5. Project Bootstrap (if `project_type: new`)

**For Backend:**
- Virtual environment setup command
- Package manager confirmed (pip, uv, poetry)

**For Frontend:**
- `create-next-app` / `create-vite` options confirmed
- UI library init commands (shadcn, etc.)
- Font installation method

---

## Phase 3: Execute Checks & Generate Files

For each missing item, either:
1. **Generate file** (docker-compose.yml, .env.example, scripts)
2. **Ask user** for input
3. **Mark as TBD** if skipped

### Generated File Templates

See `profiles/be.md` or `profiles/fe.md` for templates.

---

## Phase 4: Update Design Document

Add new section to arch document:

```markdown
## Pre-build Preparation (from Pre-build Check)

> Added: {date} via `/pre-build` skill

### External Services Status
| Service | Status | Notes |
|---------|--------|-------|
| Google OAuth | ✅ Ready | Client ID in .env |
| OpenAI | ⚠️ TBD | Need API key |

### Infrastructure Status
| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL | ✅ Ready | docker-compose.yml |
| Redis | ✅ Ready | docker-compose.yml |

### Business Logic Definitions
| Logic | Formula/Algorithm |
|-------|-------------------|
| 평균단가 | (기존수량×기존평단가 + 추가수량×매입가) / 총수량 |
| 수익률 | (현재가 - 평단가) / 평단가 × 100 |

### Mock Data Status
| Data | Status | Location |
|------|--------|----------|
| 시장 데이터 | ✅ Ready | data/mock/market.json |

### Generated Files
- `.env.example` - Environment variable template
- `docker-compose.yml` - Local development infrastructure
```

---

## Phase 5: Summary Report

```markdown
## Pre-build Check Complete

### Readiness Summary
| Category | Ready | TBD | Blocked |
|----------|-------|-----|---------|
| External Services | 2 | 1 | 0 |
| Infrastructure | 2 | 0 | 0 |
| Business Logic | 3 | 0 | 0 |
| Mock Data | 1 | 0 | 0 |

### Generated Files
- `.env.example` (12 variables)
- `docker-compose.yml` (PostgreSQL, Redis)
- `scripts/generate_mock.py`

### Action Required (TBD Items)
- [ ] Obtain OpenAI API key
- [ ] Define AI scoring weights

### Next Step
Run `/build` to start implementation.
```

---

## Completion Message

> ✅ **Pre-build Check Complete**
>
> Output: `docs/{serviceName}/arch-be.md` or `arch-fe.md` (updated)
>
> - Ready: {N} items
> - TBD: {M} items
> - Files generated: {K}
>
> **Next Step**: Run `/build` to start implementation.

---

## Check Category Reference

| Category | Trigger Keywords | Check Items |
|----------|-----------------|-------------|
| OAuth | oauth, google, kakao, social login | Client ID, Secret, Redirect URI |
| LLM | openai, anthropic, llm, ai, gpt, claude | API Key, Model name, Usage limits |
| Database | postgresql, mysql, mongodb, database | Connection, docker-compose, Migration tool |
| Cache | redis, cache, session store | Connection, docker-compose |
| Payment | stripe, payment, billing | API Key, Webhook secret |
| Calculation | 계산, calculate, score, 점수, average | Formula definition |
| Mock Data | mock, seed, fixture, sample | Schema, Generation script |
| Bootstrap | project_type: new | Init commands, Package manager |
