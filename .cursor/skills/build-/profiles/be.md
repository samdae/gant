# Backend Build Profile

> This profile is for backend implementation.
> Use when input is `arch-be.md`.

## Input Detection

- Input file: `arch-be.md`
- Applies automatically when design document is backend-focused

---

## Package Installation (Phase 0.5)

**Backend-specific package managers:**

| Manager | Virtual Env | Install Command | Lock File |
|---------|-------------|-----------------|-----------|
| pip | `python -m venv .venv` | `pip install -r requirements.txt` | - |
| uv | `uv venv` | `uv pip install -r requirements.txt` | `uv.lock` |
| poetry | auto-managed | `poetry install` | `poetry.lock` |

**For new projects (project_type: new):**
1. Create virtual environment if needed
2. Install packages from Dependencies section

**For existing projects (project_type: existing):**
1. Check if virtual environment exists
2. Install only new packages (not already in requirements.txt/pyproject.toml)

**Example commands:**
```bash
# pip with venv
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install fastapi sqlalchemy alembic

# uv
uv venv
uv pip install fastapi sqlalchemy alembic

# poetry
poetry add fastapi sqlalchemy alembic
```

---

## Project Settings Questions

```json
{
  "title": "Backend Project Settings",
  "questions": [
    {
      "id": "orm_usage",
      "prompt": "Do you use ORM (Object-Relational Mapping)?",
      "options": [
        {"id": "yes", "label": "Yes - I will provide package name (SQLAlchemy, Prisma, TypeORM, etc.)"},
        {"id": "no", "label": "No - Using Raw SQL"}
      ]
    },
    {
      "id": "db_type",
      "prompt": "What database are you using?",
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
      "prompt": "Are there DB schema changes (table/column add/modify)? If yes, how to apply?",
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
      "id": "test_strategy",
      "prompt": "Test code writing?",
      "options": [
        {"id": "per_feature", "label": "Write test file per feature"},
        {"id": "per_design", "label": "Only when specified in design document"},
        {"id": "none", "label": "No test writing"}
      ]
    },
    {
      "id": "dependency_manager",
      "prompt": "Where to record when adding new libraries?",
      "options": [
        {"id": "project_default", "label": "Project default config file (package.json, pyproject.toml, go.mod, etc.)"},
        {"id": "manual", "label": "Manual management / separate document"},
        {"id": "none", "label": "No new dependencies"}
      ]
    }
  ]
}
```

**Additional questions:**
- When ORM used → Request ORM package name
- When DB version known → Request version string

---

## Dependency Graph

Backend implementation follows this dependency order:

```
0. shared/common (first)
   └── Utility functions, constants, types shared across modules

1. Model/Entity (independent)
   └── Database models, entity definitions
   └── ORM mappings

2. Repository/DAO (depends on Model)
   └── Data access layer
   └── Database queries

3. Service (depends on Repository)
   └── Business logic
   └── Validation, transformation

4. API/Controller (depends on Service)
   └── HTTP endpoints
   └── Request/Response handling
   └── Input validation

5. External Integration (independent or depends on API)
   └── Third-party API clients
   └── Message queue publishers/consumers
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

## Completion Report Template

```markdown
## Implementation Completion Report

### Execution Summary
| Step | Status | Created Files | Modified Files |
|------|--------|--------------|---------------|
| 1. Model | ✅ | {count} | {count} |
| 2. Repository | ✅ | {count} | {count} |
| 3. Service | ✅ | {count} | {count} |
| 4. API/Controller | ✅ | {count} | {count} |

### Created Files
- `path/to/new_file` - Description

### Modified Files
- `path/to/existing_file` - Change content

### DB Migration
(Based on project settings)

**When using migration tool:**
```bash
# Alembic
alembic revision --autogenerate -m "{description}"
alembic upgrade head

# Prisma
npx prisma migrate dev --name {description}

# Flyway
flyway migrate
```

**When manual SQL execution:**
```sql
-- New table: {table name}
CREATE TABLE {table name} (
  -- Generated based on design document Section 2 + {db_type} syntax
);

-- Existing table modification
ALTER TABLE {table name} ...;

-- Index
CREATE INDEX ...;
```

### Dependency Changes
(Based on project settings)
- `package_name` needs to be added → Record in project config file

### Remaining Manual Tasks
- [ ] Environment variable setup (if any)
- [ ] Run tests
- [ ] Verify FE integration

### Git Commit
(Based on commit strategy)
- Committed / Not committed

### Next Steps Guide
> ✅ **Implementation Complete**
>
> If bugs occur, run `debug` skill in **Debug mode**.
> Document paths: `docs/{serviceName}/spec.md`, `arch-be.md`
```

---

## Sub-agent Prompt Template

When invoking sub-agent for each step:

```
## Implementation Task

### Step Information
- Step name: {extracted from Implementation Plan}
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

⚠️ Only implement rows where `Impl = [ ]`
⚠️ If method name and call location specified, must implement at that location

### Design Spec
{API Spec, Sequence Diagram, etc. related parts}

### Already Created Files (for reference)
{list of files created in previous steps}

### Required Reference Patterns
**Reference File**: {required reference file path}
**Patterns to Apply**:
- Naming: {identified naming rules}
- Structure: {identified code structure}
- Error Handling: {identified error handling approach}

### Project Settings
- Test: {test_strategy}
- Commit: {commit_strategy}

### Implementation Rules (Must Follow)

#### 1. Read Existing File First (Top Priority)
- If target file to modify already exists, **must first Read entire content**
- Even for new files, **Read at least 1 similar file** in same directory
- No Write/Edit without reading first

#### 2. Search and Replicate Similar Code Patterns
- **Search for similar feature implementations with Grep** in project
- **Replicate naming, structure, error handling approach** of found patterns

#### 3. General Rules
- Auto-fix lint errors (max 3 attempts)
- Return list of created/modified files upon completion

#### 4. Update Implementation Status (IMPORTANT)
- After successfully implementing each Code Mapping row:
  1. Read the design document (arch-be.md)
  2. Find the row by `#` number in Code Mapping table
  3. Update `[ ]` → `[x]` using StrReplace
  - Example: `| 3 | Refresh | ... | [ ] |` → `| 3 | Refresh | ... | [x] |`

### Return Format
Report upon completion:
- created_files: [created file paths]
- modified_files: [modified file paths]
- impl_updated: [list of # numbers updated to [x]]
- status: success | failed
- error: (error content if failed)
```
