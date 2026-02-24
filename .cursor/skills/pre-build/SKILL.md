---
id: pre-build
name: pre-build
description: |
  Verify implementation readiness before build.
  Checks external services, infrastructure, business logic, mock data.
  Triggers: pre-build, prepare, ready check
user-invocable: true
version: 1.0.0
triggers: ["pre-build", "prepare", "ready"]
requires: ["arch", "check"]
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, Glob, LS, Grep, Shell, AskQuestion]
---

> **NO APPLICATION CODE GENERATION**
> This skill MUST NOT generate any **application source code**.
> Forbidden: routers, services, models, components, hooks, pages, controllers, repositories — anything under `src/`.
>
> Allowed outputs only:
> - Updating arch doc with `## Pre-build Preparation` section
> - Asking user questions to fill gaps
> - Dev infrastructure files: `docker-compose.yml`, `.env.example`, `scripts/generate_mock.py`, `Dockerfile`
>
> Application code is the `/build` skill's responsibility.

> **Global Rules**: Adheres to `rules/archflow-rules.md`.

**Model**: Sonnet (analysis + light generation).

# Pre-build Workflow

Verify readiness by checking external services, infrastructure, business logic details, and data preparation before `/build`.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read | Request file path from user -> ask for copy-paste |
| Shell | Ask user to run command and paste result |
| AskQuestion | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |

## Document Structure

```
projectRoot/
  ├── docs/{serviceName}/
  │     ├── arch-be.md   # Input (Backend)
  │     └── arch-fe.md   # Input (Frontend)
  ├── .env.example             # Output (if missing)
  ├── docker-compose.yml       # Output (if needed)
  └── scripts/                 # Output (if needed)
```

---

## Phase -1: Service Discovery

Scan `docs/` for service directories. Resolve `arch-be.md`, `arch-fe.md`.

## Phase 0: Skill Entry

### 0-1. Collect Design Document

**If Service Discovery successful:**
- If only one arch file, auto-select.
- If both exist, ask: "Pre-build target: 1) Backend 2) Frontend 3) Both".

**If Service Discovery failed:**

```json
{"title":"Pre-build Check","questions":[{"id":"design_doc","prompt":"Which design document to check?","options":[{"id":"be","label":"Backend (arch-be.md)"},{"id":"fe","label":"Frontend (arch-fe.md)"},{"id":"filepath","label":"I will provide via @filepath"}]}]}
```

### 0-2. Load Profile

- `arch-be.md` -> Read `profiles/be.md` from this skill folder
- `arch-fe.md` -> Read `profiles/fe.md` from this skill folder

**WARNING**: MUST read the profile file before proceeding. The profile defines check categories and generation templates.

---

## Phase 1: Parse Design Document

| Section | Extract |
|---------|---------|
| Tech Stack | `third_party` list, `database`, `cache`, `infra` |
| Dependencies | Package list with `status: approved` |
| Implementation Plan | Steps with calculations, scoring, conversions |
| Environment Variables | Listed env vars |
| Project Type | `new` or `existing` |

---

## Phase 2: Dynamic Checklist Generation

### 2-1. External Services (from `third_party`)

| Detected Item | Check | Output if Missing |
|---------------|-------|-------------------|
| OAuth (Google, Kakao) | Client ID/Secret in .env? | Add to .env.example |
| LLM (OpenAI, Anthropic) | API Key? Usage limits? | Add to .env.example + note limits |
| Payment (Stripe) | API Key + Webhook secret? | Add to .env.example |
| SMS/Email (Twilio, SendGrid) | API credentials ready? | Add to .env.example |

```json
{"title":"External Service: {service_name}","questions":[{"id":"{service}_ready","prompt":"{service_name} is listed in tech stack. Have you obtained the required credentials?","options":[{"id":"yes","label":"Yes - credentials ready"},{"id":"no","label":"No - need to set up"},{"id":"skip","label":"Skip (will set up later)"}]}]}
```

### 2-2. Infrastructure (from `database`, `cache`, `infra`)

| Detected Item | Check | Output if Missing |
|---------------|-------|-------------------|
| PostgreSQL/MySQL/MongoDB | docker-compose.yml exists? Connection test? | Generate docker-compose.yml |
| Redis | docker-compose.yml includes redis? | Add redis service |
| Docker mentioned | Dockerfile exists? | Note for manual creation |

**Shell Check (if available):**
```bash
docker ps
test -f docker-compose.yml && echo "exists"
```

### 2-3. Business Logic Details (from Code Mapping)

**Trigger keywords**: calculate, compute, score, rating, convert, transform, average, weighted

```json
{"title":"Business Logic: {feature_name}","questions":[{"id":"{feature}_formula","prompt":"'{feature_name}' requires calculation logic. Is the formula/algorithm defined in the document?","options":[{"id":"defined","label":"Yes - already in document"},{"id":"define_now","label":"No - I'll define it now"},{"id":"skip","label":"Skip (decide during implementation)"}]}]}
```

If "define_now": ask for formula/algorithm, append to `## Business Logic Definitions` in arch doc.

### 2-4. Mock/Seed Data

**Trigger**: mock, seed, fixture, sample data, test data

| Check | Output if Missing |
|-------|-------------------|
| Mock data schema defined? | Generate schema template |
| Generation script exists? | Generate `scripts/generate_mock.py` or `.ts` |
| Sample data files exist? | Note required files |

### 2-5. Project Bootstrap (if `project_type: new`)

**BE**: Virtual env setup, package manager (pip, uv, poetry).
**FE**: create-next-app/vite options, UI library init (shadcn), font installation.

---

## Phase 3: Execute Checks & Generate Files

For each missing item: generate file, ask user, or mark TBD.
See `profiles/be.md` or `profiles/fe.md` for file templates.

---

## Phase 4: Update Design Document

Add to arch document:

```markdown
## Pre-build Preparation (from Pre-build Check)

> Added: {date} via `/pre-build` skill

### External Services Status
| Service | Status | Notes |
|---------|--------|-------|
| Google OAuth | Ready | Client ID in .env |
| OpenAI | [TBD] | Need API key |

### Infrastructure Status
| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL | Ready | docker-compose.yml |
| Redis | Ready | docker-compose.yml |

### Business Logic Definitions
| Logic | Formula/Algorithm |
|-------|-------------------|
| Average price | (qty1*price1 + qty2*price2) / total_qty |
| Return rate | (current - avg_price) / avg_price * 100 |

### Mock Data Status
| Data | Status | Location |
|------|--------|----------|
| Market data | Ready | data/mock/market.json |

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

### Action Required (TBD)
- [ ] Obtain OpenAI API key
- [ ] Define AI scoring weights

### Next Step
Run `/build` to start implementation.
```

---

## Check Category Reference

| Category | Trigger Keywords | Check Items |
|----------|-----------------|-------------|
| OAuth | oauth, google, kakao, social login | Client ID, Secret, Redirect URI |
| LLM | openai, anthropic, llm, gpt, claude | API Key, Model, Usage limits |
| Database | postgresql, mysql, mongodb | Connection, docker-compose, migration |
| Cache | redis, cache, session store | Connection, docker-compose |
| Payment | stripe, payment, billing | API Key, Webhook secret |
| Calculation | calculate, score, average, weighted | Formula definition |
| Mock Data | mock, seed, fixture, sample | Schema, generation script |
| Bootstrap | project_type: new | Init commands, package manager |
