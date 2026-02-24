---
id: arch
name: arch
description: |
  Multi-agent debate to derive optimal design through two perspectives.
  Domain Architect + Best Practice Advisor collaborate in round-based debate.
  Triggers: arch, architecture, blueprint, 설계, 아키텍처
user-invocable: true
version: 2.0.0
triggers: ["arch", "architecture", "blueprint", "feature design"]
requires: ["spec"]
platform: all
recommended_model: opus
agents:
  debate: archflow:domain-architect, archflow:best-practice-advisor
allowed-tools: [Read, Write, Glob, Grep, LS, Task, AskQuestion]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.
> **Code Mapping `#` Rule**: Always use `max(existing #) + 1` for new rows. NEVER reuse deleted numbers.
> **Document Version Control**: After changes, commit recommended. Message: `docs({serviceName}): arch - {summary}`. If git unavailable, skip.
> **Req ID Parsing**: Extract from spec.md `## 0. Requirement Summary` table. Each Req ID maps to Code Mapping `Spec Ref` (1:N).

**Model**: Opus required. Design quality determines implementation quality.

# Arch Workflow

Two perspective sub-agents collaborate to derive optimal design.

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read/Grep | Request file path, ask for copy-paste |
| AskQuestion | "Please select: 1) A 2) B 3) C" format |
| Task | Use Self-Debate Pattern (see below) |

## Self-Debate Pattern (when Task unavailable)

Play two roles sequentially:

```
**Role A: Domain Architect** - Full project context, design that fits this project
  Considerations: Existing patterns, technical constraints, team familiarity

**Role B: Best Practice Advisor** - Feature requirements only, ideal design
  Considerations: Industry standards, scalability, maintainability

Phase 1: Role A provides design proposal

Phase 2 (Cross-Review): Switch to Role B.
  Review the Role A design and provide:
  1. What you agree with
  2. Concerns or risks
  3. Alternative suggestions
  4. Can we reach consensus? [Yes / Need discussion]

Phase 3 (Counter-Review): Return to Role A.
  Review Role B's feedback and provide:
  1. Valid points you can accept
  2. Points you must reject (with project-specific reasons)
  3. Proposed compromises
  4. Final stance: [Agreement / Need user decision]

Phase 4 (Synthesis): Synthesize both perspectives into final design.
  Document in "Risks & Tradeoffs":
  - Chosen approach
  - Rejected alternatives and why
  - Assumptions made
  - Points requiring user decision (if any)
```

**When to use**: Only when `Task` tool is unavailable.

## Document Structure

```
docs/{serviceName}/
  spec.md       <- input
  arch-be.md    <- output (Backend)
  arch-fe.md    <- output (Frontend)
  ui.md         <- input (FE only, from /ui skill)
```

**serviceName inference**: Extracted from input file path `docs/{serviceName}/spec.md`

## Role Definitions

| Agent | Role | Context |
|-------|------|---------|
| domain-architect | Project context-based design | Requirements + project structure |
| best-practice-advisor | Best practice suggestions | Feature request only (no context) |

## Phase -1: Service Discovery

### -1.1. Scan Docs Directory

1. List `docs/` subdirectories
2. **If 1 found** (e.g., `docs/auth`): auto-select, confirm with user
   **If multiple**: ask user to select. **If none**: manual input.
3. Auto-resolve paths:
   - `spec.md` = `docs/{serviceName}/spec.md`
   - `arch-be.md` = `docs/{serviceName}/arch-be.md`
   - `arch-fe.md` = `docs/{serviceName}/arch-fe.md`
   - `ui.md` = `docs/{serviceName}/ui.md`

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> **WARNING**: This skill strongly recommends Opus model.
> Design quality determines implementation quality, so maintain Opus even when cost savings are needed.
>
> **Input**: `docs/{serviceName}/spec.md` | **Output**: `docs/{serviceName}/arch-be.md` or `arch-fe.md`

### 0-1. Collect Input

**If serviceName resolved in Phase -1**: verify `spec.md` exists, proceed to 0-1.5.
If not exists: "Requirements not found at docs/{serviceName}/spec.md. Run /spec or /reverse first."

**If NOT resolved**:

```json
{"title":"Start Design Debate","questions":[{"id":"has_requirements","prompt":"Do you have a requirements document? (docs/{serviceName}/spec.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"},{"id":"no","label":"No - Need requirements refinement first"}]}]}
```

- `yes` -> Request file path -> 0-1.5
- `no` -> Guide to **spec** skill

### 0-1.5. Select Architecture Type (BE/FE)

```json
{"title":"Architecture Type","questions":[{"id":"arch_type","prompt":"What type of architecture are you designing?","options":[{"id":"be","label":"Backend - API server, business logic, database"},{"id":"fe","label":"Frontend - Web app, SPA, components"}]}]}
```

- `be` -> Read `templates/be.md`, use as output template
- `fe` -> Check for ui.md first, then read `templates/fe.md`

**WARNING**: MUST read the template file before proceeding to Phase 1.

### 0-1.6. Frontend Prerequisites (FE only)

Verify `docs/{serviceName}/ui.md` exists:

```json
{"title":"UI Specification Check","questions":[{"id":"has_ui_spec","prompt":"Do you have a UI specification? (docs/{serviceName}/ui.md)","options":[{"id":"yes","label":"Yes - I will provide via @filepath"},{"id":"no","label":"No - I need to run /ui first"}]}]}
```

- `yes` -> Request ui.md path -> Proceed to Phase 1
- `no` -> Show guidance:
  > **WARNING**: UI specification required for Frontend architecture.
  > Run `/ui` first to generate UI specification from:
  > - `docs/{serviceName}/spec.md`
  > - `docs/{serviceName}/arch-be.md`
  >
  > The ui.md defines screens, components, and interactions needed for arch-fe.

**NOTE**: Frontend arch input = spec.md + ui.md (NOT arch-be.md directly).

### 0-1.7. Project Type

```json
{"title":"Project Type","questions":[{"id":"project_type","prompt":"Is this a new project or existing project?","options":[{"id":"new","label":"New project - Start from scratch"},{"id":"existing","label":"Existing project - Has code already"}]}]}
```

- `new` -> 0-1.8 (Setup Strategy)
- `existing` -> 0-1.7a (Path Detection)

### 0-1.7a. Existing Project - Path Detection

Auto-detect by scanning for dependency files:

| Language | Files to Check | Detected Path |
|----------|----------------|---------------|
| Python | `pyproject.toml`, `requirements.txt` | Parent directory of file |
| Node.js | `package.json` | Parent directory of file |

```json
{"title":"Detected Project Paths","questions":[{"id":"path_confirm","prompt":"I found:\n- BE: {detected_be_path}\n- FE: {detected_fe_path}\n\nCorrect?","options":[{"id":"accept","label":"Yes - Use these paths"},{"id":"modify","label":"No - I will specify manually"}]}]}
```

- `accept` -> 0-1.7b | `modify` -> manual input -> 0-1.7b

### 0-1.7b. Existing Project - Auto-detect Dependencies

Read dependency files from detected paths. Extract:
- Installed packages with versions
- Package manager (from lock files: package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock)
- Run commands (from scripts in package.json or pyproject.toml)

-> Proceed to 0-1.9

### 0-1.8. Setup Strategy (New Projects)

```json
{"title":"Setup Strategy","questions":[{"id":"setup_strategy","prompt":"How would you like to configure the project?","options":[{"id":"recommend","label":"LLM Recommendation - AI proposes optimal setup based on requirements"},{"id":"manual","label":"Manual Selection - I will choose each option"}]}]}
```

- `recommend` -> 0-1.8a | `manual` -> 0-1.8b

### 0-1.8a. LLM Full Recommendation

Analyze spec.md and propose complete setup:
1. Project Structure (Monorepo / Monolith / Custom)
2. BE/FE Paths
3. Language, Framework, Database, ORM
4. Package Manager, Essential Libraries
5. Run Commands

```json
{"title":"Proposed Project Setup","questions":[{"id":"full_proposal","prompt":"Based on analysis:\n\n**Structure**: {type}\n- BE: {be_path} | FE: {fe_path}\n\n**Stack**: {lang} / {fw} / {db} / {orm}\n**PM**: {pm}\n**Run**: BE: {cmd_be} | FE: {cmd_fe}\n**Libraries**: {libs}\n\nAccept?","options":[{"id":"accept","label":"Accept - Proceed with this setup"},{"id":"modify","label":"Modify - Switch to manual selection"}]}]}
```

- `accept` -> Save all, proceed to 0-2 | `modify` -> 0-1.8b

### 0-1.8b. Manual Setup - Project Structure

```json
{"title":"Project Structure","questions":[{"id":"project_structure","prompt":"What project structure do you want?","options":[{"id":"monorepo","label":"Monorepo - BE+FE in same repo (apps/{serviceName}-api|web)"},{"id":"monolith","label":"Monolith - Single service (backend/, frontend/)"},{"id":"custom","label":"Custom - I will specify paths"}]}]}
```

- `monorepo` -> `apps/{serviceName}-api`, `apps/{serviceName}-web`
- `monolith` -> `backend/`, `frontend/`
- `custom` -> manual path input

### 0-1.8c. Manual Setup - Language & Framework

```json
{"title":"Language Selection","questions":[{"id":"language","prompt":"What programming language for backend?","options":[{"id":"python","label":"Python"},{"id":"typescript","label":"TypeScript (Node.js)"},{"id":"go","label":"Go"},{"id":"java","label":"Java"},{"id":"other","label":"Other (specify)"}]}]}
```

Then ask framework based on language:

| Language | Framework Options |
|----------|-------------------|
| Python | FastAPI, Django, Flask |
| TypeScript | NestJS, Express, Fastify |
| Go | Gin, Echo, Fiber |
| Java | Spring Boot, Quarkus |

### 0-1.8d. Manual Setup - Database & ORM

```json
{"title":"Database Selection","questions":[{"id":"database","prompt":"What database will you use?","options":[{"id":"postgresql","label":"PostgreSQL"},{"id":"mysql","label":"MySQL / MariaDB"},{"id":"mongodb","label":"MongoDB"},{"id":"sqlite","label":"SQLite"},{"id":"none","label":"No database"},{"id":"other","label":"Other (specify)"}]}]}
```

ORM by language:

| Language | ORM Options |
|----------|-------------|
| Python | SQLAlchemy, Tortoise ORM, Raw SQL |
| TypeScript | Prisma, TypeORM, Drizzle, Raw SQL |
| Go | GORM, sqlx, Raw SQL |
| Java | JPA/Hibernate, MyBatis, Raw SQL |

### 0-1.8e. Manual Setup - Package Manager

**Python**:
```json
{"title":"Python Package Manager","questions":[{"id":"python_pkg_manager","prompt":"Which package manager?","options":[{"id":"uv","label":"uv - Fast, modern"},{"id":"pip","label":"pip + venv - Standard Python"},{"id":"poetry","label":"Poetry - Dep management + packaging"}]}]}
```

**Node.js**:
```json
{"title":"Node Package Manager","questions":[{"id":"node_pkg_manager","prompt":"Which package manager?","options":[{"id":"npm","label":"npm - Default Node.js"},{"id":"yarn","label":"Yarn - Fast, reliable"},{"id":"pnpm","label":"pnpm - Efficient disk space"}]}]}
```

-> After all manual selections, proceed to 0-1.9

### 0-1.9. Library Review

Analyze spec.md requirements, recommend libraries per feature:

```json
{"title":"Library Review: {feature_name}","questions":[{"id":"lib_{library_name}","prompt":"{library_name} ({version}) - {purpose}","options":[{"id":"use","label":"Use as recommended"},{"id":"skip","label":"Don't use"},{"id":"alt","label":"Use alternative (specify)"},{"id":"recommend","label":"Get LLM recommendation"}]}]}
```

For existing projects: show installed with markers, highlight missing.
Record decisions in Dependencies section.

### 0-2. Infer serviceName

Extract from path: `docs/alert/spec.md` -> serviceName = "alert"
Output: `docs/alert/arch-be.md` or `docs/alert/arch-fe.md`

## Phase 1: Initial Input Collection

Confirm requirements doc path (e.g., `@docs/alert/spec.md`).
If already provided -> Phase 1.5.

### Phase 1.5: Parse Requirement Summary

Read spec.md and extract Requirement Summary grid:

1. Find `## 0. Requirement Summary` section
2. Parse table: Req ID (FR-001, FR-002...), Category, Requirement, Priority
3. Store for Code Mapping: each Req ID -> Code Mapping `Spec Ref` (1:N)

**If not found**: warn "spec.md missing Requirement Summary grid", suggest `/reinforce`.

## Phase 2: Parallel Initial Design

### 2-A: Domain Architect (via Task)

```
Task(
  subagent_type: "domain-architect",
  description: "Project context-based design",
  prompt: """
    Requirements: {requirements MD content}
    Feature description: {feature description}
    Project structure: {project exploration results}
    Based on the above, provide a design proposal.
  """
)
```

Expected: design proposal (implementation approach, file structure, dependencies), constraints, tradeoffs.

### 2-B: Best Practice Advisor (via Task)

```
Task(
  subagent_type: "best-practice-advisor",
  description: "Best practice-based design",
  prompt: """
    Feature description: {feature description only, no project context}
    Provide an ideal design proposal for implementing this feature.
  """
)
```

Expected: ideal design (based on best practices), patterns/anti-patterns, considerations.

## Phase 3: Debate (Automated, 2 rounds)

Forward the following relay prompt to both agents:

```
From now on, I will relay another LLM's response.
That LLM was also instructed on the same feature definition.

Other agent's design:
{other_agent_response}

Review from your perspective and provide:
1. Points you agree with
2. Concerns
3. Alternative suggestions (if any)
4. Can we reach consensus: [Agree / Need further discussion]
```

**Round 1**: Domain Architect design -> Best Practice Advisor reviews.
**Round 2**: Best Practice review -> Domain Architect revises/rebuts.

## Phase 4: User Checkpoint

After 2 rounds, **must** provide interim report:

| Item | Domain Architect | Best Practice Advisor |
|------|------------------|----------------------|
| Core argument | (1-2 sentence) | (1-2 sentence) |
| Agreed points | (list) | (list) |
| Disputed points | (list) | (list) |

**Options** (AskQuestion, dynamically generated based on debate results):

| Field | Description |
|------|-------------|
| title | Reflect debate topic (e.g., "Alert Scheduling Design Debate") |
| prompt | Include report table summary above |
| options | 4 basic options below, adjust based on situation |

- `domain`: Adopt Domain Architect - Prioritize project reality
- `best`: Adopt Best Practice - Prioritize ideal design
- `continue`: 2 more rounds of debate
- `custom`: User combines on disputed points

**Option adjustment**: If both agree -> exclude `continue`. If one clearly superior -> mark as default.

**NOTE**: Run in Normal mode, not Plan mode. Can both intervene mid-process with AskQuestion + write final file.

## Phase 5: Follow-up

Options 1,2,4 -> Phase 6. Option 3 -> Rounds 3-4, auto-terminate after 4.
If no consensus: adopt Domain Architect + note Best Practice recommendations.

## Phase 5.5: Quality Gate Validation

Validate completeness based on arch_type before writing.

**Backend (BE):**

| Item | Validation Criteria | If Incomplete |
|------|-------------------|---------------|
| DB Schema | All tables have full column definitions | Enter question loop |
| Code Mapping | All features mapped to file/class/method | Enter question loop |
| API Spec | All endpoints have Request/Response defined | Enter question loop |
| Error Policy | Main error scenarios and responses defined | Enter question loop |

**Frontend (FE):**

| Item | Validation Criteria | If Incomplete |
|------|-------------------|---------------|
| Component Structure | Page and reusable component hierarchy | Enter question loop |
| Code Mapping | All features mapped to file/component/hook | Enter question loop |
| State Management | Global/Server/Local state defined | Enter question loop |
| Route Definition | Routes and auth guards defined | Enter question loop |
| API Integration | Backend endpoints connected to hooks | Enter question loop |

### Question Loop

```json
{"title":"Design Information Supplement Required","questions":[{"id":"missing_info","prompt":"Missing:\n- {list}\n\nHow to proceed?","options":[{"id":"provide","label":"Provide - I will provide the information"},{"id":"infer","label":"Allow inference - AI can estimate"},{"id":"skip","label":"Skip - I will supplement later"}]}]}
```

- `provide` -> user input | `infer` -> AI estimates, note in Assumptions | `skip` -> mark "[TBD]"

### Fail Gate (return to debate if empty)

**Backend:**

| Condition | Minimum Requirement |
|-----------|-------------------|
| **If API exists** | Request/Response spec + at least 2 error responses |
| **If Auth exists** | Role/Permission table with at least 1 entry |
| **If Data (DB) exists** | Core entity with at least 5 fields defined |

**Frontend:**

| Condition | Minimum Requirement |
|-----------|-------------------|
| **If Pages exist** | At least 1 page component with route defined |
| **If Auth exists** | Auth guard and protected route defined |
| **If API calls exist** | At least 1 hook/service with endpoint connection |
| **If State exists** | At least 1 global state store defined |

**WARNING**: If any fails -> re-enter Phase 5.5. When all pass -> Phase 6.

## Phase 6: Write Design Document

Write **implementation-ready design document** based on debate results.

| Section | Content | Source |
|---------|---------|--------|
| 0. Summary | Goal/Non-goals/Metrics | Requirements |
| 1. Scope | In/Out | Debate |
| 1.5. Tech Stack | Language, framework, DB, etc. | Exploration/user |
| 2. Architecture Impact | Components, Data | Domain Architect |
| 3. Code Mapping | Feature -> file/module | Domain Architect + exploration |
| 4. Implementation Plan | Order + reference files | Agreed priority |
| 5. Sequence Diagram | Main flow | Main agent |
| 6. API Specification | Endpoints, Req/Res | Main agent |
| 7. Infra/Ops | Env vars, deployment | Domain Architect |
| 8. Risks & Tradeoffs | Debate conclusion | Both agents |
| 9. Checklist | Error/Auth/Data | Error, auth, data integrity |

### Tech Stack (Section 1.5)

| Item | Examples |
|------|----------|
| Project Structure | Monorepo / Monolith / Custom |
| BE Path | `apps/auth-api` / `backend` / `./` |
| FE Path | `apps/auth-web` / `frontend` / `./` |
| Run Command (BE) | `uv run uvicorn main:app` / `npm run dev` |
| Run Command (FE) | `npm run dev` / `yarn dev` |
| Language | Python 3.11 / TypeScript 5.x / Go 1.21 / Java 17 |
| Framework | FastAPI / NestJS / Spring Boot / Gin |
| DB | PostgreSQL 15 / MySQL 8 / MongoDB 6 |
| ORM | SQLAlchemy / Prisma / TypeORM / GORM / None (Raw SQL) |
| Package Manager | uv / pip / poetry / npm / yarn / pnpm |
| 3rd-party | Redis, Kafka, S3, Elasticsearch, etc. |
| Infra | K8s / Docker / AWS / GCP / On-premise |

**NOTE**: BE/FE Paths and Run Commands used by `build`, `test`, `debug` skills.

### DB Changes (Section 2)

All tables must have full column definitions.

**Anti-patterns (Prohibited):**
- "Delete X field from existing table" (change without full schema)
- "Modify existing table" (unclear what columns exist)

Example:

| Column | Type | Change | Description |
|--------|------|--------|-------------|
| id | INTEGER | Maintain | PK |
| event_type | VARCHAR(100) | Maintain | Event type |
| reference_id | VARCHAR(100) | **New** | Related resource ID |
| ~~is_read~~ | ~~BOOLEAN~~ | **Delete** | Moved to separate table |

When manual SQL migration: record change types (CREATE TABLE / ALTER TABLE / CREATE INDEX) for build phase.

### Code Mapping (Section 3)

Require: full file path, class, method, call location, code to add.

**Anti-patterns (Prohibited):**
- "Call AlertPublisher from Issue service" (which method?)
- "src/services/*.py (modify)" (no specific file and method)

Example:

| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| 1 | Quality Create | `.../quality_issue/service.py` | `QualityIssueService` | `create_issue()` | After DB save call `_publish_create_alert()` | [ ] |
| 2 | Quality Resolve | `.../quality_issue/service.py` | `QualityIssueService` | `resolve_issue()` | After status change call `_publish_resolve_alert()` | [ ] |

> `[ ]` = not implemented, `[x]` = done by build. `#` = row number, never reused.

### Debate Conclusion (Section 8)

```markdown
## 8. Risks & Tradeoffs (Debate Conclusion)
### Chosen Option
- (adopted design approach)
### Rejected Alternatives
- (unadopted items and reasons)
### Reasoning
- Project constraints: ...
- Best practice adoption: ...
- Future improvement points: ...
### Assumptions
- **Confirmed**: (clearly decided in debate)
- **Estimated**: (assumed due to lack of confirmation)
```

### Save Path

`docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`

## Output Template

- Backend: `templates/be.md` | Frontend: `templates/fe.md`
- Located in `skills/arch/templates/`. Read selected template before writing.

## Template Reference (Backend - inline)

```markdown
# Backend Design Doc: {Feature Name}
> Created: {date} | Service: {serviceName} | Spec: docs/{serviceName}/spec.md
## 0. Summary
**Goal**: (1-2 sentences)
**Non-goals**: (excluded)
**Success metrics**: (criteria)
## 1. Scope
**In scope**: (items)
**Out of scope**: (future improvements)

## 1.5. Tech Stack
\`\`\`yaml
tech_stack:
  language: "{lang}"
  framework: "{fw}"
  database: "{db}"
  orm: "{orm}"
  third_party: ["{svc1}", "{svc2}"]
  infra: "{infra}"
\`\`\`
## 2. Architecture Impact
| Service/Module | Responsibility | Change type |
|----------------|----------------|-------------|
| {service} | {role} | new/modify |
### Database Schema
\`\`\`yaml
database_schema:
  new_tables:
    - name: "{table}"
      columns:
        - {name: "id", type: "INTEGER", constraints: ["PK","AUTO_INCREMENT"]}
        - {name: "{col}", type: "{type}", constraints: ["{c1}"], desc: "{desc}"}
        - {name: "created_at", type: "TIMESTAMP", constraints: ["NOT NULL","DEFAULT NOW()"]}
  modified_tables:
    - name: "{table}"
      changes:
        - {column: "{col}", type: "{type}", action: "ADD|DROP|MODIFY", desc: "{desc}"}
  indexes:
    - {table: "{tbl}", columns: ["{c1}","{c2}"], type: "BTREE", unique: false}
migrations:
  - {type: "CREATE_TABLE", table: "{tbl}", desc: "{desc}"}
  - {type: "ALTER_TABLE", table: "{tbl}", desc: "{change}"}
  - {type: "CREATE_INDEX", table: "{tbl}", desc: "{index desc}"}
\`\`\`
## 3. Code Mapping
| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| 1 | {feature} | {full path} | {class} | {method} | {action} | [ ] |
## 4. Implementation Plan
**Reference Files**: {path1} ({purpose}), {path2} ({purpose})
1. **{step}** - {tasks}
2. **{step}** - {tasks}
## 5. Sequence Diagram
\`\`\`mermaid
sequenceDiagram
    participant Client
    participant API
    participant Service
    participant DB
    Client->>API: {request}
    API->>Service: {call}
    Service->>DB: {query}
    DB-->>Service: {result}
    Service-->>API: {return}
    API-->>Client: {response}
\`\`\`
## 6. API Specification
\`\`\`yaml
api_endpoints:
  - name: "{api}"
    method: "{GET|POST|PUT|DELETE}"
    path: "/api/v1/{path}"
    auth_required: true
    request:
      headers: [{name: "Authorization", type: "string", required: true}]
      params: [{name: "{param}", type: "{type}", required: true}]
      body: {content_type: "application/json", schema: {field1: "{type}", field2: "{type}"}}
    response:
      success: {status: 200, schema: {success: "boolean", data: "{type}"}}
      errors:
        - {status: 400, code: "INVALID_INPUT", message: "{msg}"}
        - {status: 404, code: "NOT_FOUND", message: "{msg}"}
\`\`\`
## 7. Infra/Ops
| Variable | Description | Default |
|----------|-------------|---------|
| {VAR} | {desc} | {val} |
## 8. Risks & Tradeoffs
**Chosen**: {approach} | **Rejected**: {alternatives and why}
**Reasoning**: constraints: {reason}, best practice: {applied}, future: {later}
**Assumptions**: Confirmed: {decided} | Estimated: {assumed, needs verification}
## 9. Error/Auth/Data Checklist
**Error Handling**

| Situation | Location | Handling | Response |
|---|---|---|---|
| {scenario} | {file/method} | {try-catch/propagation/logging} | {HTTP code, msg} |

**Auth Rules**

| Action | Permission | Location | On Failure |
|---|---|---|---|
| {api} | {role} | {middleware} | {403/401} |

**Data Validation**

| Validation | Timing | On Failure |
|---|---|---|
| {FK existence} | {before save} | {400 + msg} |
| {Duplicate} | {on create} | {409 Conflict} |
| {Range} | {on input} | {422 + details} |
WARNING: If empty, 80% of implementation will be unstable - Must complete
```

## Phase 6.5: Update spec.md Status

After saving: read spec.md, find `## 0. Requirement Summary` table.
Update Status `Draft` -> `Designed` for each Req ID used in Code Mapping.

Example:
```markdown
| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | Auth | Email/password login | High | Designed |  <- Updated
| FR-002 | Auth | Social login | Medium | Designed |  <- Updated
```

## Completion

> **Design Document Complete**
> Saved to: `docs/{serviceName}/arch-be.md` or `arch-fe.md`
> Updated: spec.md (Status -> Designed)
> **Next**: Run `/build` (recommend Sonnet in new session)

## Integration Flow

```
[spec] -> spec.md -> [arch] -> arch-be/fe.md -> [build] -> Implementation -> (Bug) -> [debug] -> trace.md
```
