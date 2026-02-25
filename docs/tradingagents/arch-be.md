# Backend Design Doc: TradingAgents Features (FR-013~054)

> Created: 2026-02-11
> Updated: 2026-02-25
> Service: tradingagents
> Type: Backend
> Requirements document: docs/tradingagents/spec.md
> Repo layout: monorepo (`packages/tradingagents`)

## 0. Summary

### Goal

기존 TradingAgents 멀티에이전트 분석 파이프라인에 **영속 메모리(Hybrid RAG)**, **가상 매매 검증**, **스케줄 기반 자동화**를 추가하고, **Postgres 기반 데이터 저장**, **반성 집중화(반성에이전트 1곳)**, **요약에이전트**를 도입하여, AI 분석의 정확도를 정량적으로 추적·학습하는 자기 개선 시스템으로 진화시킨다. 추가로 **스케줄 테이블 재설계(7테이블)**, **통화 지원(KRW/USD)**, **자동 청산 메커니즘**, **시장별 스케줄링**, **Codex LLM 프로바이더**를 도입한다. v5에서 **RAG 검색 파이프라인 개편(맥락 인식 검색, usefulness 기반 필터링)**, **RAG Validator(경험 유용성 자동 평가)**, **매매검증 검색 기능**을 추가한다.

### Non-goals

- 실제 증권사 API 연동 (가상 매매만)
- 멀티유저/멀티전략 지원 (단일 사용자)
- 실시간 데이터 스트리밍 (분석 시점 1회성 fetch 유지)

### Success metrics

- 메모리 영속성: 프로세스 재시작 후 Postgres + ChromaDB 100% 복원
- 가상 매매: positions/trades 테이블에 완전한 매매 이력 기록
- 학습 효과: has_memory=true vs false 분석 결과 비교 가능
- 스케줄: 지정 주기대로 자동 분석 실행, 1시간 이내 완료
- 반성 품질: 청산 포지션마다 전 사이클 기반 반성문 생성
- RAG 품질: usefulness_score < 40 문서 자동 배제, 쓰레기 경험 점진적 필터링
- RAG 맥락: 동일 market/sector 경험 우선 검색, 크로스 티커 노이즈 감소

---

## 1. Scope

### In scope

- FR-015: Hybrid RAG Memory (Postgres FTS + Vector, chromadb 내장 ONNX 임베딩)
- FR-018: 구조화된 reflect_and_remember 입력
- FR-019: Bootstrap 태깅 (has_memory 플래그)
- FR-013: 가상 매매 추적
- FR-014: Portfolio Agent (독립 에이전트, LangGraph 외부)
- FR-016: APScheduler 기반 티커별 스케줄링
- FR-017: AgentState current_position 제거됨 (FR-021로 축소)
- FR-020: 전략 기반 매매 실행 — 부분 매도, PA 매도 수량 전략 결정
- FR-021: 분석플로우 객관성 확보 — 12에이전트에서 포지션 주입 제거
- FR-022: PA 프롬프트 강화 — 가중치 기반 판단, 디바이어싱, HybridMemory 연결
- ~~FR-023: 저장 경로 통합 + 아카이빙~~ → Superseded by FR-030
- ~~FR-024: 저장 경로 개편~~ → Superseded by FR-030
- FR-025: FastAPI 웹 백엔드 — REST API + WebSocket
- FR-026: READ 공개 + WRITE 인증 (Bearer token)
- FR-034: UI 지표용 현재가/PnL API — yfinance on-demand 조회
- ~~FR-027: 파일명 변경~~ → Superseded by FR-030
- ~~FR-028: 저장 경로 명칭 변경~~ → Superseded by FR-030
- FR-029: 기억 오염 방지 + 메타데이터 강화 — outcome/market/sector/industry 태깅
- **FR-030: Postgres 전환 — 파일 기반 저장 전면 폐기, 7테이블 + GIN FTS**
- **FR-031: 반성 집중화 — 반성에이전트 1곳, 청산 시에만**
- **FR-032: 요약에이전트 — 개별 요약 컬럼**
- **FR-033: BM25 엔진 교체 — rank_bm25 → Postgres FTS (GIN)**
- **FR-035: Svelte SPA 프론트엔드**
- **FR-036: 시장 데이터 중복 실행 방지**
- **FR-037: 에이전트 이벤트 영속화**
- **FR-038: DB 리셋/마이그레이션 스크립트**
- **FR-039: 스케줄 테이블 재설계 — schedules 제거, 7테이블**
- **FR-040: 통화(Currency) 전면 지원**
- **FR-041: 포지션별 독립 자금**
- **FR-042: 자동 청산 메커니즘 — stop_loss/target + ±30% 폴백**
- **FR-043: 매매 시점/가격 보정 — yfinance 데이터 기준일**
- **FR-044: 스케줄러 시장별 실행 시간 — CronTrigger**
- **FR-045: 총손익 = 실현 + 미실현**
- **FR-047: Win/Loss 판정 기준 통일**
- **FR-050: Codex(GPT-5.3) LLM Provider**
- **FR-051: RAG 맥락 인식 검색 — 쿼리 enrichment (market/sector 텍스트 부착)**
- **FR-052: RAG 검색 파이프라인 재설계 — RRF → usefulness 순서, usefulness_score, RAG_TOP_K**
- **FR-053: RAG Validator — 회고분석 기반 문서별 usefulness_score ±1 자동 조정**
- **FR-054: 매매검증 검색 — 키워드 + 시멘틱 이중 검색**

### Out of scope

- Pydantic 기반 설정 마이그레이션 (기존 dict 유지)
- 멀티스레드 병렬 분석 (순차 실행 유지)
- Event Sourcing / CQRS 패턴 (단일 트랜잭션 모델)

---

## 1.5. Tech Stack

```yaml
tech_stack:
  project_structure: "Monorepo"
  be_path: "packages/tradingagents"
  fe_path: "apps/web"
  run_command_be: "uv run uvicorn apps.api.app:app --host 0.0.0.0 --port 8000"
  run_command_fe: "cd apps/web && npm run dev"
  language: "Python 3.10+"
  framework: "LangGraph (langgraph>=0.4.8)"
  database: "PostgreSQL 17 (Supabase 호환)"
  orm: "None (Raw SQL via psycopg)"
  package_manager: "uv"
  third_party:
    - "chromadb (Vector Store + Built-in ONNX Embedding)"
    - "apscheduler (Job Scheduling)"
    - "yfinance (Market Data)"
    - "langchain-core (LLM Abstraction)"
    - "fastapi (Web API Framework)"
    - "uvicorn (ASGI Server)"
    - "psycopg[binary] (PostgreSQL Driver)"
  infra: "Docker Compose (postgres:17) / Supabase / Local"
```

> `rank-bm25` 제거됨 — Postgres FTS 내장으로 교체 (FR-033)
> `sqlite3` 제거됨 — Postgres (psycopg) 전환 (FR-030)

---

## 1.6. Dependencies

```yaml
package_manager: "uv"
project_type: "existing"

dependencies:
  # Existing
  - name: "langchain-core"
    version: ">=0.3.81"
    purpose: "LLM abstraction layer"
    status: "approved"
  - name: "langgraph"
    version: ">=0.4.8"
    purpose: "Graph-based agent orchestration"
    status: "approved"
  - name: "yfinance"
    version: ">=0.2.63"
    purpose: "시장 데이터 fetch"
    status: "approved"

  # NEW — FR-015: Hybrid RAG (Vector 경로)
  - name: "chromadb"
    version: ">=1.5.0"
    purpose: "Vector store + 내장 임베딩 (all-MiniLM-L6-v2, ONNX Runtime)"
    status: "approved"

  # NEW — FR-016: Scheduling
  - name: "apscheduler"
    version: ">=3.11.2"
    purpose: "티커별 주기적 분석 스케줄링"
    status: "approved"

  # NEW — FR-025: Web API
  - name: "fastapi"
    version: ">=0.115.0"
    purpose: "REST API + WebSocket 웹 백엔드"
    status: "approved"
  - name: "uvicorn"
    version: ">=0.34.0"
    purpose: "ASGI 서버"
    status: "approved"

  # NEW — FR-030: Postgres
  - name: "psycopg[binary]"
    version: ">=3.3.2"
    purpose: "PostgreSQL 드라이버 (dict_row, per-thread connection)"
    status: "approved"

  # NEW — Logging
  - name: "python-json-logger"
    version: ">=3.3.0"
    purpose: "JSON 구조화 로깅 포매터"
    status: "approved"

  # NEW — FR-050: Codex LLM Provider
  - name: "oauth-codex"
    version: "latest"
    purpose: "OpenAI Codex OAuth PKCE 인증 + LLM 호출"
    status: "approved"

  # REMOVED
  # - rank-bm25: Postgres FTS로 교체 (FR-033)
  # - sqlite3: Postgres로 교체 (FR-030)
```

---

## 2. Architecture Impact

### Components

| Service / Module | Responsibility | Change type |
|---|---|---|
| `tradingagents/storage/` | Postgres DB 연결, Repository 패턴 CRUD (7 repos) | **new** (FR-030, FR-039) |
| `tradingagents/agents/summary_agent.py` | 12에이전트 raw → 개별 요약 컬럼 생성 | **new** (FR-032) |
| `tradingagents/memory/` | Hybrid RAG (Postgres FTS + ChromaDB), RRF | modify (FR-033) |
| `tradingagents/graph/reflection.py` | 반성 집중화: 5개 → 1개 메서드 | modify (FR-031) |
| `tradingagents/graph/trading_graph.py` | DB 연동, 구조화 반성, 트랜잭션 | modify |
| `tradingagents/graph/signal_processing.py` | strategy_json 파싱 + LLM fallback | modify |
| `tradingagents/virtual_trade/trade_manager.py` | DB 기반 매매 관리 (파일 I/O 제거) | modify (FR-030) |
| `tradingagents/virtual_trade/portfolio_agent.py` | PA 프롬프트 강화, HybridMemory 연결 | modify (FR-022) |
| `tradingagents/scheduler/ticker_scheduler.py` | DB 기반 스케줄 + 사이클 관리, 중복 실행 방지 | modify (FR-030, FR-036) |
| `tradingagents/graph/propagation.py` | current_position 제거 | modify |
| `tradingagents/agents/utils/agent_states.py` | current_position 필드 제거 | modify |
| `tradingagents/api/` | FastAPI 웹 백엔드 — REST + WS + auth + UI metrics | **new** (FR-025, FR-034) |
| `tradingagents/runtime_context.py` | contextvars 기반 스케줄 컨텍스트 전파 | **new** |
| `tradingagents/errors.py` | 커스텀 예외 계층 (DataVendorError, DecisionParseError, AgentExecutionError) | **new** |
| `tradingagents/default_config.py` | DB URL, 스케줄러 설정, 캐시 설정 추가 | modify |
| `apps/api/app.py` | FastAPI 진입점 (프록시) | **new** |
| `tradingagents/rag_validator/` | RAG Validator — 회고분석 기반 문서별 usefulness_score ±1 평가 + 효과 리포트 생성 | **new** (FR-053) |
| `tradingagents/memory/hybrid_memory.py` | 쿼리 enrichment + 파이프라인 재설계 (RRF → usefulness 순서, top-K) | modify (FR-051, FR-052) |
| `tradingagents/virtual_trade/portfolio_agent.py` | `_build_rag_query()` enrichment 반영, `RAG_TOP_K` 적용 | modify (FR-051, FR-052) |
| `tradingagents/storage/reflection_repo.py` | `usefulness_score` 컬럼 CRUD, `search_keyword()` 추가 | modify (FR-052, FR-054) |
| `apps/web/` | Svelte SPA 프론트엔드 | **new** (FR-035) |
| `pyproject.toml` | chromadb, apscheduler, fastapi, uvicorn, psycopg | modify |
| ~~`tradingagents/virtual_trade/report_store.py`~~ | ~~JSON array append~~ | **삭제** (FR-032로 대체) |
| `tradingagents/llm_clients/codex_client.py` | ChatCodex(BaseChatModel) LangChain 래퍼 — OAuth PKCE | **new** (FR-050) |
| `tradingagents/llm_clients/factory.py` | LLM 팩토리에 `"codex"` 프로바이더 추가 | modify (FR-050) |
| `scripts/reset_db.py` | PostgreSQL FK 역순 DROP + ChromaDB 컬렉션 삭제 + init_schema() | **new** (FR-038) |
| ~~`tradingagents/storage/schedule_repo.py`~~ | ~~ScheduleRepository~~ | **삭제** (FR-039, schedule_config_repo+schedule_job_repo로 이관) |

### Data

#### Postgres Schema — FR-030, FR-039~044

> 전체 DDL은 `tradingagents/storage/database.py` 참조
> **FR-039**: `schedules` 테이블 제거, 8→7테이블. `schedule_configs` 확장, `schedule_jobs` FK 통합

```sql
-- ① schedule_configs: 티커별 설정 (기존 + 확장)
CREATE TABLE schedule_configs (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT    NOT NULL UNIQUE,
    interval_days   INTEGER NOT NULL DEFAULT 1,
    current_cycle   INTEGER NOT NULL DEFAULT 0,        -- [NEW] 원자적 사이클 관리
    currency        TEXT    NOT NULL DEFAULT 'USD',     -- [NEW] KRW | USD
    initial_capital DOUBLE PRECISION NOT NULL DEFAULT 5000, -- [NEW] KRW=5000000, USD=5000
    market          TEXT    NOT NULL DEFAULT 'us',      -- [NEW] us | kr | crypto
    display_name    TEXT,
    last_data_date  DATE,
    created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_configs_ticker ON schedule_configs(ticker);

-- [REMOVED] schedules 테이블 — schedule_jobs가 흡수

-- ② schedule_jobs: 사이클별 실행 기록 (schedules + schedule_jobs 통합)
CREATE TABLE schedule_jobs (
    id                 BIGSERIAL PRIMARY KEY,
    schedule_config_id BIGINT  NOT NULL REFERENCES schedule_configs(id), -- [CHANGED]
    scheduled_cycle    INTEGER NOT NULL,               -- [NEW] schedules에서 흡수
    status             TEXT    NOT NULL,
    error_type         TEXT,
    error_message      TEXT,
    error_detail       TEXT,
    created_at         TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_jobs_config ON schedule_jobs(schedule_config_id);

-- ③ positions: 포지션 (기존 + 통화/청산 전략)
CREATE TABLE positions (
    id          BIGSERIAL PRIMARY KEY,
    ticker      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',
    shares      DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost    DOUBLE PRECISION,
    currency    TEXT    NOT NULL DEFAULT 'USD',         -- [NEW] FR-040
    stop_loss   DOUBLE PRECISION,                      -- [NEW] FR-042
    target      DOUBLE PRECISION,                      -- [NEW] FR-042
    return_pct  DOUBLE PRECISION,
    opened_at   TIMESTAMPTZ NOT NULL,
    closed_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_positions_ticker_status ON positions(ticker, status);

-- ④ reports: 분석 리포트 (FK 변경)
CREATE TABLE reports (
    id                                BIGSERIAL PRIMARY KEY,
    schedule_job_id                   BIGINT NOT NULL REFERENCES schedule_jobs(id), -- [CHANGED]
    position_id                       BIGINT REFERENCES positions(id),
    market_report                     TEXT,
    fundamentals_report               TEXT,
    bull_history                      TEXT,
    bear_history                      TEXT,
    investment_debate_judge_decision  TEXT,
    aggressive_history                TEXT,
    conservative_history              TEXT,
    neutral_history                   TEXT,
    trader_investment_judge_decision  TEXT,
    trader_investment_decision        TEXT,
    investment_plan                   TEXT,
    final_trade_decision              TEXT,
    decision_position                 TEXT,
    portfolio_action                  TEXT,
    portfolio_shares                  DOUBLE PRECISION,
    portfolio_rationale               TEXT,
    pa_opinion                        TEXT,
    pipeline_strategy                 TEXT,
    created_at                        TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_reports_job ON reports(schedule_job_id);
CREATE INDEX idx_reports_position ON reports(position_id);

-- ⑤ trades: 매매 기록 (기존 + 통화)
CREATE TABLE trades (
    id          BIGSERIAL PRIMARY KEY,
    position_id BIGINT NOT NULL REFERENCES positions(id),
    report_id   BIGINT NOT NULL REFERENCES reports(id),
    action      TEXT    NOT NULL,
    shares      DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    currency    TEXT    NOT NULL DEFAULT 'USD',         -- [NEW] FR-040
    executed_at TIMESTAMPTZ NOT NULL                   -- [CHANGED] → yfinance 데이터 기준일
);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_report ON trades(report_id);

-- ⑥ reflections: 회고 (FR-052 usefulness_score 추가)
CREATE TABLE reflections (
    id               BIGSERIAL PRIMARY KEY,
    position_id      BIGINT NOT NULL REFERENCES positions(id),
    reflection       TEXT    NOT NULL,
    key_lessons      TEXT,
    outcome          TEXT,
    return_pct       DOUBLE PRECISION,
    market           TEXT,
    sector           TEXT,
    industry         TEXT,
    usefulness_score DOUBLE PRECISION NOT NULL DEFAULT 50, -- [NEW] FR-052/053: RAG Validator ±1 조정, < 40 시 배제
    created_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_reflections_position ON reflections(position_id);

-- ⑦ schedule_job_events: 에이전트 활동 로그 (FK 정리)
CREATE TABLE schedule_job_events (
    id              BIGSERIAL PRIMARY KEY,
    schedule_job_id BIGINT REFERENCES schedule_jobs(id),
    ticker          TEXT,
    agent           TEXT,
    status          TEXT,
    message         TEXT,
    step            INTEGER,
    phase           TEXT,
    created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_job_events_job ON schedule_job_events(schedule_job_id);
CREATE INDEX idx_schedule_job_events_ticker ON schedule_job_events(ticker);
CREATE INDEX idx_schedule_job_events_created_at ON schedule_job_events(created_at);
CREATE UNIQUE INDEX idx_schedule_job_events_unique ON schedule_job_events(schedule_job_id, agent);

-- ⑧ FTS: Postgres GIN 인덱스 (BM25 검색용) — FR-033
CREATE INDEX idx_reflections_search
    ON reflections
    USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
```

> 제외 컬럼: `sentiment_report` (시의성), `news_report` (bull/bear 논거에 반영)
> 각 요약 컬럼 목표: 200~400 토큰

#### 테이블 관계 (FR-039 이후)

```
schedule_configs ─── 1:N ─── schedule_jobs ─── 1:N ─── schedule_job_events
                             schedule_jobs ─── 1:1 ─── reports
                                                       reports ──N:1── positions ─── 1:N ─── trades
                                                                        positions ─── 1:0..1 ── reflections
                                                       reports ──1:N── trades (report_id FK)
```

#### 폐기 대상 (FR-030, FR-039)

| 기존 | 대체 |
|------|------|
| `eval_results/` 로그 저장 | Postgres `reports` 테이블 |
| `memory/experience/{agent}.jsonl` (5개) | Postgres `reflections` + GIN FTS |
| `memory/experience/chroma/{agent}/` (5개) | ChromaDB 단일 컬렉션 |
| `memory/trade/{TICKER}/trade.json` | Postgres `positions` + `trades` |
| `memory/trade/{TICKER}/report.json` | Postgres `reports` |
| `memory/archive/{TICKER}/{n}/` | `positions.status = 'closed'` |
| `rank_bm25` 라이브러리 | Postgres GIN FTS |
| `schedules` 테이블 | `schedule_jobs`가 흡수 (FR-039) |
| `schedule_repo.py` | `schedule_config_repo.py` + `schedule_job_repo.py`로 이관 (FR-039) |

#### Directory Structure (Runtime)

```
Postgres DB (Supabase / Docker)  ← 7 테이블 (FR-039: schedules 제거)
apps/web/dist/                   ← Svelte SPA 빌드 결과
packages/tradingagents/
  └── memory/chroma/             ← ChromaDB vector index
scripts/
  └── reset_db.py                ← DB 리셋 스크립트 (FR-038)
```

---

## 3. Code Mapping

### Phase 1: 구현 완료 (FR-013~020)

| # | Spec Ref | Feature | File | Class | Method | Impl | Note |
|---|----------|---------|------|-------|--------|------|------|
| 1 | FR-015 | HybridMemory 모듈 | `memory/__init__.py` | — | — | [x] | |
| 2 | FR-015 | HybridMemory 클래스 | `memory/hybrid_memory.py` | `HybridMemory` | `__init__`, `add_situations`, `get_memories`, `_rrf_fusion` | [x] | **FR-033에서 Postgres FTS로 리팩터링 완료** |
| 3 | FR-015 | backward compat 재수출 | `agents/__init__.py` | — | — | [x] | |
| 4 | FR-015 | 메모리 교체 | `graph/trading_graph.py` | `TradingAgentsGraph` | `__init__` | [x] | |
| 5 | FR-015 | chromadb 의존성 | `pyproject.toml` | — | — | [x] | |
| 6 | FR-018 | 구조화된 반성 입력 | `graph/trading_graph.py` | `TradingAgentsGraph` | `reflect_and_remember` | [x] | **FR-031에서 단일 반성으로 변경 완료** |
| 7 | FR-018 | Reflector 프롬프트 | `graph/reflection.py` | `Reflector` | `reflect_on_position` | [x] | **FR-031에서 교체 완료** |
| 8 | FR-018 | 메타데이터 저장 | `memory/hybrid_memory.py` | `HybridMemory` | `add_situations` | [x] | **FR-033에서 DB 저장으로 변경 완료** |
| 9 | FR-019 | Bootstrap 태깅 | `graph/trading_graph.py` | `TradingAgentsGraph` | `propagate` | [x] | |
| 10 | FR-019 | 메모리 쿼리 추적 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | [x] | |
| 11 | FR-013 | TradeManager 모듈 | `virtual_trade/__init__.py` | — | — | [x] | |
| 12 | FR-013 | TradeManager 클래스 | `virtual_trade/trade_manager.py` | `TradeManager` | CRUD 메서드 | [x] | **FR-030에서 DB 기반으로 리팩터링 완료** |
| 13 | FR-014 | PortfolioAgent | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_build_prompt` | [x] | **FR-022에서 프롬프트 강화 완료** |
| 14 | FR-016 | Scheduler 모듈 | `scheduler/__init__.py` | — | — | [x] | |
| 15 | FR-016 | TickerScheduler | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `add_ticker`, `start`, `_run_analysis_cycle` | [x] | **FR-030에서 DB 연동 완료** |
| 16 | FR-016 | apscheduler 의존성 | `pyproject.toml` | — | — | [x] | |
| 17 | FR-017 | AgentState 필드 | `agents/utils/agent_states.py` | `AgentState` | — | [x] | |
| 18 | FR-017 | Propagator 파라미터 | `graph/propagation.py` | `Propagator` | `create_initial_state` | [x] | |
| 19 | FR-017 | TradingAgentsGraph position 전달 | `graph/trading_graph.py` | `TradingAgentsGraph` | `propagate` | [x] | |
| 20 | FR-020 | TradeManager 부분 매도 | `virtual_trade/trade_manager.py` | `TradeManager` | `close_positions` | [x] | **FR-030에서 DB 기반으로 변경 완료** |
| 21 | FR-020 | PA 매도 수량 전략 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_parse_decision` | [x] | |
| 22 | FR-020 | Scheduler 부분 매도 분기 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | [x] | |
| 23 | ALL | DEFAULT_CONFIG 확장 | `default_config.py` | — | — | [x] | **FR-030에서 DB URL 변경 완료** |

### Phase 2: 구현 완료 (FR-021~037)

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 24 | FR-030 | Storage 모듈 init | `storage/__init__.py` | — | — | 새 모듈 생성 | [x] |
| 25 | FR-030 | Database 연결 관리 | `storage/database.py` | `Database` | `__init__`, `init_schema`, `get_connection`, `execute_in_transaction`, `close` | Postgres 연결 + per-thread pool + schema 초기화 | [x] |
| 26 | ~~FR-030~~ | ~~ScheduleRepository~~ | ~~`storage/schedule_repo.py`~~ | — | — | **삭제 (FR-039)**: schedule_config_repo + schedule_job_repo로 이관 | [x] |
| 27 | FR-030 | ScheduleConfigRepository | `storage/schedule_config_repo.py` | `ScheduleConfigRepository` | `create`, `upsert`, `get_all`, `get_by_ticker`, `delete`, `update_last_data_date`, `get_all_display_names`, `update_display_name`, `increment_cycle`, `get_current_cycle` | schedule_configs CRUD + UPSERT + cycle 관리 (FR-039) | [x] |
| 28 | FR-030 | PositionRepository | `storage/position_repo.py` | `PositionRepository` | `create`, `get_active`, `update_shares`, `close_position`, `get_by_id` | positions CRUD + status 전환 | [x] |
| 29 | FR-030 | ReportRepository | `storage/report_repo.py` | `ReportRepository` | `create`, `get_by_position`, `get_by_job` | reports INSERT (pipeline_strategy JSON 직렬화 포함) | [x] |
| 30 | FR-030 | TradeRepository | `storage/trade_repo.py` | `TradeRepository` | `create`, `get_by_position`, `get_history`, `get_cash_balance` | trades CRUD + 가용 현금 계산 | [x] |
| 31 | FR-030 | ReflectionRepository | `storage/reflection_repo.py` | `ReflectionRepository` | `create`, `get_by_id`, `get_by_position`, `search_fts` | reflections + Postgres FTS 검색 (`ts_rank_cd`) | [x] |
| 32 | FR-030 | ScheduleJobRepository | `storage/schedule_job_repo.py` | `ScheduleJobRepository` | `create`, `update_status`, `get_latest_by_config`, `get_latest_by_ticker`, `list_by_config`, `update_latest_by_config`, `has_done_today_for_ticker` | schedule_jobs 상태 관리 + 재시도 (FR-039: schedule_config_id 기반) | [x] |
| 33 | FR-037 | ScheduleEventRepository | `storage/schedule_event_repo.py` | `ScheduleEventRepository` | `create`, `list_by_ticker`, `list_latest_by_ticker`, `list_by_job_id` | schedule_job_events UPSERT (agent 기준 유니크) | [x] |
| 34 | FR-031 | 반성 집중화 | `graph/reflection.py` | `Reflector` | `reflect_on_position` | 레거시 7개 메서드 완전 삭제 (`reflect_bull_researcher` 등). 1개 메서드만 존재. DB에서 reports+trades 조회 → 반성문 작성 | [x] |
| 35 | FR-031 | reflect_and_remember 변경 | `graph/trading_graph.py` | `TradingAgentsGraph` | `reflect_and_remember` | 5개 에이전트별 반성 → Reflector.reflect_on_position(position_id) 1회 호출 | [x] |
| 36 | FR-032 | 요약에이전트 | `agents/summary_agent.py` | `SummaryAgent` | `__init__`, `summarize`, `_summarize_component` | 12에이전트 raw + PA 의견 → 13개 요약 생성. quick_think_llm 사용 | [x] |
| 37 | FR-033 | Postgres FTS 교체 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories`, `add_situations`, `_fts_retrieve` | rank_bm25 제거, Postgres FTS 쿼리로 교체. JSONL 제거 | [x] |
| 38 | FR-021 | 12에이전트 포지션 주입 제거 | `agents/utils/agent_states.py`, `graph/propagation.py`, `graph/trading_graph.py` | `AgentState`, `Propagator`, `TradingAgentsGraph` | `create_initial_state`, `propagate` | current_position state 필드 제거, 12에이전트 객관적 분석 보장 | [x] |
| 39 | FR-022 | PA 프롬프트 강화 + 메모리 연결 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_build_prompt`, `_build_rag_query`, `_shares_from_allocation` | 분석(6):경험(4) 가중치, 디바이어싱, HybridMemory 검색, allocation_pct 기반 수량 계산 | [x] |
| 40 | FR-029 | 메타데이터 태깅 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | outcome/market/sector/industry 자동 추가. yf.Ticker.info fetch | [x] |
| 41 | FR-029 | RAG 결과 레이블 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | 결과에 `[✅ 성공 사례]`/`[⚠️ 실패 사례]` 레이블 부착 | [x] |
| 42 | FR-025 | FastAPI 앱 | `api/app.py` | — | `create_app`, `lifespan`, `broadcast_status`, `_queue_worker` | FastAPI 앱, CORS, lifespan에서 APScheduler+큐워커 시작 | [x] |
| 43 | FR-025 | API 라우트 | `api/routes.py` | — | REST 엔드포인트 (23개) | 전체 CRUD + 페이지네이션 + 현재가 조회 | [x] |
| 44 | FR-025 | WebSocket | `api/ws.py` | — | `analyze_ws` | WS /ws/analyze/{ticker}: 에이전트 상태 실시간 스트리밍 | [x] |
| 45 | FR-026 | 인증 미들웨어 | `api/auth.py` | — | `check_admin_token` | Bearer {ADMIN_TOKEN} 검증 | [x] |
| 46 | FR-030 | TradeManager DB 리팩터링 | `virtual_trade/trade_manager.py` | `TradeManager` | 전체 | JSON I/O → PositionRepository + TradeRepository 사용 | [x] |
| 47 | FR-030 | Scheduler DB 연동 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | 파일 → DB 전체 전환. 트랜잭션 패턴 적용 | [x] |
| 48 | FR-030 | Config DB URL | `default_config.py` | — | `_get_database_url` | Postgres URL 자동 구성 (SUPABASE_DB_URL / POSTGRES_* env vars) | [x] |
| 49 | FR-030 | report_store.py 삭제 | ~~`virtual_trade/report_store.py`~~ | — | — | 파일 삭제 (SummaryAgent + DB로 대체) | [x] |
| 50 | FR-006 | strategy_json 파싱 | `graph/signal_processing.py` | `SignalProcessor` | `process_signal`, `_extract_strategy_json` | ```strategy_json 코드블록 파싱 + LLM fallback | [x] |
| 51 | FR-036 | 중복 실행 방지 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle` | last_data_date 비교, 새 데이터 없으면 스킵 | [x] |
| 52 | — | 런타임 컨텍스트 | `runtime_context.py` | — | `set_schedule_context`, `reset_schedule_context`, `get_current_schedule_job_id`, `get_current_schedule_id` (alias), `log_schedule_error` | contextvars로 스케줄 Job ID 전파 | [x] |
| 53 | — | 커스텀 예외 | `errors.py` | `DataVendorError`, `DecisionParseError`, `AgentExecutionError` | — | 에러 유형별 처리 분기 지원 | [x] |
| 54 | FR-035 | Frontend SPA | `apps/web/` | — | — | Svelte 4 + TypeScript + Vite + svelte-spa-router | [x] |
| 55 | FR-037 | 이벤트 영속화 broadcast | `api/app.py` | — | `broadcast_status` | WS 송신 + schedule_job_events DB 저장 동시 수행 | [x] |

### Phase 3: 구현 완료 (FR-038~050)

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 56 | FR-038 | DB 리셋 스크립트 | `scripts/reset_db.py` | — | `main()`, `reset_postgres()`, `reset_chromadb()` | FK 역순 DROP(`DROP_ORDER` 8테이블) + ChromaDB `shutil.rmtree` + `Database.init_schema()`. `--confirm` 필수, `--keep-chroma` 옵션 | [x] |
| 57 | FR-039 | schedules 테이블 제거 | `storage/database.py` | `Database` | `init_schema` | CREATE TABLE schedules 제거, schedule_configs에 `current_cycle`/`currency`/`initial_capital`/`market` 추가 | [x] |
| 58 | FR-039 | schedule_repo 삭제 | ~~`storage/schedule_repo.py`~~ | — | — | 파일 삭제, 로직을 config_repo + job_repo로 이관 | [x] |
| 59 | FR-039 | schedule_config_repo 확장 | `storage/schedule_config_repo.py` | `ScheduleConfigRepository` | `increment_cycle`, `get_current_cycle` | `current_cycle` 원자적 증가 (`UPDATE ... RETURNING`), MAX() 쿼리 제거 | [x] |
| 60 | FR-039 | schedule_job_repo 확장 | `storage/schedule_job_repo.py` | `ScheduleJobRepository` | `create`, `get_latest_by_config`, `list_by_config`, `update_latest_by_config` | `schedule_config_id` + `scheduled_cycle` 파라미터, config 기반 조회 메서드 | [x] |
| 61 | FR-039 | FK 변경 — reports | `storage/report_repo.py` | `ReportRepository` | `create` | `schedule_id` → `schedule_job_id` FK 파라미터 | [x] |
| 62 | FR-039 | FK 변경 — events | `storage/schedule_event_repo.py` | `ScheduleEventRepository` | `create` | `schedule_id` 컬럼 제거, `schedule_job_id`만 사용 | [x] |
| 63 | FR-039 | Scheduler 리팩토링 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `enqueue_schedule`, `_run_analysis_cycle` | `config_repo.increment_cycle(ticker)` → `job_repo.create(config_id, cycle, ...)`, 트랜잭션 내 schedule_job_id 기반 | [x] |
| 64 | FR-039 | Routes 리팩토링 | `api/routes.py` | — | 전체 | `schedule_id` 참조를 `schedule_job_id`/`schedule_config_id`로 변경, JOIN 쿼리 수정 | [x] |
| 65 | FR-040 | 통화 자동 감지 | `storage/schedule_config_repo.py` | — | `detect_ticker_defaults(ticker)` | 티커 접미사 기반 `(currency, initial_capital, market)` 튜플 반환. `.KS`/`.KQ` → `("KRW", 5_000_000, "kr")`, 기본 → `("USD", 5_000, "us")` | [x] |
| 66 | FR-040/041 | 통화별 cash 계산 | `storage/trade_repo.py` | `TradeRepository` | `get_cash_balance(ticker, initial_capital)` | `WHERE p.ticker = %s AND p.status = 'active'` — active position의 BUY/SELL 합산으로 가용 현금 계산 | [x] |
| 67 | FR-040 | PA 통화 인식 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | `cfg.get("currency")`, `cfg.get("initial_capital")` → PA context에 전달, `trade_repo.create(currency=ticker_currency)` | [x] |
| 68 | FR-041 | 독립 자금 모델 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `_get_cash_available` | `trade_repo.get_cash_balance(ticker, initial_capital)` — active position 기준 격리, 이전 포지션 trades 미포함 | [x] |
| 69 | FR-042 | 자동 청산 로직 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` (인라인) | `return_pct` vs `sl_pct`/`tgt_pct` (±30% 폴백) 체크 → `trade_manager.close_all_positions` + `reflector.reflect_on_position` | [x] |
| 70 | FR-042 | PA stop_loss/target 파싱 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `_parse_decision` | `strategy_update.stop_loss`/`target` 파싱 ($ 제거, float 변환). 스케줄러에서 `position_repo.update_stop_loss_target()` 호출. stop_loss ≥ target 역전 시 무시 (스케줄러 검증). PA 프롬프트에서 MODIFY 액션 제거 (BUY/SELL/HOLD만) | [x] |
| 71 | FR-042 | positions stop_loss/target | `storage/position_repo.py` | `PositionRepository` | `update_stop_loss_target(position_id, stop_loss, target)` | positions 테이블 stop_loss/target 업데이트 | [x] |
| 72 | FR-043 | 매매 가격 보정 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_get_latest_close(ticker, job_id, retries=2, retry_delay=30)` | `(price, data_date_iso)` 튜플 반환. 항상 최신 확정 종가(`history["Close"].iloc[-1]`) 사용. 2회 재시도. `_get_current_price()` 레거시 래퍼 삭제됨 | [x] |
| 73 | FR-043 | executed_at 주입 | `storage/trade_repo.py` | `TradeRepository` | `create(..., executed_at=trade_date)` | `executed_at` 파라미터로 yfinance 데이터 기준일 주입. None이면 `datetime.now()` 폴백 | [x] |
| 73-1 | FR-043 | opened_at 주입 | `storage/position_repo.py` | `PositionRepository` | `create(..., opened_at=date)` | `opened_at` 파라미터로 yfinance 데이터 기준일 주입. None이면 `datetime.now()` 폴백. `trade_manager.open_position()`에서 `date` 전달 | [x] |
| 74 | FR-044 | CronTrigger 변경 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_make_cron_trigger(market)` (staticmethod) | `kr` → `CronTrigger(hour=16, minute=30, timezone="Asia/Seoul")`, `us/기타` → `CronTrigger(hour=17, minute=0, timezone="US/Eastern")` | [x] |
| 75 | FR-045 | 총손익 API | `api/routes.py` | — | `get_metrics` | `total_realized_pnl` = closed positions의 `SELL합-BUY합`, `total_unrealized_pnl` = active positions의 `(current_price-avg_cost)*shares`, `total_pnl` = 합산. 통화 필터 없음(FE에서 처리) | [x] |
| 76 | FR-046 | Closed positions API | `api/routes.py` | — | `get_positions_closed` | `GET /positions/closed` — `positions WHERE status='closed'` + `outcome` 계산 (`return_pct >= 0` → win) | [x] |
| 77 | FR-047 | Win/Loss 판정 통일 | `graph/reflection.py:112`, `api/routes.py:518` | — | — | `return_pct >= 0` → `"win"`, `< 0` → `"loss"` 양쪽 일원화 | [x] |
| 78 | FR-050 | Codex LLM 클라이언트 | `llm_clients/codex_client.py` | `ChatCodex(BaseChatModel)`, `CodexClient(BaseLLMClient)` | `_generate`, `bind_tools`, `_convert_messages` | `oauth_codex.Client` → `_engine.responses.create()`. Responses API + tool calling 지원. `gpt-5.3-codex` 단일 모델 | [x] |
| 79 | FR-050 | Factory 확장 | `llm_clients/factory.py` | — | `create_llm_client` | `provider == "codex"` → `CodexClient(model, ...)` 분기 | [x] |
| 80 | FR-050 | Config 확장 | `default_config.py` | — | — | `LLM_PROVIDER=codex` → `deep_think_llm`/`quick_think_llm` 모두 `"gpt-5.3-codex"`로 설정 | [x] |

> **경로 접두사**: # 1~55, 56~80 파일 경로는 `tradingagents/` 하위 (scripts/ 제외)
> **Impl**: `[x]` = 구현 완료

### Phase 4: 미구현 (FR-051~054)

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 81 | FR-051 | RAG 쿼리 enrichment | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `_build_rag_query` | market/sector 텍스트 부착. `schedule_configs.market` + `yfinance Ticker.info.sector` 사용 | [ ] |
| 82 | FR-052 | HybridMemory 파이프라인 재설계 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | FTS top-3 + ChromaDB top-3 → 중복제거 + RRF top-3 → usefulness < 40 배제 → usefulness DESC → top-K. 기존 top-10+top-10 RRF 교체 | [ ] |
| 83 | FR-052 | usefulness 필터링 | `memory/hybrid_memory.py` | `HybridMemory` | `_apply_usefulness_filter` | usefulness_score < 40 하드 배제, DESC 정렬, top-K 컷. `ReflectionRepository` 연동 | [ ] |
| 84 | FR-052 | reflections.usefulness_score 컬럼 | `storage/database.py` | `Database` | `init_schema` | ALTER TABLE reflections ADD COLUMN usefulness_score (ensure_column 패턴) | [ ] |
| 85 | FR-052 | ReflectionRepo usefulness 메서드 | `storage/reflection_repo.py` | `ReflectionRepository` | `get_usefulness_scores(reflection_ids)`, `update_usefulness_score(reflection_id, delta)` | 벌크 조회 + ±1 업데이트 (0~100 클램핑) | [ ] |
| 86 | FR-052 | RAG_TOP_K 환경변수 | `default_config.py` | — | — | `"rag_top_k": int(os.getenv("RAG_TOP_K", "1"))` 추가 | [ ] |
| 87 | FR-053 | RAG Validator 모듈 | `rag_validator/__init__.py` | — | — | 새 모듈 생성 | [ ] |
| 88 | FR-053 | RAG Validator 프롬프트 | `rag_validator/prompt.py` | — | `build_validation_prompt` | 회고분석 결과 + RAG 문서별 → "PA가 이 경험을 반영했는가?" 판정 프롬프트. 구조화 출력 (JSON verdict + justification) | [ ] |
| 89 | FR-053 | RAG Validator 서비스 | `rag_validator/service.py` | `RAGValidatorService` | `validate(retrospective_id)`, `_evaluate_document(retro_content, rag_doc)`, `_apply_score_adjustments(results)`, `_generate_report(results)` | 오케스트레이터: 입력 수집 → 문서별 평가 → 점수 조정 → 리포트 생성 | [ ] |
| 90 | FR-053 | RAG Validator 멱등성 | `rag_validator/service.py` | `RAGValidatorService` | `_is_already_evaluated(retrospective_id, reflection_id)` | (retrospective_id, reflection_id) 쌍 중복 평가 방지 | [ ] |
| 91 | FR-053 | RAG Validator API | `api/routes.py` | — | `POST /rag-validator/run`, `GET /rag-validator/reports` | 수동 실행 트리거 + 리포트 조회. Bearer 인증 | [ ] |
| 92 | FR-053 | RAG Validator 큐 통합 | `api/app.py` | — | `_queue_worker` | `item['type'] == 'rag_validation'` 분기. priority=2 (스케줄 0, 회고분석 1, RAG 검증 2) | [ ] |
| 93 | FR-054 | 키워드 검색 | `storage/reflection_repo.py` | `ReflectionRepository` | `search_keyword(query, limit)` | `ILIKE '%{query}%'` on reflection + key_lessons | [ ] |
| 94 | FR-054 | 시멘틱 검색 | `memory/hybrid_memory.py` | `HybridMemory` | `search_semantic(query, limit)` | ChromaDB 단독 쿼리 (RRF 없이) | [ ] |
| 95 | FR-054 | 검색 API | `api/routes.py` | — | `GET /reflections/search?q=...&mode=keyword|semantic&limit=20` | 모드별 전략 디스패치. 공개 READ | [ ] |

---

## 4. Implementation Plan

### 📂 Required Reference Files

| File | Reference Purpose |
|------|------------------|
| `tradingagents/graph/trading_graph.py` | 메모리 초기화, propagate(), reflect_and_remember() 패턴 |
| `tradingagents/graph/reflection.py` | Reflector 프롬프트 구조, reflect_on_position |
| `tradingagents/memory/hybrid_memory.py` | Postgres FTS + ChromaDB Hybrid RAG |
| `tradingagents/virtual_trade/trade_manager.py` | DB 기반 매매 관리 |
| `tradingagents/virtual_trade/portfolio_agent.py` | PA 프롬프트 + allocation_pct 기반 수량 계산 |
| `tradingagents/scheduler/ticker_scheduler.py` | 분석 사이클 트랜잭션 패턴 |
| `tradingagents/storage/database.py` | Postgres 연결 관리 + DDL |
| `tradingagents/api/app.py` | FastAPI lifespan + 큐 워커 + broadcast |
| `tradingagents/api/routes.py` | REST 엔드포인트 전체 |

### Step-by-Step Implementation

1. **Step 1: Database Layer (FR-030)**
   - `storage/__init__.py` 생성
   - `storage/database.py`: Postgres 연결, per-thread 풀, `init_schema()` (전체 DDL 실행 + 마이그레이션 ensure_column)
   - 8개 Repository 클래스

2. **Step 2: HybridMemory Postgres FTS 전환 (FR-033)**
   - `rank_bm25` import 제거, JSONL `_load_corpus` / `_save_entry` 제거
   - BM25 경로: `ReflectionRepository.search_fts(query)` (`ts_rank_cd` + `plainto_tsquery`)
   - Vector 경로: ChromaDB 유지 (단일 컬렉션)
   - RRF 합산 로직 유지

3. **Step 3: 요약에이전트 (FR-032)**
   - `agents/summary_agent.py`: 12개 raw → 13개 요약, quick_think_llm

4. **Step 4: 반성 집중화 (FR-031)**
   - `reflect_on_position(position_id, db, ticker)`: reports+trades 조회 → 반성문 생성

5. **Step 5: TradeManager DB 리팩터링 (FR-030)**
   - JSON CRUD 제거, PositionRepository + TradeRepository 사용

6. **Step 6: 분석 사이클 트랜잭션 (FR-030)**
   - `_run_analysis_cycle_impl`: LLM 호출 밖에서 DB 쓰기만 트랜잭션

7. **Step 7: 분석 객관성 + PA 강화 (FR-021, FR-022, FR-029)**
   - 12에이전트 포지션 주입 제거
   - PA: 분석(6):경험(4) 가중치, 디바이어싱, allocation_pct 기반 수량

8. **Step 8: 웹 API (FR-025~026, FR-037)**
   - REST 23개 엔드포인트 + WS + Bearer 인증
   - broadcast_status: WS + schedule_job_events DB 동시 저장

9. **Step 9: Frontend SPA (FR-035)**
   - Svelte 4 + svelte-spa-router + 11개 라우트 (10개 페이지 + NotFoundRedirect)

10. **Step 10: 중복 실행 방지 (FR-036)**
    - schedule_configs.last_data_date vs yfinance 최신 거래일 비교

---

## 5. Sequence Diagrams

### 5.1 Full Analysis Cycle (1 Schedule Execution)

```
┌─ 스케줄 트리거 ──────────────────────────────────────────────────────────┐
│                                                                            │
│  schedule_configs.current_cycle += 1 (원자적 증가, FR-039)                │
│  ScheduleJobRepository.create(schedule_config_id, cycle, 'pending')        │
│                                                                            │
│  0. 중복 실행 방지 (FR-036)                                               │
│     schedule_configs.last_data_date vs yfinance 최신 거래일                │
│     → 동일하면 'skipped' 처리, 종료                                       │
│                                                                            │
│  0.5. 자동 청산 체크 (FR-042)                                             │
│     _get_latest_close(ticker) → (price, date) (FR-043)                    │
│     active position의 return_pct 계산                                     │
│     → stop_loss/target 또는 ±30% 초과 시 PA 거치지 않고 즉시 전량 청산   │
│     → 청산 처리 후 반성에이전트 실행, 분석 파이프라인은 스킵              │
│                                                                            │
│  1. G-ANT 분석 (12에이전트 파이프라인, 기존 그대로)                       │
│     Market → Social → News → Fundamentals                                  │
│     → Bull ↔ Bear (N rounds) → Research Judge                             │
│     → Trader → Aggressive ↔ Conservative ↔ Neutral → Risk Judge           │
│     → Signal: BUY/HOLD/SELL + strategy_json                               │
│     ※ 12에이전트는 포지션 정보 없이 완전 객관적 분석 (FR-021)            │
│     ※ 각 에이전트 완료 시 broadcast_status → WS + schedule_job_events    │
│                                                                            │
│  2. PA 판단 (deep_think_llm)                                              │
│     ← final_state 읽기                                                     │
│     ← PositionRepository.get_active(ticker) → current position            │
│     ← TradeRepository.get_cash_balance(ticker, initial_capital) → 가용 현금│
│     ← HybridMemory.get_memories(query) → RAG 검색 (있을 때만)            │
│     → allocation_pct 기반 수량 계산 + 매매 결정                           │
│     → strategy_update: stop_loss/target 파싱 (역전 시 무시)               │
│     → PositionRepository.update_stop_loss_target() (트랜잭션 밖)         │
│                                                                            │
│  3. SummaryAgent.summarize(final_state, pa_opinion)                        │
│     → 13개 요약 dict + decision_position/portfolio_action/pipeline_strategy│
│                                                                            │
│  4. 청산 확인 (shares == 0 after trade?)                                   │
│     ├─ NO  → skip                                                          │
│     └─ YES → Reflector.reflect_on_position(position_id, db, ticker)       │
│              + yfinance Ticker.info → sector/industry/market 메타데이터   │
│                                                                            │
│  ═══ BEGIN TRANSACTION ═══                                                  │
│  5. ScheduleJobRepository.update_status('done')                            │
│  6. TradeManager.open_position / close_positions (매매가 있을 때만)        │
│  7. ReportRepository.create(schedule_job_id, position_id, summaries)       │
│  8. TradeRepository.create(position_id, report_id, action, shares, price, │
│     currency=ticker_currency, executed_at=trade_date)                      │
│  ═══ COMMIT ═══                                                            │
│                                                                            │
│  9. (청산 시, 트랜잭션 외부)                                              │
│     ReflectionRepository.create(pos_id, reflection, ...)                   │
│     + HybridMemory.add_situations(reflection) → ChromaDB 벡터 저장        │
│                                                                            │
│  10. schedule_configs.last_data_date 업데이트                              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

> **트랜잭션 전략**: LLM 호출(1~4)은 트랜잭션 밖에서 실행. DB 쓰기(5~8)만 하나의 트랜잭션으로 묶어 원자성 보장.
> **ChromaDB**: 트랜잭션 밖에서 별도 저장 (ChromaDB는 Postgres 트랜잭션과 무관). 실패 시 로그만 남기고 진행.
> **Reflection**: 트랜잭션 밖에서 실행. 실패해도 포지션 청산은 이미 커밋됨.

### 5.2 Hybrid RAG Search (PA Memory Read) — FR-051/052 개편

```
PA: "반도체 대형주 모멘텀 진입 경험?"
         │
    1. Query Enrichment (FR-051)
       + "Market: us Sector: Technology"
         │
    ┌────┴────┐
    ▼         ▼
 ChromaDB    Postgres FTS
 top-3       top-3
 (시멘틱     (키워드 매칭,
  맥락 반영)  enrichment 무관)
    │         │
    └────┬────┘
         ▼
    2. 중복 제거 + RRF top-3 (적합성 커팅)
         ▼
    3. usefulness_score < 40 하드 배제
       → usefulness DESC 정렬
       → top-K (env: RAG_TOP_K, 기본 1)
         ▼
    4. 레이블 부착
       [✅ 성공 사례] / [⚠️ 실패 사례]
         ▼
    PA에 주입 (파이프라인 60% + 경험 40%)
```

### 5.4 RAG Validator Flow (FR-053)

```
회고분석 완료 (retrospective_analyses.status = 'completed')
         │
    사용자 또는 자동 트리거
         │
         ▼
RAGValidatorService.validate(retrospective_id)
         │
    ┌────┴──────────────────────────────────────┐
    │  retrospective_analyses.analysis_content  │
    │  reports WHERE position_id = X            │
    │  → rag_used=true인 reports의 rag_docs     │
    │  → memories[*].reflection_id 추출         │
    └────┬──────────────────────────────────────┘
         │
    각 RAG 문서별 LLM 평가:
    "PA가 이 경험을 실제로 반영했는가?"
    → verdict: reflected | not_reflected | ambiguous
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 점수 조정   리포트 생성
 ±1 UPDATE   효과 분석
 (0~100      보고서
  클램핑)    (사람이 읽음)
```

### 5.3 Reflection Agent Flow (청산 시에만)

```
position.shares == 0 확인
         │
         ▼
Reflector.reflect_on_position(position_id, db, ticker)
         │
    ┌────┴────────────────────────────────────┐
    │  ReportRepository.get_by_position()     │
    │  → 전 사이클 에이전트별 요약 조회       │
    │                                         │
    │  TradeRepository.get_by_position()      │
    │  → 전체 매매 이력 조회                  │
    │                                         │
    │  PositionRepository.get_by_id()         │
    │  → 포지션 메타 (수익률, 보유 기간)     │
    │                                         │
    │  deep_think_llm 호출                    │
    │  → 반성문 + 핵심 교훈 + outcome 생성   │
    └────┬────────────────────────────────────┘
         │
    ┌────┴──────────────┐
    │                    │
    ▼                    ▼
 Postgres             ChromaDB
 reflections INSERT   벡터 임베딩 저장
 + GIN FTS 자동 인덱싱 (내장 ONNX)
```

---

## 6. API Specification

### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | 헬스체크 (status, scheduler_running, queue_length, schedules_count, uptime) |
| GET | `/queue` | — | 분석 큐 상태 (running, pending, total) |
| GET | `/metrics` | — | 대시보드 지표 (active/closed/wins/losses + total_realized_pnl + total_unrealized_pnl + total_pnl). 통화 필터 없음 — FE 클라이언트 사이드 필터링 (FR-045) |
| GET | `/activity` | — | 최근 활동 피드 (?limit, ?since_hours, ?ticker) |
| GET | `/schedules` | — | 스케줄 목록 (?cursor, ?limit) |
| GET | `/schedules/summary` | — | 오늘 스케줄 실행 요약 (done/failed/skipped/running/pending) |
| POST | `/schedules` | Bearer | 새 스케줄 등록 (ticker, interval_days, display_name) |
| DELETE | `/schedules/{ticker}` | Bearer | 스케줄 삭제 + 큐 정리 |
| POST | `/schedules/{ticker}/retry` | Bearer | 실패 스케줄 재시도 |
| GET | `/schedules/{ticker}/cycles` | — | 분석 사이클 이력 (?cursor, ?limit) |
| GET | `/schedules/{ticker}/cycles/{id}/events` | — | 사이클별 에이전트 이벤트 |
| GET | `/positions` | — | 포지션 목록 (?status 필터) |
| GET | `/positions/{id}` | — | 포지션 상세 (trades + reports) |
| GET | `/positions/market` | — | 활성 포지션 + yfinance 현재가 + PnL |
| GET | `/positions/closed` | — | 청산 포지션 목록 (outcome, return_pct, currency 포함) (FR-046) |
| GET | `/position/{id}/graph` | — | OHLC 일봉 차트 (?days, 인메모리 캐시: 당일 24h TTL / 과거 7d TTL) |
| GET | `/reports` | — | 보고서 목록 (?ticker, ?position_id, ?cursor, ?limit) |
| GET | `/reports/tickers` | — | 티커별 보고서 요약 |
| GET | `/reflections` | — | 반성문 목록 (?outcome, ?cursor, ?limit). FR-049 FE에서 사용 |
| GET | `/search` | — | Hybrid RAG 검색 (?query, ?limit) |
| GET | `/search/tickers` | — | Yahoo Finance 티커 검색 (?q) |
| GET | `/tickers/names` | — | 티커 display_name 맵 |
| GET | `/live/{ticker}/events` | — | 실시간 에이전트 이벤트 (?limit) |
| GET | `/reflections/search` | — | 매매검증 검색 (?q, ?mode=keyword\|semantic, ?limit) (FR-054) |
| POST | `/rag-validator/run` | Bearer | RAG Validator 수동 실행 (retrospective_id 또는 전체) (FR-053) |
| GET | `/rag-validator/reports` | — | RAG 효과 분석 리포트 조회 (?cursor, ?limit) (FR-053) |

### WebSocket

| Path | Description |
|------|-------------|
| `WS /ws/analyze/{ticker}` | 에이전트 상태 실시간 스트리밍 (step/phase 포함, timeout 1h) |

### Authentication (FR-026)

```
READ 엔드포인트: 인증 없이 공개 접근
WRITE 엔드포인트 (POST, DELETE): Authorization: Bearer {ADMIN_TOKEN}
ADMIN_TOKEN: 환경변수 TRADINGAGENTS_ADMIN_TOKEN (미설정 시 서버 시작 차단)
```

---

## 7. Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRADINGAGENTS_ADMIN_TOKEN` | WRITE 인증 토큰 (필수, 미설정 시 시작 차단) | — |
| `TRADINGAGENTS_CORS_ORIGINS` | CORS 허용 도메인 (쉼표 구분, 비어있으면 `*`) | `""` |
| `LLM_PROVIDER` | LLM 제공자 (`gemini-cli` / `antigravity` / `codex`) | `gemini-cli` |
| `SUPABASE_DB_URL` | Supabase Postgres 연결 URL | — |
| `SUPABASE_DIRECT_URL` | DDL 실행용 Direct 연결 URL | — |
| `POSTGRES_USER` / `PASSWORD` / `DB` / `HOST` / `PORT` | 로컬 Postgres 개별 설정 | — |
| `TRADINGAGENTS_SCHEDULER_ENABLED` | APScheduler 활성화 | `false` |
| `TRADINGAGENTS_LOG_LEVEL` | 로그 레벨 | `INFO` |
| `TRADINGAGENTS_STOCK_DOWNLOAD_DAYS` | yfinance 다운로드 기간 | `330` |
| `TRADINGAGENTS_STOCK_DOWNLOAD_BUFFER_DAYS` | stockstats 버퍼 | `300` |
| `TRADINGAGENTS_STOCK_CACHE_STALE_DAYS` | 캐시 유효 기간 | `3` |
| `TRADINGAGENTS_CHROMA_PATH` | ChromaDB 저장 경로 | `memory/chroma` |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage API 키 (optional) | — |
| `RAG_TOP_K` | PA 주입 경험 수 (초기 1, 추후 2~3) (FR-052) | `1` |

---

## 8. Risks & Tradeoffs

### 설계 결정 근거

| 결정 | 선택 | 대안 (기각) | 근거 |
|------|------|------------|------|
| DB 엔진 | Postgres (Supabase 호환) | SQLite | 운영 환경 안정성, 동시 접근, 인프라 일원화 |
| DB 접근 패턴 | Repository 패턴 (테이블별 클래스, 7개) | 단일 Database 래퍼 | SRP, 테스트 용이성, 향후 확장 |
| SQL 레이어 | Raw SQL (psycopg) | SQLAlchemy Core | 의존성 최소, 쿼리 단순 (<10 테이블) |
| 반성 구조 | PA 1곳 집중 | 5에이전트 개별 반성 | LLM 호출 5→1, 데이터 오염↓, 비용↓ |
| BM25 엔진 | Postgres GIN FTS | rank_bm25 + JSONL / SQLite FTS5 | 의존성↓, 인덱스 자동관리, DB 일원화 |
| 트랜잭션 범위 | DB 쓰기만 묶음 (LLM 밖) | 전체 사이클 묶음 | DB 락 최소화 (ms급), API 동시 읽기 보장 |
| 마이그레이션 | Clean break (기존 데이터 없음) | 파일→DB 변환 스크립트 | 기존 운영 데이터 없음 |
| 리포트 저장 | 개별 컬럼 + pipeline_strategy JSON | 단일 JSON blob | 컬럼별 조회, FTS 검색, 구조 보장 |
| ChromaDB 저장 | 트랜잭션 밖 별도 저장 | 트랜잭션 내 포함 | ChromaDB는 Postgres와 별도 엔진, 원자성 불가 |
| Reflection 저장 | 트랜잭션 밖 실행 | 트랜잭션 내 포함 | 반성 실패가 매매 커밋을 롤백하면 안 됨 |
| Frontend | Svelte 4 SPA (해시 라우팅) | React / Vue / SSR | 번들 크기 최소, 모바일 최적화, 단일 사용자 |
| 자금 모델 | 포지션별 독립 자금 | 공유 자금 풀 | 분석 검증 시스템 (자동매매 아님), 포지션 간 간섭 제거 (FR-041) |
| 자동 청산 | PA stop_loss/target 우선 + ±30% 폴백 | 고정 비율만 | PA의 전략적 판단 반영, 안전장치 이중화 (FR-042) |
| 스케줄 테이블 | schedules 제거, 7테이블 | 기존 8테이블 유지 | schedules↔schedule_jobs 1:1 중복 제거, FK 단순화 (FR-039) |
| 통화 처리 | 통화별 분리 (환율 변환 안 함) | 환율 변환 합산 | 환율 변동 리스크 제거, 단순성 (FR-040) |
| 스케줄 타이밍 | CronTrigger 시장별 | IntervalTrigger 단순 간격 | 장마감 후 종가 확정 데이터 기반 분석 보장 (FR-044) |
| RAG 맥락 인식 | 쿼리 enrichment (텍스트 부착) | DB 하드 필터 (WHERE market = :market) | 인프라 변경 없음, graceful degradation, ChromaDB 시멘틱이 맥락 자연 반영 (FR-051) |
| RAG 파이프라인 순서 | RRF(적합성) → usefulness(유용성) | usefulness → RRF | 초기 usefulness 전부 50이라 변별력 없음. 변별력이 항상 있는 축(RRF)으로 먼저 커팅이 안전 (FR-052) |
| RAG top-K 초기값 | K=1 | K=3 | 1개일 때 RAG Validator 귀인 평가가 깨끗함. 3개면 어느 문서가 영향을 줬는지 판별 어려움 (FR-052) |
| usefulness 하드 플로어 | 40 | 30 또는 동적 | 기본값 50에서 10회 연속 "쓸모없다" 판정 시 도달. 충분히 보수적. 운영 데이터 보면서 40~43 조절 예정 (FR-052) |
| usefulness 점수 범위 | 0~100 클램핑 | 무한 | 장기 누적 시 점수 폭주 방지 (Best Practice Advisor 제안 반영) |
| RAG Validator 평가 단위 | 문서별 개별 평가 | 사이클 단위 일괄 평가 | 문서별이어야 usefulness_score 귀인이 정확 (FR-053) |
| RAG Validator 조정 폭 | ±1 고정 | 신뢰도 가중 (±1~3) | 느린 수렴이 의도. 빠른 적용은 노이즈에 반응할 위험 (FR-053) |
| RAG 소스 범위 | 반성(매매검증)만 | 회고분석 포함 | 회고분석은 검증/시각화 전용. RAG 소스 단일화로 역할 명확 |
| 검색 API 설계 | 단일 엔드포인트 + mode 파라미터 | 모드별 별도 엔드포인트 | API 표면 최소화, 클라이언트 로직 단순화 (FR-054) |

### 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Postgres 연결 끊김 | 분석 중단 | per-thread 재연결 (`get_connection`에서 `SELECT 1` 체크 후 자동 재연결) |
| ChromaDB 벡터 비동기 | 반성 저장 후 즉시 검색 불가 | 반성 직후 동일 사이클에서 RAG 읽기 없음 (다음 사이클부터) |
| Postgres FTS 한국어 토크나이저 부재 | 한글 검색 품질 저하 | `'simple'` 설정 + 벡터 검색이 보완 |
| 요약 품질 편차 | quick_think_llm 성능 한계 | 각 컬럼 200~400 토큰 목표 명시, 프롬프트 엔지니어링 |
| yfinance 가격 조회 실패 | 대시보드 PnL 표시 불가 | KRX 대체 심볼 fallback (`.KS` ↔ `.KQ`), 가격 null 허용 |
| LLM rate limit (429) | 분석 지연 | 30s 대기 후 **동일 모델** 재시도 (최대 5회, `MAX_RETRIES=5`) |
| LLM capacity exhaustion (503) | 분석 품질 저하 | 모델 다운그레이드 fallback chain: `gemini-2.5-pro → gemini-2.5-flash`, `gemini-3-pro-high → gemini-3-pro-low → gemini-3-flash` |

### 가정사항

- 단일 사용자, 순차 실행 → 쓰기 충돌 없음
- 분석 사이클당 ~1시간, DB 쓰기는 사이클 말미 수 ms
- 반성 데이터는 청산 시에만 생성 → 점진적 축적 (급격한 증가 없음)
- ChromaDB 내장 임베딩 (`all-MiniLM-L6-v2`) 품질이 본 용도에 충분
- Supabase Free Tier 또는 로컬 Docker Postgres 사용

---

## 9. Error/Auth/Data Checklist

### Error Cases

| # | Category | Error | Handling |
|---|----------|-------|----------|
| 1 | Postgres | Connection lost | per-thread 재연결 (`get_connection` 내 SELECT 1 체크) |
| 2 | Postgres | Transaction failure | 자동 롤백 (`execute_in_transaction`), schedule_job status='failed' |
| 3 | ChromaDB | 벡터 저장 실패 | 로그 남기고 계속 진행, `chroma_available=False`로 FTS-only 모드 전환 |
| 4 | LLM | 요약에이전트 실패 | 해당 컬럼 truncated raw 저장 (fallback) |
| 5 | LLM | 반성에이전트 실패 | 기본 반성문 생성 (fallback), position은 이미 closed |
| 6 | Network | 데이터 벤더 fetch 실패 | 30s 간격 2회 재시도 후 다음 벤더 fallback, schedule_jobs 기록 |
| 7 | Auth | ADMIN_TOKEN 미설정 | 서버 시작 차단 (`raise RuntimeError`) |
| 8 | Auth | 잘못된 Bearer 토큰 | 401 Unauthorized |
| 9 | LLM | Decision parse 실패 | `DecisionParseError` → 스케줄 실패 + 자동 재큐잉 1회 |
| 10 | LLM | Agent execution 실패 | `AgentExecutionError` → 스케줄 실패 + 자동 재큐잉 1회 |
| 11 | Data | 모든 벤더 실패 | `DataVendorError` → 스케줄 실패 (재큐잉 없음) |
| 11a | Data | 현재가 조회 실패 | yfinance 5일 히스토리 조회, 2회 재시도(30s 간격), 모두 실패 시 `DataVendorError` |
| 12 | Schedule | 중복 스케줄 등록 | ticker 기준 중복 체크 → 409 Conflict |
| 13 | Schedule | 새 데이터 없음 | schedule_job status='skipped' (FR-036) |
| 14 | Transaction | 부분 실패 | 전체 롤백, schedule_job status='failed' |
| 15 | Server | 서버 재시작 시 running job | self-heal: running→failed 마킹 후 재큐잉 |
| 16 | RAG | 양쪽 retriever 빈 결과 | 빈 결과 반환, PA는 RAG 없이 파이프라인 결론만으로 판단 (FR-052) |
| 17 | RAG | FTS 또는 ChromaDB 한쪽 실패 | 살아있는 쪽 결과만으로 진행. 로그 남김 (FR-052) |
| 18 | RAG | usefulness 필터 후 전부 배제됨 | 빈 결과 반환. 임계값 완화 안 함 (FR-052) |
| 19 | RAG | usefulness_score 경계값 (0 또는 100) | 클램핑 처리. 조정은 no-op. 로그 남김 (FR-053) |
| 20 | RAG Validator | LLM이 ambiguous 판정 | ±0 (점수 변경 없음). 로그에 기록 (FR-053) |
| 21 | RAG Validator | 중복 평가 시도 | 멱등성 가드: (retrospective_id, reflection_id) 이미 평가 시 스킵 (FR-053) |
| 22 | Search | 시멘틱 검색 시 ChromaDB 불가 | 503 반환. 키워드 검색은 정상 작동 (FR-054) |

### Authorization

| Action | Required Permission | Validation Location | On Failure |
|--------|-------------------|-------------------|-----------|
| GET 엔드포인트 | 없음 (공개) | — | — |
| POST /schedules | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| DELETE /schedules/{ticker} | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| POST /schedules/{ticker}/retry | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| POST /rag-validator/run | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| GET /reflections/search | 없음 (공개) | — | — |
| GET /rag-validator/reports | 없음 (공개) | — | — |

### Data Integrity Rules

| Validation Item | Validation Timing | On Failure |
|----------------|------------------|-----------|
| schedule FK → reports | report INSERT 시 | Postgres FK constraint |
| position FK → trades | trade INSERT 시 | Postgres FK constraint |
| report FK → trades | trade INSERT 시 | Postgres FK constraint |
| position FK → reflections | reflection INSERT 시 | Postgres FK constraint |
| schedule_configs.ticker UNIQUE | config UPSERT 시 | ON CONFLICT DO UPDATE |
| schedule_job_events (job_id, agent) UNIQUE | event INSERT 시 | ON CONFLICT DO UPDATE |
| position.shares ≥ 0 | 매도 시 application-level | ValueError |
| 큐 중복 방지 | enqueue 시 `_is_ticker_queued` 체크 | 스킵 (로그) |
| 재큐잉 1회 제한 | `_requeued_job_ids` set (job 완료 시 `discard`) | 스킵 (로그) |

---

## 10. Additional Design Details

### 10.1 REST API 페이지네이션

| 항목 | 값 |
|------|-----|
| 방식 | **혼합**: `/schedules`는 offset 기반, 나머지는 id cursor 기반 |
| 기본 limit | 10건 |
| 최대 limit | 100건 |
| 파라미터 | `/schedules`: `?cursor={offset}&limit={n}` / 나머지: `?cursor={last_id}&limit={n}` |

### 10.2 POST /schedules 요청 스키마

```python
class ScheduleRequest(BaseModel):
    ticker: str               # 필수
    interval_days: int = 1    # 선택 (기본 1일)
    display_name: str = None  # 선택 (티커 한글명)
```

### 10.3 큐 영속성

- `asyncio.Queue`는 메모리 기반이지만, **schedule_jobs 테이블의 `status`** 로 영속화
- 서버 재시작 시:
  1. `status='running'` → `failed` 마킹 (self-heal)
  2. 오늘 `done`이 아닌 스케줄 재큐잉 (`has_done_today_for_ticker` 체크)

### 10.4 실패 스케줄 재시도

| 항목 | 값 |
|------|-----|
| 자동 재시도 | `DecisionParseError`, `AgentExecutionError` → 자동 재큐잉 **1회** |
| 수동 재시도 | `POST /schedules/{ticker}/retry` (Bearer 인증) |
| `DataVendorError` | 자동 재시도 없음 (데이터 문제) |

### 10.5 WebSocket 메시지 포맷

```json
{
  "agent": "Market Analyst",
  "status": "running",
  "message": "Market Analyst running",
  "step": 1,
  "phase": "Data Collection",
  "total_steps": 13,
  "timestamp": "2026-02-20T09:30:00+00:00"
}
```

### 10.6 에이전트 단계 매핑

| Agent | Step | Phase |
|-------|------|-------|
| Market Analyst | 1 | Data Collection |
| Social Analyst | 2 | Data Collection |
| News Analyst | 3 | Data Collection |
| Fundamentals Analyst | 4 | Data Collection |
| Bull Researcher | 5 | Investment Debate |
| Bear Researcher | 6 | Investment Debate |
| Research Manager | 7 | Investment Debate |
| Trader | 8 | Trade Decision |
| Aggressive Analyst | 9 | Risk Assessment |
| Neutral Analyst | 10 | Risk Assessment |
| Conservative Analyst | 11 | Risk Assessment |
| Risk Judge | 12 | Risk Assessment |
| Portfolio Agent | 13 | Execution |

### 10.7 LLM 모델 매핑 및 Resilience

| Config 모델명 | gemini-cli 실제 모델 | 용도 |
|---|---|---|
| `gemini-3-pro-high` | `gemini-2.5-pro` | deep_think_llm (PA, Reflector, Research Manager, Risk Judge) |
| `gemini-3-flash` | `gemini-2.5-flash` | quick_think_llm (4 Analysts, Researchers, Trader, SummaryAgent) |
| `gemini-3-pro-low` | (antigravity 전용) | 503 fallback 중간 단계 |
| `gemini-3-flash-lite` | `gemini-2.5-flash-lite` | 미사용 (품질 부족) |
| `gpt-5.3-codex` | `gpt-5.3-codex` (codex 프로바이더) | deep_think_llm + quick_think_llm 단일 모델 (FR-050) |

**429 (Rate Limit)**: 30s 대기 → 동일 모델 재시도 (최대 5회)
**503 (Capacity)**: 모델 다운그레이드 chain 적용 후 다음 모델로 즉시 재시도

```
Fallback chain:
  gemini-2.5-pro → gemini-2.5-flash
  gemini-3-pro-high → gemini-3-pro-low → gemini-3-flash
```

### 10.9 Postgres 연결 관리

| 항목 | 값 |
|------|-----|
| 전략 | **per-thread 연결 풀** (`threading.local`) |
| 메인 연결 | `__init__`에서 1개 생성 |
| 워커 연결 | 필요 시 자동 생성 (`get_connection`) |
| 체크 | `SELECT 1`로 연결 유효성 확인, 실패 시 재연결 |
| DDL | `SUPABASE_DIRECT_URL` 있으면 별도 연결로 DDL 실행 |
| autocommit | `False` (명시적 commit/rollback) |

### 10.10 CORS 설정

```python
cors_origins = os.getenv("TRADINGAGENTS_CORS_ORIGINS", "").strip()
origins = [o.strip() for o in cors_origins.split(",") if o.strip()] or ["*"]
allow_credentials = "*" not in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 10.11 UI Metrics (FR-034)

#### 계산식

```
pnl = (current_price - avg_cost) * shares
return_pct = (current_price - avg_cost) / avg_cost * 100

total_unrealized_pnl = Σ pnl
total_unrealized_return_pct = total_unrealized_pnl / Σ(avg_cost * shares) * 100
```

#### KRX 가격 fallback

```python
# 6자리 숫자 티커(KRX) → .KS / .KQ 대체 시도
if ticker.endswith(".KS"):
    alt = ticker.replace(".KS", ".KQ")
elif ticker.endswith(".KQ"):
    alt = ticker.replace(".KQ", ".KS")
```

---

### ⚠️ TBD (Skipped)

| 항목 | 사유 |
|------|------|
| DB 백업 자동화 | Supabase 자체 백업 사용 |
| CORS origins 제한 | Cloudflare 도메인 확보 후 설정 |
| interval_days 격일 스케줄 | 당분간 1(매일) 고정. 향후 `current_cycle % interval_days != 0` 스킵 방식 |
| 사용자 initial_capital 설정 UI | 현재 고정값 (USD $5,000 / KRW ₩5,000,000). 향후 확장 대비 DB 저장 |
