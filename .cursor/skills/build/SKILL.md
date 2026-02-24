---
id: build
name: build
description: |
  Automated implementation based on design document.
  Analyzes arch.md, creates dependency graph, executes step-by-step.
  Triggers: build, compile, implement
user-invocable: true
version: 2.0.0
triggers: ["build", "compile", "implement", "generate code"]
requires: ["arch"]
platform: all
recommended_model: sonnet
allowed-tools: [Read, Write, StrReplace, Glob, Grep, LS, Shell, Task]
---

> **Global Rules**: Adheres to `rules/archflow-rules.md`.

# Build Workflow

Automated implementation based on design document (arch.md).

## Recommended Model

**Sonnet recommended** (cost-effective)
Design doc is detailed, high-performance model unnecessary. High token consumption makes cost savings significant.
**Run in new session after switching model.**

## Tool Fallback

| Tool | Alternative |
|------|-------------|
| Read/Grep | Request file path from user, ask for copy-paste |
| AskQuestion | "Please select: 1) A 2) B 3) C" format |
| Task | Execute step-by-step sequentially, report each step before next |

## Document Structure

```
docs/{serviceName}/
  arch-be.md  <- input (Backend)
  arch-fe.md  <- input (Frontend)
```

**serviceName inference**: Extracted from `docs/{serviceName}/arch-be.md` or `arch-fe.md`
**Prerequisites**: arch skill output with Implementation Plan, Code Mapping, Tech Stack sections.

---

## Phase -1: Service Discovery

1. List `docs/` subdirectories
2. If 1 found: auto-select. Multiple: ask user. None: manual input.
3. Auto-resolve: `arch-be.md` / `arch-fe.md` paths, profile = `profiles/be.md` or `fe.md`

## Phase 0: Skill Entry

### 0-0. Model Guidance (Display at start)

> **This skill recommends the Sonnet model.**
> Design doc is detailed, high-performance model unnecessary. High token consumption makes cost savings significant.
> **Switch model in a new session before running.**
> **Input**: `docs/{serviceName}/arch-be.md` or `docs/{serviceName}/arch-fe.md`

### 0-1. Verify Design Document

When invoked without input, use AskQuestion:

```json
{
  "title": "Start Implementation",
  "questions": [
    {
      "id": "has_design",
      "prompt": "Do you have a design document? (docs/{serviceName}/arch-be.md or arch-fe.md)",
      "options": [
        {"id": "yes", "label": "Yes - I will provide via @filepath"},
        {"id": "no", "label": "No - Need design document first"}
      ]
    }
  ]
}
```

- `no` -> Guide to **arch** skill
- `yes` -> Request file path -> Proceed to 0-2

### 0-2. Infer serviceName and Detect Profile

From path: `docs/alert/arch-be.md` -> serviceName="alert", profile=BE
Load profile: `profiles/be.md` or `profiles/fe.md`

**WARNING**: MUST read the profile file before proceeding. Profile defines project settings questions, dependency graph, and completion report template.

### 0-2.5. Pre-Analyze Design Document (Smart Detect)

Read `arch-be.md` or `arch-fe.md`, parse Tech Stack section. Extract: db_type, orm_usage, target_framework.
Goal: Skip redundant questions in 0-3.

### 0-3. Verify Project Settings (Only if needed)

Dynamic Question Generation: Based on 0-2.5 data, remove already-answered questions.
- If db_type detected -> Remove db_type question
- If orm_usage detected -> Remove orm_usage question

Remaining questions (ask only what is missing, use profile's full set excluding detected):

```json
{
  "title": "Project Settings",
  "questions": [
    {
      "id": "orm_usage",
      "prompt": "Do you use ORM?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide package name (SQLAlchemy, Prisma, TypeORM, etc.)"},
        {"id": "no", "label": "No - Using Raw SQL"}
      ]
    },
    {
      "id": "db_type",
      "prompt": "What database?",
      "options": [
        {"id": "postgresql", "label": "PostgreSQL"},
        {"id": "mysql", "label": "MySQL / MariaDB"},
        {"id": "sqlite", "label": "SQLite"},
        {"id": "mongodb", "label": "MongoDB"},
        {"id": "other", "label": "Other (specify)"}
      ]
    },
    {
      "id": "db_version",
      "prompt": "Do you know the DB version?",
      "options": [
        {"id": "known", "label": "Yes - I will provide version"},
        {"id": "project", "label": "No - Check from project config files"},
        {"id": "unknown", "label": "No - Use standard SQL (ANSI)"}
      ]
    },
    {
      "id": "db_schema_change",
      "prompt": "DB schema changes? How to apply?",
      "options": [
        {"id": "auto", "label": "Auto-apply on app startup (ORM, etc.)"},
        {"id": "migration_tool", "label": "Use migration tool (Alembic, Flyway, Prisma Migrate, etc.)"},
        {"id": "manual_sql", "label": "Manual SQL execution"},
        {"id": "none", "label": "No DB changes"}
      ]
    },
    {
      "id": "commit_strategy",
      "prompt": "Git commit strategy?",
      "options": [
        {"id": "none", "label": "No commit (default)"},
        {"id": "per_phase", "label": "Commit per step"},
        {"id": "final", "label": "Commit once after completion"}
      ]
    },
    {
      "id": "dependency_manager",
      "prompt": "Where to record new libraries?",
      "options": [
        {"id": "project_default", "label": "Project default config (package.json, pyproject.toml, go.mod, etc.)"},
        {"id": "manual", "label": "Manual management / separate document"},
        {"id": "none", "label": "No new dependencies"}
      ]
    }
  ]
}
```

- ORM used -> Request package name
- DB version known -> Request version

## Phase 0.5: Load Required Reference Files

Check design doc's **Section 4 > Required Reference Files**:
1. Load listed files with Read tool
2. Note patterns: naming, folder structure, error handling, import style
3. Include patterns in sub-agent prompts

If no reference files listed -> Auto-select 3 representative files from Code Mapping

## Phase 0.5b: Package Installation

**Before any code implementation, install required dependencies.**

Read Dependencies section from design doc:
```yaml
package_manager: "{pip|uv|poetry|npm|yarn|pnpm}"
dependencies:
  - name: "{package}"
    version: "{version}"
    status: "approved"      # Only install approved packages
```

| Package Manager | Install Command |
|-----------------|-----------------|
| pip | `pip install {package}=={version}` |
| uv | `uv pip install {package}=={version}` |
| poetry | `poetry add {package}@{version}` |
| npm | `npm install {package}@{version}` |
| yarn | `yarn add {package}@{version}` |
| pnpm | `pnpm add {package}@{version}` |

```bash
# pip example
pip install fastapi==0.109.0 sqlalchemy==2.0.25 alembic==1.13.1
# npm example
npm install react@18.2.0 zustand@4.5.0 axios@1.6.5
```

Execute via Shell, verify exit code. If failed: show error, ask user to resolve.
Report installed count and status before proceeding to Phase 1.

---

## Phase 1: Deep Analysis (Main Agent)

| Section | Extract Information |
|---------|-------------------|
| Tech Stack | Language, framework, DB, ORM, 3rd-party |
| Implementation Plan | Step-by-step task list |
| Code Mapping | File roles, new/modify, **method names/call locations** |
| Architecture Impact | DB changes (migration needed or not) |
| API Specification | Endpoint details |

### 1-1. Identify Common Files
Files in shared/common/utils/lib paths or referenced by multiple steps -> process first (step 0).

### 1-2. Dependency Graph
```
0. shared/common (first)
1. Model/Entity (independent)
2. Repository/DAO (depends on model)
3. Service (depends on repository)
4. API/Controller (depends on service)
5. External integration (independent or depends on API)
```

### 1-3. Plan Execution
| Step | Method | Reason |
|------|--------|--------|
| No dependencies | Parallel | Speed improvement |
| With dependencies | Sequential | Prior results needed |

### 1-4. Detect Migrations
Record DB changes (new tables, field add/delete, index changes) for Phase 4.

---

## Phase 2: Sub-agent Based Execution

### Architecture

```
Main Agent (Orchestrator) -- manage order, invoke, collect, intervene
    |
    v
Sub-agent per step (Task, subagent_type: "generalPurpose") -- independent context, return results to main
```

### 2-1. Sub-agent Invocation Pattern

```
Task(
  subagent_type: "generalPurpose",
  description: "Step N: {step name}",
  prompt: """
    ## Implementation Task

    ### Step Information
    - Step name: {from Implementation Plan}
    - Goal: {step description}

    ### Tech Stack
    - Language: {language}
    - Framework: {framework}
    - DB: {DB type} {version}
    - ORM: {ORM package name or "Raw SQL"}

    ### Code Mapping (files to handle in this step)
    **Pass rows with `Impl = [ ]` from design document Section 3:**
    | # | Feature | File | Class | Method | Action | Impl |
    |---|---------|------|-------|--------|--------|------|
    | {#} | {feature} | {file path} | {class name} | {method name} | {call location and code to add} | [ ] |

    **WARNING**: Only implement rows where `Impl = [ ]` (skip already implemented)
    **WARNING**: If method name and call location specified, must implement at that location

    ### Design Spec
    {API Spec, Sequence Diagram, etc. related parts}

    ### Already Created Files (for reference)
    {list of files created in previous steps}

    ### Required Reference Patterns (from Phase 0.5)
    **Reference File**: {path}
    **Patterns to Apply**:
    - Naming: {identified naming rules}
    - Structure: {identified code structure}
    - Error Handling: {identified error handling approach}

    ### Project Settings
    - Commit: {commit_strategy}

    ### Implementation Rules (Must Follow)

    **1. Read Existing File First (Top Priority)**
    - If target file exists, **must first Read entire content**
    - Even for new files, **Read at least 1 similar file** in same directory
    - No Write/Edit without reading first

    **2. Search and Replicate Similar Code Patterns**
    - **Search for similar implementations with Grep** in project
    - **Replicate naming, structure, error handling** of found patterns

    **3. General Rules**
    - Auto-fix lint errors (max 3 attempts)
    - Return list of created/modified files

    **4. Update Implementation Status (IMPORTANT)**
    - After implementing each Code Mapping row:
      1. Read design doc (arch-be.md or arch-fe.md)
      2. Find row by `#` number
      3. Update `[ ]` -> `[x]` via StrReplace

    ### Return Format
    - created_files: [paths]
    - modified_files: [paths]
    - status: success | failed
    - error: (if failed)
  """
)
```

### 2-2. Step-by-Step Execution Flow

```
Main Agent:
  for each step in Implementation Plan:
    1. Invoke sub-agent (Task)
    2. Wait for result
    3. Check result:
       - success -> next step
       - failed -> Phase 2-4 (request intervention)
    4. Commit if strategy is "per_phase"
    5. Accumulate created file list (pass to next step)
```

### 2-3. Parallel Execution
Independent steps (from dependency graph) can run simultaneously.

```
Example: Step 1 (Model) + Step 5 (External) -> parallel
         Step 2 (Repository) -> after Step 1 / Step 3 (Service) -> after Step 2
```

**WARNING**: Execute sequentially when modifying same file to prevent conflicts.

---

## Phase 2-4: Request Intervention on Issues

Conditions: failure after 3 retries, conflict with existing code, decision not in design doc.

```json
{
  "title": "Implementation Issue (Step N: {step name})",
  "questions": [
    {
      "id": "resolution",
      "prompt": "[Sub-agent error content]\n\nHow to proceed?",
      "options": [
        {"id": "retry", "label": "Retry (add hint)"},
        {"id": "option_a", "label": "[Solution A]"},
        {"id": "option_b", "label": "[Solution B]"},
        {"id": "skip", "label": "Skip this step"},
        {"id": "stop", "label": "Stop implementation"}
      ]
    }
  ]
}
```

When retry selected: user provides hint -> re-invoke sub-agent.

## Phase 3: Implementation Validation (Main Agent)

For each Code Mapping item:

1. **Grep** for method/class existence in corresponding file
2. **When exists**: Read 30 lines for validation (existence check). For modification: **200 lines above/below** or entire file (<500 lines)
   **WARNING**: When modifying, do not fix blindly based on only 30 lines -- Must understand style/error handling/DI/util usage approach
3. **When non-existent or misaligned** -> Implement supplement

### Validation Checklist

| Target | Method | Criteria |
|--------|--------|---------|
| Method exists | Grep | Method name match |
| Class exists | Grep | Class name match |
| Basic structure | Read 30 lines | Rough alignment with design |
| Context for modification | Read 200 lines/entire | Understand style, error handling, DI |

All items confirmed -> Phase 4.

---

## Phase 4: Completion Report (Main Agent)

### 4-1. Collect Results
Per sub-agent: created_files, modified_files, status.

### 4-2. Report Content

```markdown
## Implementation Completion Report

### Execution Summary
| Step | Status | Created Files | Modified Files |
|------|--------|--------------|---------------|
| 1. Model | OK | 2 | 0 |
| 2. Repository | OK | 1 | 1 |
| ... | ... | ... | ... |

### Created Files
- `path/to/new_file` - Description

### Modified Files
- `path/to/existing_file` - Change content

### DB Migration
(Based on project settings)

**When using migration tool:**
Tool-specific commands guidance

**When manual SQL execution:**
\`\`\`sql
-- New table: {table name}
CREATE TABLE {table name} (
  -- Generated based on design document Section 2 + {db_type} syntax
);
-- Existing table modification
ALTER TABLE {table name} ...;
-- Index
CREATE INDEX ...;
\`\`\`

### Dependency Changes
- `package_name` -> Record in project config file

### Remaining Manual Tasks
- [ ] Environment variable setup (if any)
- [ ] Run tests
- [ ] Verify FE integration

### Git Commit
(Based on commit strategy) Committed / Not committed

### Next Steps Guide
> **Implementation Complete**
> 1. **Verify**: Run `/test` for implemented code.
> 2. **Debug**: If bugs, run `/debug`.
> Document paths: `docs/{serviceName}/spec.md`, `arch-be.md` or `arch-fe.md`
```

### 4-3. Update spec.md Status

Read `docs/{serviceName}/spec.md`, find `## 0. Requirement Summary` table.
For each Req ID with `Impl = [x]`: update Status `Designed` -> `Implemented`.

```markdown
| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | Auth | Email/password login | High | Implemented |  <- Updated
| FR-002 | Auth | Social login | Medium | Implemented |  <- Updated
```

Completes SSOT cycle: Draft -> Designed -> Implemented.

### Commit Handling

| Strategy | Handling |
|---------|---------|
| none | User handles directly |
| per_phase | Already completed per step |
| final | Commit all changes at once |

---

## Integration Flow

```
[spec] -> [arch] -> [build] -> Implementation -> [debug] if bugs
```

## Important Notes

1. **Auto-executed**: file creation/modification, lint fixing, commit
2. **Not auto-executed (safety)**: DB migration, package install, server restart, tests
3. **Termination**: user selects "Stop", fatal error, or design doc parse failure
