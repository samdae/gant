# Backend Pre-build Profile

## Check Categories

### 1. External Services Detection

**Parse `tech_stack.third_party` section and check:**

| Pattern | Service Type | Required Credentials |
|---------|--------------|---------------------|
| `oauth`, `google`, `kakao`, `social` | OAuth Provider | CLIENT_ID, CLIENT_SECRET |
| `openai`, `gpt` | OpenAI | OPENAI_API_KEY |
| `anthropic`, `claude` | Anthropic | ANTHROPIC_API_KEY |
| `stripe`, `payment` | Payment | STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET |
| `twilio`, `sms` | SMS | TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN |
| `sendgrid`, `email` | Email | SENDGRID_API_KEY |
| `aws`, `s3` | AWS | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY |
| `firebase` | Firebase | FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY |

### 2. Infrastructure Detection

**Parse `database`, `orm`, `infra` sections:**

| Pattern | Component | Check Method |
|---------|-----------|--------------|
| `postgresql`, `postgres` | PostgreSQL | docker-compose.yml, DATABASE_URL |
| `mysql`, `mariadb` | MySQL | docker-compose.yml, DATABASE_URL |
| `mongodb`, `mongo` | MongoDB | docker-compose.yml, MONGODB_URI |
| `redis` | Redis | docker-compose.yml, REDIS_URL |
| `rabbitmq`, `celery` | Message Queue | docker-compose.yml |
| `elasticsearch` | Search | docker-compose.yml |

### 3. Business Logic Keywords

**Scan Code Mapping for these keywords:**

| Korean | English | Logic Type |
|--------|---------|------------|
| 계산 | calculate, compute | Formula needed |
| 점수 | score, rating | Scoring algorithm |
| 평균 | average, mean | Aggregation formula |
| 가중 | weighted | Weight definition |
| 변환 | convert, transform | Conversion logic |
| 환율 | exchange rate | Rate source |
| 할인 | discount | Discount rules |
| 수수료 | fee, commission | Fee calculation |

### 4. Mock Data Detection

**Search Implementation Plan for:**

- `mock` → Mock data schema needed
- `seed` → Seed data script needed
- `fixture` → Test fixtures needed
- `sample`, `test data` → Sample data files needed
- `90일`, `30일` etc. → Date range for mock data

---

## Generated File Templates

### docker-compose.yml (PostgreSQL + Redis)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-app}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### .env.example Template

```bash
# Database
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@localhost:5432/${DB_NAME}
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=app

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# OAuth (uncomment and fill as needed)
# GOOGLE_CLIENT_ID=
# GOOGLE_CLIENT_SECRET=
# KAKAO_CLIENT_ID=
# KAKAO_CLIENT_SECRET=

# LLM (uncomment and fill as needed)
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-4o

# CORS
CORS_ORIGINS=["http://localhost:3000"]
```

### Mock Data Generation Script Template

```python
#!/usr/bin/env python3
"""
Mock data generation script.
Run: python scripts/generate_mock.py
"""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_DIR = Path("data/mock")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def generate_date_range(days: int = 90):
    """Generate date range from today backwards."""
    today = datetime.now().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(days)]

def main():
    dates = generate_date_range(90)
    
    # TODO: Generate mock data based on schema
    # Example:
    # market_data = [{"date": d, "value": random.uniform(100, 200)} for d in dates]
    # (OUTPUT_DIR / "market.json").write_text(json.dumps(market_data, indent=2))
    
    print(f"Mock data generated in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
```
