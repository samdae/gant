# Backend Check Profile

> Backend architecture verification. Input: `arch-be.md`.

## Component Detection Checklist

| Component | Detection Method | Triggers |
|-----------|------------------|----------|
| Auth | "auth", "OAuth", "JWT", "login" | Token refresh, Session management |
| DB | DB schema tables defined | Soft delete, Indexes, Migrations |
| REST API | API endpoints defined | Pagination, Rate limiting, Versioning |
| External API | External API list exists | Retry policy, Caching, Fallback |
| Async | Celery, Queue, Worker, Job | Error handling, Retry, DLQ |
| Real-time | SSE, WebSocket | Connection management, Heartbeat |
| File storage | Upload, S3, file | Size limits, Cleanup policy |
| Caching | Redis, Cache | TTL policy, Invalidation |
| K8s/Docker | Deployment config exists | Health check, Resource limits |
| LLM/AI | LLM, OpenAI, Claude | Cost control, Token limits |

## Gap Analysis Checklists

### Auth Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Token refresh logic | Is refresh token flow defined? | Ask user |
| Token expiration | Is expiry duration specified? | Ask user |
| Session invalidation | How to logout/revoke? | Ask user |
| Password policy | Is password requirements defined? | Suggest |
| MFA | Is MFA mentioned if needed? | Ask user |

### DB Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Soft vs Hard delete | Is deletion strategy defined? | Ask user |
| Index strategy | Are indexes defined for query patterns? | Suggest based on API |
| Migration strategy | Is migration tool mentioned? | Suggest |
| Backup/Recovery | Is backup strategy defined? | Ask user |
| Connection pooling | Is pool size defined? | Suggest default |

### REST API Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Pagination | Is pagination defined for list APIs? | Ask user |
| Rate limiting | Is rate limit policy defined? | Ask user |
| API versioning | Is /v1/ or versioning mentioned? | Suggest |
| Request validation | Is validation logic defined? | Suggest |
| Response format | Is error response format defined? | Suggest |
| CORS policy | Is CORS configuration defined? | Ask if needed |

### External API Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Retry policy | Is retry count/backoff defined? | Ask user |
| Caching strategy | Is response caching defined? | Ask user |
| Fallback behavior | What if external API fails? | Ask user |
| Timeout settings | Is timeout defined? | Suggest default |
| Circuit breaker | Is circuit breaker pattern used? | Suggest |

### Async Processing Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Error handling | What if task fails? | Ask user |
| Retry policy | Is retry count defined? | Ask user |
| DLQ | Is DLQ/failed task handling defined? | Suggest |
| Idempotency | Can task be safely retried? | Ask user |
| Priority levels | Are task priorities defined? | Ask if needed |

### Real-time Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Connection timeout | Is SSE/WS timeout defined? | Suggest default |
| Reconnection logic | Client reconnection strategy? | Suggest |
| Heartbeat | Is keep-alive mechanism defined? | Suggest |
| Message format | Is message schema defined? | Ask user |
| Scaling strategy | How to scale WebSocket servers? | Ask if needed |

### File Storage Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Size limits | Is max file size defined? | Ask user |
| Allowed types | Are file types restricted? | Ask user |
| Storage location | S3, local, CDN? | Ask user |
| Cleanup policy | When to delete old files? | Ask user |
| Virus scanning | Is malware check needed? | Ask if sensitive |

### Caching Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| TTL policy | Is cache expiration defined? | Ask user |
| Invalidation strategy | When to invalidate cache? | Ask user |
| Cache key pattern | Is key naming defined? | Suggest |
| Cache warming | Is preloading needed? | Ask if needed |

### Infrastructure Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Health check endpoint | Is /health or probe defined? | Suggest |
| Liveness/Readiness | Are K8s probes defined? | Suggest if K8s |
| Graceful shutdown | Is shutdown handling defined? | Suggest |
| Logging strategy | Is log format/level defined? | Ask user |
| Monitoring | Is metrics/alerting defined? | Ask user |
| Resource limits | Are CPU/memory limits defined? | Suggest if K8s |

### LLM/AI Gaps
| Required Detail | Check | If Missing |
|-----------------|-------|------------|
| Cost tracking | Is token/cost logging defined? | Suggest |
| Usage limits | Is per-user limit defined? | Ask user |
| Fallback model | What if primary model fails? | Ask user |
| Prompt versioning | Is prompt management defined? | Suggest |
| Response validation | Is LLM output validated? | Suggest |
| Timeout handling | Is LLM timeout defined? | Suggest default |

## Q&A Template

```json
{
  "title": "Missing Detail: {Topic}",
  "questions": [{
    "id": "{topic_id}",
    "prompt": "{Description of missing item}. How should this be handled?",
    "options": [
      {"id": "option_a", "label": "{Option A} (recommended)"},
      {"id": "option_b", "label": "{Option B}"},
      {"id": "option_c", "label": "{Option C}"},
      {"id": "skip", "label": "Skip for now (decide during implementation)"}
    ]
  }]
}
```

Skip: Mark as `TBD` in document, continue to next gap, list all skipped at end.

## Document Update (Section 12 in arch-be.md)

```markdown
## 12. Additional Design Details (from Review)
### Authentication - Token expiration: {value}, Refresh: {value}/{description}
### API - Pagination: {value} default/{max} max, Rate limit: {value} req/min/user
### Database - Deletion: {soft|hard delete}, Index: {description}
### Infrastructure - Health check: {endpoint}, Graceful shutdown: {timeout}
### TBD (Skipped) - {skipped item list}
```

## Summary Report

```markdown
## Backend Architecture Review Complete
### Components Detected
- [x] Auth ({type}), [x] Database ({type}, {N} tables), [x] REST API ({N} endpoints)
- [x] Async ({type}), [ ] Real-time (not detected), [x] External APIs ({N} services)
(Mark [x] detected, [ ] not detected)
### Gaps Filled: {N}
| Item | Decision |
|------|----------|
| Token refresh | {decision} |
| Pagination | {decision} |
### Skipped (TBD): {M} - {list}
### Document Updated - docs/{serviceName}/arch-be.md Section 12 added
### Next Step - Run `/build`
```
