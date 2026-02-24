# Backend Build Profile

> Input: `arch-be.md`. Applies automatically for backend design documents.

---

## Package Installation (Phase 0.5)

| Manager | Virtual Env | Install Command | Lock File |
|---------|-------------|-----------------|-----------|
| pip | `python -m venv .venv` | `pip install -r requirements.txt` | - |
| uv | `uv venv` | `uv pip install -r requirements.txt` | `uv.lock` |
| poetry | auto-managed | `poetry install` | `poetry.lock` |

**New projects**: Create virtual environment first, then install from Dependencies section.
**Existing projects**: Check if venv exists, install only new packages.

```bash
# pip with venv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install fastapi sqlalchemy alembic

# uv
uv venv && uv pip install fastapi sqlalchemy alembic

# poetry
poetry add fastapi sqlalchemy alembic
```

---

## Project Settings Questions

Ask only what wasn't auto-detected from Tech Stack (0-2.5):

```json
{
  "title": "Backend Project Settings",
  "questions": [
    {
      "id": "orm_usage",
      "prompt": "Do you use ORM?",
      "options": [
        {"id": "yes", "label": "Yes - provide package name (SQLAlchemy, Prisma, TypeORM, etc.)"},
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
      "prompt": "DB version?",
      "options": [
        {"id": "known", "label": "Yes - will provide version"},
        {"id": "project", "label": "No - Check from project config"},
        {"id": "unknown", "label": "No - Use standard SQL (ANSI)"}
      ]
    },
    {
      "id": "db_schema_change",
      "prompt": "DB schema changes? How to apply?",
      "options": [
        {"id": "auto", "label": "Auto-apply on startup (ORM)"},
        {"id": "migration_tool", "label": "Migration tool (Alembic, Flyway, Prisma Migrate)"},
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
      "id": "test_strategy",
      "prompt": "Test code writing?",
      "options": [
        {"id": "per_feature", "label": "Write test per feature"},
        {"id": "per_design", "label": "Only when in design doc"},
        {"id": "none", "label": "No test writing"}
      ]
    },
    {
      "id": "dependency_manager",
      "prompt": "Where to record new libraries?",
      "options": [
        {"id": "project_default", "label": "Project default (package.json, pyproject.toml, go.mod)"},
        {"id": "manual", "label": "Manual / separate document"},
        {"id": "none", "label": "No new dependencies"}
      ]
    }
  ]
}
```

- ORM used -> Request ORM package name
- DB version known -> Request version string

---

## Dependency Graph

```
0. shared/common (first) - utilities, constants, types
1. Model/Entity (independent) - DB models, ORM mappings
2. Repository/DAO (depends on Model) - data access, queries
3. Service (depends on Repository) - business logic, validation
4. API/Controller (depends on Service) - HTTP endpoints, request/response
5. External Integration (independent or depends on API) - 3rd-party clients, MQ
```

### Parallel Execution Rules

| Step | Can Parallel With | Reason |
|------|-------------------|--------|
| Model + External Analysis | Yes | No dependencies |
| Repository | After Model | Depends on Model |
| Service | After Repository | Depends on Repository |
| API/Controller | After Service | Depends on Service |

> Execute sequentially when modifying same file to prevent conflicts

---

## Sub-agent Prompt Template

```
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
| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| {#} | {feature} | {file path} | {class name} | {method name} | {call location and code to add} | [ ] |

**WARNING**: Only implement rows where `Impl = [ ]`
**WARNING**: If method name and call location specified, must implement at that location

### Design Spec
{API Spec, Sequence Diagram, etc.}

### Already Created Files
{list from previous steps}

### Required Reference Patterns
**Reference File**: {path}
**Patterns to Apply**:
- Naming: {identified naming rules}
- Structure: {identified code structure}
- Error Handling: {identified error handling approach}

### Project Settings
- Test: {test_strategy}
- Commit: {commit_strategy}

### Implementation Rules (Must Follow)

**1. Read Existing File First (Top Priority)**
- If target file exists, **must Read entire content first**
- For new files, **Read at least 1 similar file** in same directory
- No Write/Edit without reading first

**2. Search and Replicate Similar Code Patterns**
- **Grep for similar implementations** in project
- **Replicate naming, structure, error handling** of found patterns

**3. General Rules**
- Auto-fix lint errors (max 3 attempts)
- Return list of created/modified files

**4. Update Implementation Status (IMPORTANT)**
- After implementing each Code Mapping row:
  1. Read design doc (arch-be.md)
  2. Find row by `#` in Code Mapping table
  3. Update `[ ]` -> `[x]` via StrReplace
  - Example: `| 3 | Refresh | ... | [ ] |` -> `| 3 | Refresh | ... | [x] |`

### Return Format
- created_files: [paths]
- modified_files: [paths]
- impl_updated: [# numbers updated to [x]]
- status: success | failed
- error: (if failed)
```

---

## Completion Report Template

```markdown
## Implementation Completion Report

### Execution Summary
| Step | Status | Created Files | Modified Files |
|------|--------|--------------|---------------|
| 1. Model | OK | {count} | {count} |
| 2. Repository | OK | {count} | {count} |
| 3. Service | OK | {count} | {count} |
| 4. API/Controller | OK | {count} | {count} |

### Created Files
- `path/to/new_file` - Description

### Modified Files
- `path/to/existing_file` - Change content

### DB Migration
(Based on project settings)

**When using migration tool:**
\`\`\`bash
# Alembic
alembic revision --autogenerate -m "{description}"
alembic upgrade head

# Prisma
npx prisma migrate dev --name {description}

# Flyway
flyway migrate
\`\`\`

**When manual SQL execution:**
\`\`\`sql
-- New table: {table name}
CREATE TABLE {table name} (
  -- Generated based on design doc + {db_type} syntax
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
> If bugs occur, run `debug` skill.
> Document paths: `docs/{serviceName}/spec.md`, `arch-be.md`
```
