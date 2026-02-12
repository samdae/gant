---
id: arch
name: Arch
description: |
  Multi-agent debate to derive optimal design through two perspectives.
  Domain Architect + Best Practice Advisor collaborate in round-based debate.

  Triggers: arch, architecture, blueprint, 설계, 아키텍처
user-invocable: true
version: 2.0.0
triggers:
  - "arch"
  - "architecture"
  - "blueprint"
  - "feature design"
requires: ["spec"]
platform: all
recommended_model: opus
agents:
  debate: archflow:domain-architect, archflow:best-practice-advisor
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - LS
  - Task
  - AskQuestion
---

> ℹ️ **Global Rules Applied**:
> This skill adheres to the Archflow Global Rules defined in `rules/archflow-rules.md`.

# Arch Workflow

Two perspective sub-agents collaborate to derive optimal design.

## 💡 Recommended Model

**Opus Required** - Design quality determines implementation quality

→ Even when cost savings are needed, maintain Opus for this phase

## 🔄 Tool Fallback

| Tool | Alternative when unavailable |
|------|------------------------------|
| **Read/Grep** | Request file path from user → ask for copy-paste |
| **AskQuestion** | "Please select: 1) OptionA 2) OptionB 3) OptionC" format |
| **Task** | Use Self-debate Pattern instead of sub-agent calls |

## Sub-agent Alternative (when Task tool unavailable)

When the `Task` tool is unavailable for multi-agent collaboration, use the **Self-Debate Pattern**:

### Phase 1: Initial Prompt Split

```
You will play two roles in sequence to design this feature:

**Role A: Domain Architect**
- Context: Full project structure, requirements document
- Goal: Design that fits this specific project
- Considerations: Existing patterns, technical constraints, team familiarity

**Role B: Best Practice Advisor**
- Context: Feature requirements only (no project context)
- Goal: Ideal design based on universal best practices
- Considerations: Industry standards, scalability, maintainability

Start with Role A. After your design, I will ask you to switch to Role B.
```

### Phase 2: Cross-Review (Round 1)

```
Now switch to Role B (Best Practice Advisor).

Review the Role A design above and provide:
1. What you agree with
2. Concerns or risks
3. Alternative suggestions
4. Can we reach consensus? [Yes / Need discussion]
```

### Phase 3: Counter-Review (Round 2)

```
Now return to Role A (Domain Architect).

Review Role B's feedback and provide:
1. Valid points you can accept
2. Points you must reject (with project-specific reasons)
3. Proposed compromises
4. Final stance: [Agreement / Need user decision]
```

### Phase 4: Synthesis

```
Now synthesize both perspectives into a final design.
Document in "Risks & Tradeoffs" section:
- Chosen approach
- Rejected alternatives and why
- Assumptions made
- Points requiring user decision (if any)
```

**When to use**: Only when `Task` tool is unavailable and multi-perspective design is needed.

## 📁 Document Structure

```
projectRoot/
  └── docs/
        └── {serviceName}/
              ├── spec.md   # spec skill output
              ├── arch.md      # ← This skill's output
              └── trace.md      # debug skill output
```

**serviceName inference**: Automatically extracted from input file path `docs/{serviceName}/spec.md`


## Role Definitions

| Agent | Role | Context |
|-------|------|---------|
| domain-architect | Project context-based design | Requirements MD + project structure |
| best-practice-advisor | Best practice suggestions | Feature request only (no context) |

## Phase -1: Service Discovery

### -1.1. Scan Docs Directory

1. **List subdirectories** in `docs/` folder.
2. **Determine Service Name**:
   - **If 1 directory found** (e.g., `docs/auth`): Auto-select "auth" (Ask for confirmation: "Designing for 'auth' service?")
   - **If multiple found**: Ask user to select: "Which service? 1) auth 2) payment"
   - **If none found**: Ask user to input service name manually.

3. **Auto-resolve Paths**:
   - `spec.md` = `docs/{serviceName}/spec.md`
   - `arch-be.md` = `docs/{serviceName}/arch-be.md`
   - `arch-fe.md` = `docs/{serviceName}/arch-fe.md`
   - `ui.md` = `docs/{serviceName}/ui.md`

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> ⚠️ **This skill strongly recommends using the Opus model.**
> Design quality determines implementation quality, so maintain Opus for this phase even when cost savings are needed.
>
> **Input**: `docs/{serviceName}/spec.md`
> **Output**: `docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`

### 0-1. Collect Input Information

**If serviceName was NOT resolved in Phase -1:**

When skill is invoked without input, **use AskQuestion to guide information collection**:

```json
{
  "title": "Start Design Debate",
  "questions": [
    {
      "id": "has_requirements",
      "prompt": "Do you have a requirements document? (docs/{serviceName}/spec.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - Need requirements refinement first"}
      ]
    }
  ]
}
```

**Processing by response:**
- `yes` → Request file path → Proceed to 0-1.5
- `no` → Guide to **spec** skill

**If serviceName WAS resolved in Phase -1:**
- Verify `docs/{serviceName}/spec.md` exists.
- If exists, **skip this step** and proceed to 0-1.5 using the auto-resolved path.
- If not exists, error: "Requirements not found at docs/{serviceName}/spec.md. Run /spec or /reverse first."

### 0-1.5. Select Architecture Type (BE/FE)

```json
{
  "title": "Architecture Type",
  "questions": [
    {
      "id": "arch_type",
      "prompt": "What type of architecture are you designing?",
      "options": [
        {"id": "be", "label": "Backend - API server, business logic, database"},
        {"id": "fe", "label": "Frontend - Web app, SPA, components"}
      ]
    }
  ]
}
```

**Processing by response:**
- `be` → **Read `templates/be.md`** from this skill folder, use as output template
- `fe` → **Check for ui.md first**, then **Read `templates/fe.md`**

> ⚠️ **MUST read the template file before proceeding to Phase 1.**
> The template defines the document structure for this architecture type.

### 0-1.6. Frontend Prerequisites Check (FE only)

**When Frontend selected**, verify ui.md exists:

```json
{
  "title": "UI Specification Check",
  "questions": [
    {
      "id": "has_ui_spec",
      "prompt": "Do you have a UI specification? (docs/{serviceName}/ui.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - I need to run /ui first"}
      ]
    }
  ]
}
```

**Processing by response:**
- `yes` → Request ui.md path → Proceed to Phase 1
- `no` → Show guidance:
  > ⚠️ **UI specification required for Frontend architecture.**
  >
  > Run `/ui` first to generate UI specification from:
  > - `docs/{serviceName}/spec.md`
  > - `docs/{serviceName}/arch-be.md`
  >
  > The ui.md defines screens, components, and interactions needed for arch-fe.

> **Frontend arch input**: spec.md + ui.md (NOT arch-be.md directly)

### 0-1.7. Project Type

**Question 1: New or Existing Project**

```json
{
  "title": "Project Type",
  "questions": [
    {
      "id": "project_type",
      "prompt": "Is this a new project or existing project?",
      "options": [
        {"id": "new", "label": "New project - Start from scratch"},
        {"id": "existing", "label": "Existing project - Has code already"}
      ]
    }
  ]
}
```

**Processing by response:**
- `new` → Go to **0-1.8 (Setup Strategy)**
- `existing` → Go to **0-1.7a (Existing Project Path Detection)**

### 0-1.7a. Existing Project - Path Detection

**Auto-detect project paths by scanning for dependency files:**

| Language | Files to Check | Detected Path |
|----------|----------------|---------------|
| Python | `pyproject.toml`, `requirements.txt` | Parent directory of file |
| Node.js | `package.json` | Parent directory of file |

**Present detected paths:**

```json
{
  "title": "Detected Project Paths",
  "questions": [
    {
      "id": "path_confirm",
      "prompt": "I found the following project paths:\n- BE: {detected_be_path}\n- FE: {detected_fe_path}\n\nAre these correct?",
      "options": [
        {"id": "accept", "label": "Yes - Use these paths"},
        {"id": "modify", "label": "No - I will specify paths manually"}
      ]
    }
  ]
}
```

- `accept` → Save paths, proceed to **0-1.7b (Existing Project Dependencies)**
- `modify` → Ask for manual path input, then proceed to **0-1.7b**

### 0-1.7b. Existing Project - Auto-detect Dependencies

**Read dependency files from detected paths:**

| Language | Files to Check |
|----------|----------------|
| Python | `requirements.txt`, `pyproject.toml`, `Pipfile` |
| Node.js | `package.json` |

**Extract and present:**
- List of installed packages with versions
- Detect package manager from lock files (package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, uv.lock)
- Detect run commands from scripts (package.json scripts, pyproject.toml scripts)

→ Proceed to **0-1.9 (Library Review)**

---

### 0-1.8. Setup Strategy (New Projects Only)

**Question: LLM Recommendation or Manual Selection**

```json
{
  "title": "Setup Strategy",
  "questions": [
    {
      "id": "setup_strategy",
      "prompt": "How would you like to configure the project?",
      "options": [
        {"id": "recommend", "label": "LLM Recommendation - AI proposes optimal setup based on requirements"},
        {"id": "manual", "label": "Manual Selection - I will choose each option"}
      ]
    }
  ]
}
```

**Processing by response:**
- `recommend` → Go to **0-1.8a (LLM Full Recommendation)**
- `manual` → Go to **0-1.8b (Manual Setup)**

### 0-1.8a. LLM Full Recommendation

**Analyze spec.md and propose complete project setup:**

1. **Project Structure**: Monorepo / Monolith / Custom
2. **BE/FE Paths**: Based on structure (e.g., `apps/{serviceName}-api`, `apps/{serviceName}-web`)
3. **Language**: Python / TypeScript / Go / Java / etc.
4. **Framework**: FastAPI / NestJS / Spring Boot / etc.
5. **Database**: PostgreSQL / MySQL / MongoDB / etc.
6. **ORM**: SQLAlchemy / Prisma / TypeORM / None (Raw SQL)
7. **Package Manager**: uv / pip / npm / yarn / pnpm / etc.
8. **Essential Libraries**: Based on requirements analysis
9. **Run Commands**: Based on framework (e.g., `uv run uvicorn main:app`, `npm run dev`)

**Present Full Proposal:**

```json
{
  "title": "Proposed Project Setup",
  "questions": [
    {
      "id": "full_proposal",
      "prompt": "Based on requirements analysis, I recommend:\n\n**Project Structure**\n- Structure: {Monorepo/Monolith}\n- BE Path: {apps/serviceName-api}\n- FE Path: {apps/serviceName-web}\n\n**Tech Stack**\n- Language: {Language}\n- Framework: {Framework}\n- Database: {Database}\n- ORM: {ORM}\n- Package Manager: {PackageManager}\n\n**Run Commands**\n- BE: {run_command_be}\n- FE: {run_command_fe}\n\n**Libraries**\n- {lib1}, {lib2}, {lib3}...\n\nDo you accept this setup?",
      "options": [
        {"id": "accept", "label": "Accept - Proceed with this setup"},
        {"id": "modify", "label": "Modify - Switch to manual selection"}
      ]
    }
  ]
}
```

- `accept` → Save all decisions, proceed to **0-2 (Infer serviceName)**
- `modify` → Proceed to **0-1.8b (Manual Setup)**

### 0-1.8b. Manual Setup - Project Structure

**Question 1: Project Structure**

```json
{
  "title": "Project Structure",
  "questions": [
    {
      "id": "project_structure",
      "prompt": "What project structure do you want?",
      "options": [
        {"id": "monorepo", "label": "Monorepo - BE+FE in same repo (apps/{serviceName}-api|web)"},
        {"id": "monolith", "label": "Monolith - Single service (backend/, frontend/)"},
        {"id": "custom", "label": "Custom - I will specify paths"}
      ]
    }
  ]
}
```

**Processing by response:**
- `monorepo` → Set paths as `apps/{serviceName}-api`, `apps/{serviceName}-web`
- `monolith` → Set paths as `backend/`, `frontend/`
- `custom` → Ask for manual path input

### 0-1.8c. Manual Setup - Language & Framework

**Question: Language Selection**

```json
{
  "title": "Language Selection",
  "questions": [
    {
      "id": "language",
      "prompt": "What programming language for backend?",
      "options": [
        {"id": "python", "label": "Python"},
        {"id": "typescript", "label": "TypeScript (Node.js)"},
        {"id": "go", "label": "Go"},
        {"id": "java", "label": "Java"},
        {"id": "other", "label": "Other (specify)"}
      ]
    }
  ]
}
```

**Then ask framework based on language:**

| Language | Framework Options |
|----------|-------------------|
| Python | FastAPI, Django, Flask |
| TypeScript | NestJS, Express, Fastify |
| Go | Gin, Echo, Fiber |
| Java | Spring Boot, Quarkus |

### 0-1.8d. Manual Setup - Database & ORM

**Question: Database Selection**

```json
{
  "title": "Database Selection",
  "questions": [
    {
      "id": "database",
      "prompt": "What database will you use?",
      "options": [
        {"id": "postgresql", "label": "PostgreSQL"},
        {"id": "mysql", "label": "MySQL / MariaDB"},
        {"id": "mongodb", "label": "MongoDB"},
        {"id": "sqlite", "label": "SQLite"},
        {"id": "none", "label": "No database"},
        {"id": "other", "label": "Other (specify)"}
      ]
    }
  ]
}
```

**Then ask ORM based on language:**

| Language | ORM Options |
|----------|-------------|
| Python | SQLAlchemy, Tortoise ORM, Raw SQL |
| TypeScript | Prisma, TypeORM, Drizzle, Raw SQL |
| Go | GORM, sqlx, Raw SQL |
| Java | JPA/Hibernate, MyBatis, Raw SQL |

### 0-1.8e. Manual Setup - Package Manager

**For Python projects:**
```json
{
  "title": "Python Package Manager",
  "questions": [
    {
      "id": "python_pkg_manager",
      "prompt": "Which package manager do you want to use?",
      "options": [
        {"id": "uv", "label": "uv - Fast, modern package manager"},
        {"id": "pip", "label": "pip + venv - Standard Python"},
        {"id": "poetry", "label": "Poetry - Dependency management + packaging"}
      ]
    }
  ]
}
```

**For Node.js projects:**
```json
{
  "title": "Node Package Manager",
  "questions": [
    {
      "id": "node_pkg_manager",
      "prompt": "Which package manager do you want to use?",
      "options": [
        {"id": "npm", "label": "npm - Default Node.js"},
        {"id": "yarn", "label": "Yarn - Fast, reliable"},
        {"id": "pnpm", "label": "pnpm - Efficient disk space"}
      ]
    }
  ]
}
```

→ After all manual selections, proceed to **0-1.9 (Library Review)**

---

### 0-1.9. Library Review

**Based on spec.md requirements, extract needed libraries:**

1. Analyze functional requirements
2. Generate recommended library list for each feature
3. Present to user:

```json
{
  "title": "Library Review: {feature_name}",
  "questions": [
    {
      "id": "lib_{library_name}",
      "prompt": "{library_name} ({version}) - {purpose}",
      "options": [
        {"id": "use", "label": "Use as recommended"},
        {"id": "skip", "label": "Don't use"},
        {"id": "alt", "label": "Use alternative (specify)"},
        {"id": "recommend", "label": "Get LLM recommendation"}
      ]
    }
  ]
}
```

**For existing projects:**
- Show already installed libraries with ✅ marker
- Highlight missing libraries that need to be added

→ Record final decisions in Dependencies section of output document

### 0-2. Infer serviceName

Extract serviceName from provided file path:
- Input: `docs/alert/spec.md`
- Extract: `serviceName = "alert"`
- Output path:
  - BE: `docs/alert/arch-be.md`
  - FE: `docs/alert/arch-fe.md`

## Phase 1: Initial Input Collection

Confirm with user:
- Requirements document path (e.g., `@docs/alert/spec.md`)
- Feature description (if additional explanation needed)

**If file is already provided** → Proceed directly to Phase 1.5

### Phase 1.5: Parse Requirement Summary

**Read spec.md and extract Requirement Summary grid:**

1. Find `## 0. Requirement Summary` section
2. Parse the table to extract:
   - Req ID (e.g., FR-001, FR-002)
   - Category
   - Requirement description
   - Priority

3. Store for Code Mapping generation:
   - Each Req ID will be referenced in Code Mapping `Spec Ref` column
   - 1 Req ID can map to multiple Code Mapping rows (1:N relationship)

**If Requirement Summary not found:**
- Warn user: "spec.md is missing Requirement Summary grid"
- Suggest: "Run /reinforce to add Requirement Summary, or continue without traceability"

→ Proceed to Phase 2

## Phase 2: Parallel Initial Design

### 2-A: Invoke Domain Architect

**Use Task tool** to call `domain-architect` sub-agent:

```
Task(
  subagent_type: "domain-architect",
  description: "Project context-based design",
  prompt: """
    Requirements: {requirements MD content}
    Feature description: {feature description}
    Project structure: {project exploration results}

    Based on the above information, provide a design proposal.
  """
)
```

Expected output:
- Design proposal (implementation approach, file structure, dependencies)
- Project constraint considerations
- Concerns and tradeoffs

### 2-B: Invoke Best Practice Advisor

**Use Task tool** to call `best-practice-advisor` sub-agent:

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

Expected output:
- Ideal design proposal (based on best practices)
- Recommended patterns and anti-patterns
- General considerations

## Phase 3: Round 1 Debate (Automated)

Forward the following prompt to both agents:

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

### Round 1
- Domain Architect's design → Forward to Best Practice Advisor
- Best Practice Advisor returns review feedback

### Round 2
- Best Practice Advisor's review → Forward to Domain Architect
- Domain Architect returns revision/rebuttal

## Phase 4: User Checkpoint

After 2 rounds, **must** provide interim report to user.

### Report Format

| Item | Domain Architect | Best Practice Advisor |
|------|------------------|----------------------|
| Core argument | (1-2 sentence summary) | (1-2 sentence summary) |
| Agreed points | (list) | (list) |
| Disputed points | (list) | (list) |

### Present User Options

**Use AskQuestion tool** (content dynamically generated based on debate results):

| Field | Description |
|------|-------------|
| title | Reflect debate topic (e.g., "Alert Scheduling Design Debate") |
| prompt | Include above report format table summary |
| options | Provide 4 basic options below, adjust based on situation |

**Basic options:**
- `domain`: Adopt Domain Architect's approach - Prioritize project reality
- `best`: Adopt Best Practice approach - Prioritize ideal design
- `continue`: Continue debate - Proceed with 2 more rounds
- `custom`: Specify on disputed points - Directly combine

**Option adjustment rules:**
- If both agents agree → Exclude `continue`
- If one is clearly superior → Mark that option as default recommendation

**Note**: Run in Normal mode, not Plan mode. Can both intervene mid-process with AskQuestion + write final file.

## Phase 5: Follow-up Processing

### Options 1, 2, 4 → Proceed immediately to Phase 6
- Organize final design reflecting user decision

### Option 3 → Additional Debate
- Proceed with Round 3-4
- **Auto-terminate** after 4 rounds (prevent infinite loop)
- If no consensus → Adopt Domain Architect approach + note Best Practice recommendations

## Phase 5.5: Quality Gate Validation

Before writing design document, **validate completeness of required fields based on architecture type**:

### Required Validation Items (Branch by arch_type)

**Backend (arch_type = BE):**

| Item | Validation Criteria | If Incomplete |
|------|-------------------|---------------|
| DB Schema | All tables have full column definitions | Enter question loop |
| Code Mapping | All features mapped to file/class/method | Enter question loop |
| API Spec | All endpoints have Request/Response defined | Enter question loop |
| Error Policy | Main error scenarios and responses defined | Enter question loop |

**Frontend (arch_type = FE):**

| Item | Validation Criteria | If Incomplete |
|------|-------------------|---------------|
| Component Structure | Page and reusable component hierarchy defined | Enter question loop |
| Code Mapping | All features mapped to file/component/hook | Enter question loop |
| State Management | Global/Server/Local state defined | Enter question loop |
| Route Definition | Routes and auth guards defined | Enter question loop |
| API Integration | Backend endpoints connected to hooks/services | Enter question loop |

### Question Loop on Incomplete Items

```json
{
  "title": "Design Information Supplement Required",
  "questions": [
    {
      "id": "missing_info",
      "prompt": "The following information is missing:\n- {list of missing items}\n\nHow would you like to proceed?",
      "options": [
        {"id": "provide", "label": "Provide - I will provide the information"},
        {"id": "infer", "label": "Allow inference - AI can estimate"},
        {"id": "skip", "label": "Skip - I will supplement later"}
      ]
    }
  ]
}
```

- `provide` → Receive user input and supplement
- `infer` → AI estimates, note in Assumptions section
- `skip` → Mark item as "[TBD]" and proceed

### Minimum Completion Criteria (Fail Gate)

If **applicable items below are empty, return to debate phase**:

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

⚠️ If any item fails → Guide "Need supplemental information" and re-enter Phase 5.5

**When all required items pass** → Proceed to Phase 6

---

## Phase 6: Write Design Document

Write **implementation-ready design document** based on debate results.

### Section-by-Section Writing Guide

| Section | Content | Source |
|---------|---------|--------|
| 0. Summary | Goal/Non-goals/Success metrics | Extract from requirements MD |
| 1. Scope | In/Out scope | Scope confirmed in debate |
| 1.5. Tech Stack | Language, framework, DB, 3rd-party, infra | Project exploration or user input |
| 2. Architecture Impact | Components, Data changes | Domain Architect design |
| 3. Code Mapping | Feature → file/module mapping | Domain Architect design + project exploration |
| 4. Implementation Plan | Implementation order | Agreed priority |
| 5. Sequence Diagram | Main flow visualization | Main agent elaborates |
| 6. API Specification | Endpoints, Request/Response | Main agent elaborates |
| 7. Infra/Ops | Environment variables, deployment changes | Domain Architect design |
| 8. Risks & Tradeoffs | **Core debate conclusion** | Both arguments + adoption reasoning |
| 9. Error/Auth/Data Checklist | **3 essential checks** | Error handling, auth, data integrity |

### Section 1.5 Details (Tech Stack)

**Specify project tech stack:**

| Item | Examples |
|------|----------|
| **Project Structure** | Monorepo / Monolith / Custom |
| **BE Path** | `apps/auth-api` / `backend` / `./` |
| **FE Path** | `apps/auth-web` / `frontend` / `./` |
| **Run Command (BE)** | `uv run uvicorn main:app` / `npm run dev` |
| **Run Command (FE)** | `npm run dev` / `yarn dev` |
| Language | Python 3.11 / TypeScript 5.x / Go 1.21 / Java 17 |
| Framework | FastAPI / NestJS / Spring Boot / Gin |
| DB | PostgreSQL 15 / MySQL 8 / MongoDB 6 |
| ORM | SQLAlchemy / Prisma / TypeORM / GORM / None (Raw SQL) |
| Package Manager | uv / pip / poetry / npm / yarn / pnpm |
| 3rd-party | Redis, Kafka, S3, Elasticsearch, etc. |
| Infra | K8s / Docker / AWS / GCP / On-premise |

> **Note**: BE Path, FE Path, and Run Commands are used by `build`, `test`, and `debug` skills to locate and execute the project.

**Verify through project exploration or user input**

### Section 2 Details (Database Changes)

**All tables must have full column definitions:**

| Type | Content to Write |
|------|-----------------|
| New table | All column definitions (Column, Type, Constraints, Description) |
| Existing table modification | **Full schema before/after** or **Current full schema + changes noted** |

**Anti-patterns (Prohibited):**
- "Delete X field from existing table" (→ change mentioned without full schema)
- "Modify existing table" (→ unclear what columns exist)

**Example:**

| Column | Type | Change | Description |
|--------|------|--------|-------------|
| id | INTEGER | Maintain | PK |
| event_type | VARCHAR(100) | Maintain | Event type |
| reference_id | VARCHAR(100) | **New** | Related resource ID |
| ~~is_read~~ | ~~BOOLEAN~~ | **Delete** | → Moved to separate table |

### Section 2 Addition: Database Migration (when manual SQL selected)

When migration method is "manual SQL", record the following for SQL generation in implementation phase:

| Change Type | Table | Content |
|------------|-------|---------|
| CREATE TABLE | alert_read_status | New table |
| ALTER TABLE | alert | Delete is_read column |
| CREATE INDEX | alert_read_status | Add user_id index |

**Note**: Actual SQL will be generated for specific DB type in implementation phase

### Section 3 Details (Code Mapping - Integration)

**External service integration requires specific call locations:**

| Required Info | Description |
|--------------|-------------|
| File path | Full path (e.g., `apps/issue/src/services/quality_issue/service.py`) |
| Class name | Class to modify |
| **Method name** | Method to modify (e.g., `create_issue()`, `resolve_issue()`) |
| **Call location** | Point in method (e.g., "After DB save, before response return") |
| Code to call | Code snippet to add |

**Anti-patterns (Prohibited):**
- "Call AlertPublisher from Issue service" (→ which method?)
- "src/services/*.py (modify)" (→ no specific file and method)

**Example:**

| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| 1 | Quality Create | `.../quality_issue/service.py` | `QualityIssueService` | `create_issue()` | After DB save call `_publish_create_alert()` | [ ] |
| 2 | Quality Resolve | `.../quality_issue/service.py` | `QualityIssueService` | `resolve_issue()` | After status change call `_publish_resolve_alert()` | [ ] |

> **Impl column rules:**
> - `[ ]` = not implemented (initial state from arch)
> - `[x]` = implemented (updated by build after completion)
> - `#` column = row number for reference

### Section 8 Details (Debate Conclusion)

```markdown
## 8. Risks & Tradeoffs (Debate Conclusion)

### Chosen Option
- (adopted design approach)

### Rejected Alternatives
- (unadopted items from Best Practice proposals and reasons)

### Reasoning
- Project constraints: ...
- Best practice adoption: ...
- Future improvement points: ...

### Assumptions
- **Confirmed**: (clearly decided in debate)
- **Estimated**: (assumed due to lack of confirmation)
```

### Save Path

**Path**: `docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`

serviceName inferred from input file path:
- Input: `docs/alert/spec.md`
- Output (BE): `docs/alert/arch-be.md`
- Output (FE): `docs/alert/arch-fe.md`

---

# Output Document Template

> ⚠️ **Use the template from Phase 0-1.5 selection.**
>
> - **Backend**: Use template from `templates/be.md`
> - **Frontend**: Use template from `templates/fe.md`
>
> The templates are located in `skills/arch/templates/` folder.
> Read the selected template file and use it as the output document structure.

---

# Template Reference (Backend - for inline reference)

```markdown
# Backend Design Doc: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Requirements document: docs/{serviceName}/spec.md

## 0. Summary

### Goal
(Goal this feature aims to achieve - 1-2 sentences)

### Non-goals
- (Items excluded from this scope)

### Success metrics
- (List of success criteria)

---

## 1. Scope

### In scope
- (Items included in this implementation)

### Out of scope
- (Future improvements or excluded items)

---

## 1.5. Tech Stack

```yaml
tech_stack:
  language: "{language and version}"        # e.g., Python 3.11, TypeScript 5.x
  framework: "{framework}"                  # e.g., FastAPI, NestJS
  database: "{DB type and version}"         # e.g., PostgreSQL 15
  orm: "{ORM package or Raw SQL}"           # e.g., SQLAlchemy, Prisma
  third_party:                              # External services
    - "{service 1}"                         # e.g., Redis
    - "{service 2}"                         # e.g., Kafka
  infra: "{infra}"                          # e.g., K8s, Docker, AWS
```

---

## 2. Architecture Impact

### Components

| Service / Module | Responsibility | Change type |
|-----------------|----------------|-------------|
| {service name} | {role} | new / modify |

### Data

#### Database Schema

```yaml
database_schema:
  new_tables:
    - name: "{table_name}"
      description: "{table description}"
      columns:
        - name: "id"
          type: "INTEGER"
          constraints: ["PK", "AUTO_INCREMENT"]
          description: "Primary key"
        - name: "{column_name}"
          type: "{type}"
          constraints: ["{constraint1}", "{constraint2}"]
          description: "{description}"
        - name: "created_at"
          type: "TIMESTAMP"
          constraints: ["NOT NULL", "DEFAULT NOW()"]
          description: "Creation timestamp"

  modified_tables:
    - name: "{table_name}"
      changes:
        - column: "{column_name}"
          type: "{type}"
          action: "ADD"          # ADD | DROP | MODIFY
          description: "{description}"

  indexes:
    - table: "{table_name}"
      columns: ["{column1}", "{column2}"]
      type: "BTREE"              # BTREE | HASH | GIN | etc.
      unique: false
```

#### Migration Summary

```yaml
migrations:
  - type: "CREATE_TABLE"
    table: "{table}"
    description: "{description}"
  - type: "ALTER_TABLE"
    table: "{table}"
    description: "{change content}"
  - type: "CREATE_INDEX"
    table: "{table}"
    description: "{index description}"
```

---

## 3. Code Mapping

| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| 1 | {feature} | {full file path} | {class name} | {method name} | {call location and code to add} | [ ] |

---

## 4. Implementation Plan

### 📂 Required Reference Files (Must read before implementation)

| File | Reference Purpose |
|------|------------------|
| {file path 1} | {What to check in this file - patterns, style, dependencies, etc.} |
| {file path 2} | {reference purpose} |
| {file path 3} | {reference purpose} |

⚠️ **When running build skill, read above files first to understand patterns**

### Step-by-Step Implementation

1. **Step 1: {step name}**
   - {detailed task 1}
   - {detailed task 2}

2. **Step 2: {step name}**
   - {detailed task}

3. **Step 3: {step name}**
   - {detailed task}

---

## 5. Sequence Diagram

### {Flow name}

\`\`\`mermaid
sequenceDiagram
    participant Client
    participant API
    participant Service
    participant DB

    Client->>API: {request}
    API->>Service: {method call}
    Service->>DB: {DB operation}
    DB-->>Service: {result}
    Service-->>API: {return}
    API-->>Client: {response}
\`\`\`

---

## 6. API Specification

```yaml
api_endpoints:
  - name: "{API name}"
    method: "{GET|POST|PUT|DELETE}"
    path: "/api/v1/{path}"
    description: "{API description}"
    auth_required: true
    request:
      headers:
        - name: "Authorization"
          type: "string"
          required: true
      params:                    # Query params (GET) or Path params
        - name: "{param}"
          type: "{type}"
          required: true
      body:                      # Request body (POST/PUT)
        content_type: "application/json"
        schema:
          field1: "{type}"
          field2: "{type}"
    response:
      success:
        status: 200
        schema:
          success: "boolean"
          data: "{type or object}"
      errors:
        - status: 400
          code: "INVALID_INPUT"
          message: "{error message}"
        - status: 404
          code: "NOT_FOUND"
          message: "{error message}"
```

---

## 7. Infra/Ops

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| {VAR_NAME} | {description} | {value} |

### Deployment Changes
- (If needed)

---

## 8. Risks & Tradeoffs (Debate Conclusion)

### Chosen Option
- {adopted design approach}

### Rejected Alternatives
- {unadopted items and reasons}

### Reasoning
- Project constraints: {reason}
- Best practice adoption: {applied parts}
- Future improvement points: {what to do later}

### Assumptions
- **Confirmed**: {clearly decided in debate}
- **Estimated**: {assumed due to lack of confirmation - needs verification in implementation}

---

## 9. Error/Auth/Data Checklist (3 Essential Checks)

### Error Handling

| Situation | Location | Handling Method | Response |
|-----------|----------|----------------|----------|
| {exception scenario} | {file/method} | {try-catch/exception propagation/logging} | {HTTP code, error message} |

### Authorization

| Action | Required Permission | Validation Location | On Failure |
|--------|-------------------|-------------------|-----------|
| {API/feature} | {role/permission} | {middleware/service} | {403/401 response} |

### Data Integrity

| Validation Item | Validation Timing | On Failure |
|----------------|------------------|-----------|
| {FK existence} | {before save} | {400 + message} |
| {Duplicate check} | {on create} | {409 Conflict} |
| {Range validation} | {on input} | {422 + details} |

⚠️ **If this section is empty, 80% of implementation will be unstable** - Must complete
```

---

## Phase 6.5: Update spec.md Status

**After design document is saved, update spec.md Requirement Summary:**

1. Read `docs/{serviceName}/spec.md`
2. Find `## 0. Requirement Summary` table
3. For each Req ID used in Code Mapping:
   - Update Status from `Draft` to `Designed`
4. Save spec.md

**Example:**
```markdown
| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | Auth | 이메일/비밀번호 로그인 | High | Designed |  ← Updated
| FR-002 | Auth | 소셜 로그인 | Medium | Designed |  ← Updated
```

---

# Completion Guidance

After saving document, inform user:

> ✅ **Design Document Complete**
>
> Saved to: `docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`
> Updated: `docs/{serviceName}/spec.md` (Status → Designed)
>
> **Next Step**: Run `build` skill to begin implementation.
> → Recommended to switch to **Sonnet model** in new session (cost savings)

---

# Integration Flow

```
[spec] → docs/{serviceName}/spec.md
        ↓
[arch] → docs/{serviceName}/arch-be.md  (Backend)
       → docs/{serviceName}/arch-fe.md  (Frontend)
        ↓
[build] → Implementation
        ↓
(Bug occurs)
        ↓
[debug] → docs/{serviceName}/trace.md
```
