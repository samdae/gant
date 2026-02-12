# Backend Reverse Engineering Profile

> This profile is for reverse-engineering backend code.
> Use when analyzing API servers, business logic, databases.

## Code Type Detection

Keywords to detect backend code:
- `router`, `controller`, `endpoint`, `api`
- `model`, `entity`, `schema`, `migration`
- `service`, `usecase`, `repository`, `dao`
- `database`, `sql`, `orm`, `query`

---

## Core File Identification

### File Type to Target Mapping

| File Type | Extraction Target | Common Patterns |
|----------|------------------|-----------------|
| **Router/Controller** | API endpoints | `*_router.py`, `*Controller.ts`, `routes/*.js` |
| **Model/Entity** | DB schema | `models/*.py`, `entities/*.ts`, `*Model.java` |
| **Service/Usecase** | Business logic | `services/*.py`, `*Service.ts`, `usecases/*.go` |
| **Repository/DAO** | Data access | `repositories/*.py`, `*Repository.ts` |
| **Schema/DTO** | Data structures | `schemas/*.py`, `dto/*.ts`, `types/*.ts` |
| **Config files** | Tech Stack | `config.py`, `settings.ts`, `application.yml` |

### Directory Structure Patterns

```
Backend Project Structure:
├── app/ or src/
│   ├── api/ or routers/ or controllers/
│   ├── models/ or entities/
│   ├── services/ or usecases/
│   ├── repositories/ or dao/
│   ├── schemas/ or dto/
│   └── config/ or settings/
├── migrations/ or alembic/
├── tests/
└── requirements.txt / package.json / go.mod
```

---

## Direct Extraction Items

### Tech Stack Extraction

| Source | What to Extract |
|--------|-----------------|
| `requirements.txt` | Python packages (FastAPI, SQLAlchemy, etc.) |
| `package.json` | Node packages (Express, TypeORM, etc.) |
| `go.mod` | Go modules |
| `pom.xml` / `build.gradle` | Java dependencies |
| Import statements | Framework, ORM, libraries used |

### API Specification Extraction

| Framework | Detection Pattern |
|-----------|------------------|
| FastAPI | `@router.get()`, `@app.post()` |
| Express | `router.get()`, `app.post()` |
| NestJS | `@Get()`, `@Post()`, `@Controller()` |
| Spring | `@GetMapping`, `@PostMapping` |
| Gin | `r.GET()`, `r.POST()` |

**Extract for each endpoint:**
- HTTP method
- Path
- Request params/body
- Response schema
- Auth requirements (decorators)

### Database Schema Extraction

| ORM | Detection Pattern |
|-----|------------------|
| SQLAlchemy | `class Model(Base):`, `Column()` |
| TypeORM | `@Entity()`, `@Column()` |
| Prisma | `model Name { }` in schema.prisma |
| GORM | `type Model struct` with `gorm:` tags |
| Django | `class Model(models.Model):` |

**Extract for each table:**
- Table name
- Column definitions (name, type, constraints)
- Relationships (FK, indexes)

### Code Mapping Extraction

| Item | How to Extract |
|------|---------------|
| File path | Glob results |
| Class name | Parse class definitions |
| Method name | Parse function/method definitions |
| Dependencies | Analyze imports and injections |

**Output format (all rows have `Impl = [x]` since code exists):**

| # | Feature | File | Class | Method | Action | Impl |
|---|---------|------|-------|--------|--------|------|
| 1 | {inferred} | {path} | {class} | {method} | {description} | [x] |

---

## Inference Items

### Goal Inference

| Signal | Inference |
|--------|-----------|
| CRUD endpoints | "Manage {entity} data" |
| Auth endpoints | "Handle user authentication" |
| Payment/billing | "Process payments" |
| Notification endpoints | "Send notifications" |
| Analytics endpoints | "Track and report metrics" |

### Feature Inference

| Pattern | Inferred Feature |
|---------|-----------------|
| `/users/*` endpoints | User management |
| `/auth/*` endpoints | Authentication |
| `/admin/*` endpoints | Admin dashboard |
| Queue/Worker code | Background processing |
| WebSocket handlers | Real-time updates |

### Exception Policy Inference

| Pattern | Inference |
|---------|-----------|
| Custom exception classes | Defined error handling |
| `try-except` with specific exceptions | Error boundaries |
| HTTP status codes in responses | API error contracts |
| Logging in catch blocks | Error monitoring |

---

## Q&A Items (Cannot Extract)

### Required Questions

```json
{
  "questions": [
    {
      "id": "business_purpose",
      "prompt": "What is the main business purpose of this service?",
      "type": "open"
    },
    {
      "id": "users",
      "prompt": "Who are the primary users of this service?",
      "options": [
        {"id": "internal", "label": "Internal team/employees"},
        {"id": "b2b", "label": "Business customers (B2B)"},
        {"id": "b2c", "label": "End users (B2C)"},
        {"id": "mixed", "label": "Both internal and external"}
      ]
    },
    {
      "id": "non_goals",
      "prompt": "What does this service intentionally NOT do? (Out of scope)",
      "type": "open"
    },
    {
      "id": "critical_feature",
      "prompt": "Which feature is most business-critical?",
      "type": "open"
    }
  ]
}
```

---

## Output Templates

### spec.md Output Sections

```markdown
# Requirements (Reverse-engineered)

> ⚠️ Reverse-engineered from code. Verify with stakeholders.

## 1. Overview
- Service Name: {extracted}
- Domain: {inferred}
- Development Focus: [x] Backend

## 2. Purpose
- Goal: {inferred from API patterns} ❓
- Non-goals: {from Q&A}

## 3. Feature Specifications
| Feature | Description | Confidence |
|---------|-------------|------------|
| {from API} | {inferred} | High/Medium/Low |

## 4. Data Contracts
| Entity | Fields | Source |
|--------|--------|--------|
| {from models} | {extracted} | Code |

## 5. Exception Policy
{inferred from error handlers}
```

### arch-be.md Output Sections

```markdown
# Backend Design Doc (Reverse-engineered)

> ⚠️ Extracted from existing code.
> - **Extracted**: Code Mapping, API Spec, DB Schema (reliable)
> - **Inferred**: Goal, Scope (verify needed)

## 1.5. Tech Stack
{extracted from dependencies}

## 2. Architecture Impact
### Database Schema
{extracted from models}

## 3. Code Mapping
{extracted from file analysis}

## 6. API Specification
{extracted from routers}
```

---

## Completeness Indicators

| Section | Status | Meaning |
|---------|--------|---------|
| ✅ Extracted | Reliable | Directly from code |
| ❓ Inferred | Verify | Guessed from patterns |
| ❌ Unknown | Required | Need human input |
