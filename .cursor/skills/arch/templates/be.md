# Backend Architecture Document Template

Output: `docs/{serviceName}/arch-be.md`

## Template

```markdown
# Backend Design Doc: {Feature Name}

> Created: {date} | Service: {serviceName} | Type: Backend
> Requirements: docs/{serviceName}/spec.md

## 0. Summary
### Goal
(1-2 sentences)
### Non-goals
### Success metrics

## 1. Scope
### In scope
### Out of scope

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

## 1.6. Dependencies
```yaml
package_manager: "{pip|uv|poetry}"          # Phase 0-1.7
project_type: "{new|existing}"
dependencies:
  - name: "{package}"
    version: "{version or latest}"
    purpose: "{what it's used for}"
    status: "{approved|rejected|alternative}"
```
> `status: approved` = installed in build phase.

## 2. Architecture Impact
### Components
| Service / Module | Responsibility | Change type |
|-----------------|----------------|-------------|
| {service name} | {role} | new / modify |

### Database Schema
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
          action: "ADD"                     # ADD | DROP | MODIFY
          description: "{description}"
  indexes:
    - table: "{table_name}"
      columns: ["{col1}", "{col2}"]
      type: "BTREE"                         # BTREE | HASH | GIN
      unique: false
```

### Migration Summary
```yaml
migrations:
  - type: "CREATE_TABLE"
    table: "{table}"
    description: "{desc}"
  - type: "ALTER_TABLE"
    table: "{table}"
    description: "{change}"
  - type: "CREATE_INDEX"
    table: "{table}"
    description: "{index desc}"
```

## 3. Code Mapping
| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 1 | FR-001 | {feature} | {full path} | {class} | {method} | {action} | [ ] |

> **Spec Ref**: Req ID (1:N). **Impl**: `[ ]` = pending, `[x]` = done by build.

## 4. Implementation Plan
### Required Reference Files
| File | Purpose |
|------|---------|
| {path 1} | {patterns, style, dependencies} |

> Read above files first when running build skill.

### Steps
1. **Step 1: {name}** - {tasks}
2. **Step 2: {name}** - {tasks}
3. **Step 3: {name}** - {tasks}

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

## 6. API Specification
```yaml
api_endpoints:
  - name: "{API name}"
    method: "{GET|POST|PUT|DELETE}"
    path: "/api/v1/{path}"
    description: "{description}"
    auth_required: true
    request:
      headers:
        - name: "Authorization"
          type: "string"
          required: true
      params:
        - name: "{param}"
          type: "{type}"
          required: true
      body:
        content_type: "application/json"
        schema:
          field1: "{type}"
          field2: "{type}"
    response:
      success:
        status: 200
        schema: { success: "boolean", data: "{type or object}" }
      errors:
        - status: 400
          code: "INVALID_INPUT"
          message: "{error message}"
        - status: 404
          code: "NOT_FOUND"
          message: "{error message}"
```

## 7. Infra/Ops
### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| {VAR_NAME} | {description} | {value} |

### Deployment Changes
- (If needed)

## 8. Risks & Tradeoffs (Debate Conclusion)
### Chosen Option
### Rejected Alternatives
### Reasoning
- Project constraints | Best practice adoption | Future improvements
### Assumptions
- **Confirmed**: {decided} | **Estimated**: {assumed, needs verification}

## 9. Error/Auth/Data Checklist (3 Essential Checks)

### Error Handling
| Situation | Location | Handling Method | Response |
|-----------|----------|----------------|----------|
| {exception scenario} | {file/method} | {try-catch/propagation} | {HTTP code, message} |
| Invalid input | Validation layer | Schema validation | 422 Unprocessable Entity |
| External timeout | Service layer | Retry + circuit breaker | 503 Service Unavailable |

### Authorization
| Action | Required Permission | Validation Location | On Failure |
|--------|-------------------|-------------------|-----------|
| {API/feature} | {role/permission} | {middleware/service} | {403/401} |
| Create resource | ROLE_ADMIN | AuthMiddleware | 403 Forbidden |

### Data Integrity
| Validation Item | Timing | On Failure |
|----------------|--------|-----------|
| FK existence | before save | 400 + message |
| Duplicate check | on create | 409 Conflict |
| Range validation | on input | 422 + details |

> **WARNING**: If empty, 80% of implementation will be unstable - Must complete
```
