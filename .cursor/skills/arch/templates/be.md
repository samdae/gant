# Backend Architecture Document Template

> This template is for backend-focused architecture design.
> Use this when the target is API server, business logic, database, etc.

## Output File

`docs/{serviceName}/arch-be.md`

---

## Template

```markdown
# Backend Design Doc: {Feature Name}

> Created: {date}
> Service: {serviceName}
> Type: Backend
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
  framework: "{framework}"                  # e.g., FastAPI, NestJS, Spring Boot
  database: "{DB type and version}"         # e.g., PostgreSQL 15
  orm: "{ORM package or Raw SQL}"           # e.g., SQLAlchemy, Prisma, TypeORM
  third_party:                              # External services
    - "{service 1}"                         # e.g., Redis
    - "{service 2}"                         # e.g., Kafka
  infra: "{infra}"                          # e.g., K8s, Docker, AWS
```

---

## 1.6. Dependencies

```yaml
package_manager: "{pip|uv|poetry}"          # Selected in Phase 0-1.7
project_type: "{new|existing}"              # New or existing project

dependencies:
  # Core framework
  - name: "{package name}"
    version: "{version or latest}"
    purpose: "{what it's used for}"
    status: "{approved|rejected|alternative}"
  
  # Database / ORM
  - name: "{package name}"
    version: "{version}"
    purpose: "{purpose}"
    status: "{status}"
  
  # Add more as needed...
```

> **Note**: This section is populated from Phase 0-1.7c Library Review.
> `status: approved` packages will be installed in build phase.

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

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 1 | FR-001 | {feature} | {full file path} | {class name} | {method name} | {call location and code to add} | [ ] |

> **Spec Ref**: Links to Requirement ID in spec.md (1 Req ID → multiple Code Mapping rows possible)
> **Impl column**: `[ ]` = not implemented, `[x]` = implemented
> - arch generates all rows with `[ ]`
> - build updates to `[x]` after implementation

---

## 4. Implementation Plan

### Required Reference Files (Must read before implementation)

| File | Reference Purpose |
|------|------------------|
| {file path 1} | {What to check in this file - patterns, style, dependencies, etc.} |
| {file path 2} | {reference purpose} |
| {file path 3} | {reference purpose} |

> When running build skill, read above files first to understand patterns

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

> If this section is empty, 80% of implementation will be unstable - Must complete
```
