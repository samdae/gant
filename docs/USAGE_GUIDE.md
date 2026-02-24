# G-ANT Trader 사용 가이드

G-ANT Trader(TradingAgents)는 12개 AI 에이전트가 협업하여 주식/암호화폐를 분석하고, 가상 매매로 분석 정확도를 검증하며, 반성·학습 메커니즘으로 자기 개선하는 시스템입니다.

## 1. 사전 준비

### 필수 요구사항

| 항목 | 버전 |
|---|---|
| Python | 3.11+ |
| [uv](https://docs.astral.sh/uv/) | 최신 |
| PostgreSQL | 17 (Docker 또는 Supabase) |
| Node.js | 18+ (프론트엔드 빌드 시) |

### LLM 인증

API 키가 필요 없습니다. Google OAuth 기반으로 동작합니다.

| 프로바이더 | 설정 방법 | 모델 |
|---|---|---|
| `gemini-cli` (기본) | 터미널에서 `gemini` 1회 실행 → OAuth 인증 | gemini-2.5-pro / gemini-2.5-flash |
| `antigravity` | 자체 OAuth 플로우 (~/.antigravity_tokens.json) | gemini-3-pro-high / gemini-3-flash |
| `codex` | oauth-codex 패키지 PKCE 인증 | gpt-5.3-codex |

프로바이더 변경은 환경변수 `LLM_PROVIDER`로 설정합니다.

## 2. 환경 설정

### 2.1 저장소 클론 및 의존성 설치

```bash
cd <프로젝트 루트>
uv sync
```

### 2.2 환경변수 설정

`.env.example`을 복사하여 `.env`를 생성합니다.

```bash
cp .env.example .env
```

**필수 환경변수:**

```bash
# WRITE API 인증 토큰 (필수 — 미설정 시 서버 시작 차단)
TRADINGAGENTS_ADMIN_TOKEN=<원하는_토큰>
```

**데이터베이스** — 아래 중 하나를 선택합니다:

```bash
# 방법 1: Supabase
SUPABASE_DB_URL=postgresql://postgres:<password>@<host>:5432/postgres
SUPABASE_DIRECT_URL=postgresql://postgres:<password>@<host>:5432/postgres

# 방법 2: 로컬 Docker Postgres (아래 섹션 참조)
POSTGRES_USER=trading
POSTGRES_PASSWORD=tradingpass
POSTGRES_DB=tradingagents
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

**선택 환경변수:**

```bash
# LLM 프로바이더 (기본: gemini-cli)
LLM_PROVIDER=gemini-cli          # gemini-cli / antigravity / codex

# 스케줄러 활성화 (기본: false)
TRADINGAGENTS_SCHEDULER_ENABLED=true

# CORS 허용 도메인 (기본: * 전체 허용)
TRADINGAGENTS_CORS_ORIGINS=http://localhost:5173

# 로그 레벨 (기본: INFO)
TRADINGAGENTS_LOG_LEVEL=INFO
```

### 2.3 PostgreSQL 준비

**로컬 Docker 실행:**

```bash
docker compose -f infra/docker-compose.local.yml up -d
```

포트 `5432`에서 Postgres 17이 실행됩니다 (timezone: Asia/Seoul).

**스키마 초기화:**

```bash
uv run python scripts/init_db.py
```

서버 시작 시에도 자동으로 스키마를 초기화하지만, 사전에 실행하여 DB 연결을 확인할 수 있습니다.

## 3. 실행 방법

### 3.1 API 서버 실행

```bash
# 방법 1: run_api.sh (uv sync + 환경변수 로드 + 서버 시작)
scripts/run_api.sh

# 방법 2: 직접 실행
uv run uvicorn apps.api.app:app --host 0.0.0.0 --port 8000
```

서버가 시작되면:
- REST API: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws/analyze/{ticker}`
- 헬스체크: `http://localhost:8000/health`

`TRADINGAGENTS_SCHEDULER_ENABLED=true`이면 APScheduler가 함께 시작되어 등록된 티커들을 자동 분석합니다.

### 3.2 프론트엔드 실행 (개발)

```bash
cd apps/web
npm install
npm run dev
```

`http://localhost:5173`에서 Svelte SPA 대시보드에 접근합니다.

### 3.3 프론트엔드 빌드 (배포)

```bash
cd apps/web
npm run build
```

빌드 결과물은 `apps/web/dist/`에 생성됩니다.

## 4. 분석 스케줄 등록

### 웹 UI로 등록

1. 대시보드(`http://localhost:5173`) → 하단 "예약" 탭
2. "+ 추가" 버튼 → 티커 입력 (자동완성 지원) → 생성
3. 관리자 토큰 입력이 필요합니다 (최초 1회, localStorage에 저장)

### API로 등록

```bash
curl -X POST http://localhost:8000/schedules \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "display_name": "엔비디아"}'
```

- 한국 주식: `.KS`(코스피) / `.KQ`(코스닥) 접미사 → 통화 KRW, 자금 ₩5,000,000 자동 설정
- 그 외: 통화 USD, 자금 $5,000 자동 설정

### 스케줄 삭제

```bash
curl -X DELETE http://localhost:8000/schedules/NVDA \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

## 5. 분석 파이프라인

등록된 티커는 장 마감 후 자동으로 분석됩니다.

```
시장별 실행 시각:
  - 미국(나스닥 등) + 암호화폐: ET 17:00 (KST ~07:00)
  - 한국(코스피/코스닥):       KST 16:30
```

**분석 흐름:**

```
1. 중복 실행 방지 — 새 시장 데이터 없으면 스킵
2. 자동 청산 체크 — stop_loss/target 또는 ±30% 초과 시 즉시 청산
3. 12에이전트 파이프라인:
   시장분석 → 소셜분석 → 뉴스분석 → 펀더멘탈분석
   → 강세 ↔ 약세 토론 (N라운드) → 리서치 심판
   → 트레이더 제안
   → 공격적 ↔ 보수적 ↔ 중립적 리스크 토론 → 리스크 심판
   → 신호 추출 (BUY/HOLD/SELL + strategy_json)
4. Portfolio Agent — 포지션·과거 경험 종합하여 최종 매매 결정
5. 요약에이전트 — 13개 요약 컬럼으로 리포트 DB 저장
6. (청산 시) 반성에이전트 — 전 사이클 기반 반성문 작성 → Postgres + ChromaDB 저장
```

## 6. 주요 API 엔드포인트

### 공개 READ (인증 불필요)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스체크 |
| GET | `/metrics` | 대시보드 KPI (손익, 승률 등) |
| GET | `/queue` | 분석 큐 상태 |
| GET | `/positions/market` | 활성 포지션 + 현재가 + PnL |
| GET | `/positions/closed` | 청산 포지션 목록 |
| GET | `/schedules` | 스케줄 목록 |
| GET | `/reports` | 분석 리포트 목록 |
| GET | `/reflections` | 반성문 목록 |
| GET | `/activity` | 최근 활동 피드 |

### 인증 필요 WRITE

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/schedules` | 스케줄 등록 |
| DELETE | `/schedules/{ticker}` | 스케줄 삭제 |
| POST | `/schedules/{ticker}/retry` | 실패 스케줄 재시도 |

### 실시간

| 프로토콜 | 경로 | 설명 |
|---|---|---|
| WebSocket | `/ws/analyze/{ticker}` | 에이전트 진행 상태 실시간 스트리밍 |

전체 23개 REST + 1개 WS 엔드포인트는 `docs/tradingagents/arch-be.md` §6을 참조하십시오.

## 7. 데이터베이스 관리

### 스키마 초기화

```bash
uv run python scripts/init_db.py
```

### DB 리셋 (전체 데이터 삭제 + 스키마 재생성)

```bash
# Postgres + ChromaDB 전체 리셋
uv run python scripts/reset_db.py --confirm

# Postgres만 리셋 (ChromaDB 벡터 유지)
uv run python scripts/reset_db.py --confirm --keep-chroma
```

> `--confirm` 플래그 없이는 실행되지 않습니다 (안전장치).

### DB 구조 (7 테이블)

```
schedule_configs    — 티커별 설정 (통화, 자금, 시장, 주기)
schedule_jobs       — 사이클별 실행 기록
schedule_job_events — 에이전트별 진행 이벤트
positions           — 포지션 (active/closed)
reports             — 분석 리포트 (13개 요약 컬럼)
trades              — 개별 BUY/SELL 기록
reflections         — 청산 시 반성문 (Postgres FTS + ChromaDB 벡터)
```

## 8. 프로젝트 구조

```
├── apps/
│   ├── api/app.py              # FastAPI 진입점
│   └── web/                    # Svelte SPA 프론트엔드
├── packages/tradingagents/
│   ├── api/                    # REST 23개 + WS + 인증
│   ├── graph/                  # LangGraph 에이전트 파이프라인
│   ├── agents/                 # 12에이전트 + 요약에이전트
│   ├── virtual_trade/          # TradeManager + PortfolioAgent
│   ├── scheduler/              # APScheduler + CronTrigger
│   ├── storage/                # Postgres 7 Repository
│   ├── memory/                 # HybridMemory (FTS + ChromaDB)
│   ├── llm_clients/            # gemini-cli, antigravity, codex
│   ├── dataflows/              # yfinance, Alpha Vantage
│   ├── default_config.py       # 기본 설정
│   ├── errors.py               # 커스텀 예외
│   └── runtime_context.py      # contextvars 스케줄 컨텍스트
├── scripts/
│   ├── init_db.py              # DB 스키마 초기화
│   ├── reset_db.py             # DB 리셋
│   └── run_api.sh              # API 서버 실행 스크립트
├── infra/
│   ├── docker-compose.local.yml  # 로컬 Postgres
│   └── docker-compose.dev.yml    # 개발용 Postgres (포트 5433)
├── docs/                       # 설계 문서
├── pyproject.toml              # Python 의존성 (uv)
└── .env.example                # 환경변수 템플릿
```

## 9. 트러블슈팅

### 서버가 시작되지 않음

```
RuntimeError: TRADINGAGENTS_ADMIN_TOKEN is required
```
→ `.env`에 `TRADINGAGENTS_ADMIN_TOKEN` 설정 필요

### DB 연결 실패

```
Database URL is not configured
```
→ `.env`에 `SUPABASE_DB_URL` 또는 `POSTGRES_*` 환경변수 설정 필요. Docker Postgres가 실행 중인지 확인

### LLM 인증 실패

- `gemini-cli`: 터미널에서 `gemini` 명령어 1회 실행하여 OAuth 인증
- `antigravity`: `~/.antigravity_tokens.json` 토큰 파일 확인
- `codex`: `oauth-codex` 패키지의 PKCE 인증 플로우 완료 필요

### 분석이 실행되지 않음 (스케줄러)

- `TRADINGAGENTS_SCHEDULER_ENABLED=true` 설정 확인
- 장 마감 후 시간대인지 확인 (미국 ET 17:00, 한국 KST 16:30)
- `GET /health`로 `scheduler_running` 상태 확인
- 새 시장 데이터가 없으면 자동 스킵됨 (주말/공휴일)

---

상세 설계 문서: `docs/tradingagents/spec.md` (요구사항) · `docs/tradingagents/arch-be.md` (백엔드) · `docs/tradingagents/arch-fe.md` (프론트엔드) · `docs/tradingagents/ui.md` (UI 명세)
