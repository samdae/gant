# Backend Design Doc: TradingAgents Features (FR-013~037)

> Created: 2026-02-11
> Updated: 2026-02-20
> Service: tradingagents
> Type: Backend
> Requirements document: docs/tradingagents/spec.md
> Repo layout: monorepo (`packages/tradingagents`)

## 0. Summary

### Goal

기존 TradingAgents 멀티에이전트 분석 파이프라인에 **영속 메모리(Hybrid RAG)**, **가상 매매 검증**, **스케줄 기반 자동화**를 추가하고, **Postgres 기반 데이터 저장**, **반성 집중화(반성에이전트 1곳)**, **요약에이전트**를 도입하여, AI 분석의 정확도를 정량적으로 추적·학습하는 자기 개선 시스템으로 진화시킨다.

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
- **FR-030: Postgres 전환 — 파일 기반 저장 전면 폐기, 8테이블 + GIN FTS**
- **FR-031: 반성 집중화 — 반성에이전트 1곳, 청산 시에만**
- **FR-032: 요약에이전트 — 개별 요약 컬럼**
- **FR-033: BM25 엔진 교체 — rank_bm25 → Postgres FTS (GIN)**
- **FR-035: Svelte SPA 프론트엔드**
- **FR-036: 시장 데이터 중복 실행 방지**
- **FR-037: 에이전트 이벤트 영속화**

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

  # REMOVED
  # - rank-bm25: Postgres FTS로 교체 (FR-033)
  # - sqlite3: Postgres로 교체 (FR-030)
```

---

## 2. Architecture Impact

### Components

| Service / Module | Responsibility | Change type |
|---|---|---|
| `tradingagents/storage/` | Postgres DB 연결, Repository 패턴 CRUD (8 repos) | **new** (FR-030) |
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
| `apps/web/` | Svelte SPA 프론트엔드 | **new** (FR-035) |
| `pyproject.toml` | chromadb, apscheduler, fastapi, uvicorn, psycopg | modify |
| ~~`tradingagents/virtual_trade/report_store.py`~~ | ~~JSON array append~~ | **삭제** (FR-032로 대체) |

### Data

#### Postgres Schema — FR-030

> 전체 DDL은 `tradingagents/storage/database.py` 참조

```sql
-- ① schedules: 분석 실행 단위
CREATE TABLE schedules (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT    NOT NULL,
    interval_days   INTEGER NOT NULL DEFAULT 1,
    scheduled_cycle INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedules_ticker ON schedules(ticker);

-- ② schedule_configs: 스케줄 설정 영속화
CREATE TABLE schedule_configs (
    id            BIGSERIAL PRIMARY KEY,
    ticker        TEXT    NOT NULL UNIQUE,
    interval_days INTEGER NOT NULL DEFAULT 1,
    last_data_date DATE,
    display_name  TEXT,
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_configs_ticker ON schedule_configs(ticker);

-- ③ positions: 매매 사이클 (진입 → 청산)
CREATE TABLE positions (
    id          BIGSERIAL PRIMARY KEY,
    ticker      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',
    shares      DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost    DOUBLE PRECISION,
    return_pct  DOUBLE PRECISION,
    opened_at   TIMESTAMPTZ NOT NULL,
    closed_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_positions_ticker_status ON positions(ticker, status);

-- ④ reports: 에이전트별 요약 (스케줄마다 1건) — FR-032
CREATE TABLE reports (
    id                                BIGSERIAL PRIMARY KEY,
    schedule_id                       BIGINT NOT NULL REFERENCES schedules(id),
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
CREATE INDEX idx_reports_schedule ON reports(schedule_id);
CREATE INDEX idx_reports_position ON reports(position_id);

-- ⑤ trades: 개별 BUY/SELL 액션
CREATE TABLE trades (
    id          BIGSERIAL PRIMARY KEY,
    position_id BIGINT NOT NULL REFERENCES positions(id),
    report_id   BIGINT NOT NULL REFERENCES reports(id),
    action      TEXT    NOT NULL,
    shares      DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_report ON trades(report_id);

-- ⑥ reflections: 청산 시 반성에이전트 산출물 — FR-031
CREATE TABLE reflections (
    id          BIGSERIAL PRIMARY KEY,
    position_id BIGINT NOT NULL REFERENCES positions(id),
    reflection  TEXT    NOT NULL,
    key_lessons TEXT,
    outcome     TEXT,
    return_pct  DOUBLE PRECISION,
    market      TEXT,
    sector      TEXT,
    industry    TEXT,
    created_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_reflections_position ON reflections(position_id);

-- ⑦ schedule_jobs: 스케줄 실행 이력 (상태 + 에러)
CREATE TABLE schedule_jobs (
    id            BIGSERIAL PRIMARY KEY,
    schedule_id   BIGINT NOT NULL REFERENCES schedules(id),
    status        TEXT    NOT NULL,
    error_type    TEXT,
    error_message TEXT,
    error_detail  TEXT,
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_jobs_schedule ON schedule_jobs(schedule_id);

-- ⑧ schedule_job_events: 에이전트 진행 이벤트 — FR-037
CREATE TABLE schedule_job_events (
    id              BIGSERIAL PRIMARY KEY,
    schedule_job_id BIGINT REFERENCES schedule_jobs(id),
    schedule_id     BIGINT REFERENCES schedules(id),
    ticker          TEXT,
    agent           TEXT,
    status          TEXT,
    message         TEXT,
    step            INTEGER,
    phase           TEXT,
    created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_schedule_job_events_job ON schedule_job_events(schedule_job_id);
CREATE INDEX idx_schedule_job_events_schedule ON schedule_job_events(schedule_id);
CREATE INDEX idx_schedule_job_events_ticker ON schedule_job_events(ticker);
CREATE INDEX idx_schedule_job_events_created_at ON schedule_job_events(created_at);
CREATE UNIQUE INDEX idx_schedule_job_events_unique ON schedule_job_events(schedule_job_id, agent);

-- ⑨ FTS: Postgres GIN 인덱스 (BM25 검색용) — FR-033
CREATE INDEX idx_reflections_search
    ON reflections
    USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
```

> 제외 컬럼: `sentiment_report` (시의성), `news_report` (bull/bear 논거에 반영)
> 각 요약 컬럼 목표: 200~400 토큰

#### 테이블 관계

```
schedule_configs ──── (ticker 기준 1:N) ──── schedules
schedules 1──N schedule_jobs 1──N schedule_job_events
schedules 1──1 reports N──1 positions 1──N trades
                │                        │
                └── report_id ←──────── trades
                                positions 1──0..1 reflections
```

#### 폐기 대상 (FR-030)

| 기존 | 대체 |
|------|------|
| `eval_results/` 로그 저장 | Postgres `reports` 테이블 |
| `memory/experience/{agent}.jsonl` (5개) | Postgres `reflections` + GIN FTS |
| `memory/experience/chroma/{agent}/` (5개) | ChromaDB 단일 컬렉션 |
| `memory/trade/{TICKER}/trade.json` | Postgres `positions` + `trades` |
| `memory/trade/{TICKER}/report.json` | Postgres `reports` |
| `memory/archive/{TICKER}/{n}/` | `positions.status = 'closed'` |
| `rank_bm25` 라이브러리 | Postgres GIN FTS |

#### Directory Structure (Runtime)

```
Postgres DB (Supabase / Docker)  ← 전체 데이터
apps/web/dist/                   ← Svelte SPA 빌드 결과
packages/tradingagents/
  └── memory/chroma/             ← ChromaDB vector index
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
| 26 | FR-030 | ScheduleRepository | `storage/schedule_repo.py` | `ScheduleRepository` | `create`, `get_by_ticker`, `get_latest_cycle` | schedules CRUD | [x] |
| 27 | FR-030 | ScheduleConfigRepository | `storage/schedule_config_repo.py` | `ScheduleConfigRepository` | `create`, `upsert`, `get_all`, `get_by_ticker`, `delete`, `update_last_data_date`, `get_all_display_names` | schedule_configs CRUD + UPSERT | [x] |
| 28 | FR-030 | PositionRepository | `storage/position_repo.py` | `PositionRepository` | `create`, `get_active`, `update_shares`, `close_position`, `get_by_id` | positions CRUD + status 전환 | [x] |
| 29 | FR-030 | ReportRepository | `storage/report_repo.py` | `ReportRepository` | `create`, `get_by_position`, `get_by_schedule` | reports INSERT (pipeline_strategy JSON 직렬화 포함) | [x] |
| 30 | FR-030 | TradeRepository | `storage/trade_repo.py` | `TradeRepository` | `create`, `get_by_position`, `get_history`, `get_cash_balance` | trades CRUD + 가용 현금 계산 | [x] |
| 31 | FR-030 | ReflectionRepository | `storage/reflection_repo.py` | `ReflectionRepository` | `create`, `get_by_id`, `get_by_position`, `search_fts` | reflections + Postgres FTS 검색 (`ts_rank_cd`) | [x] |
| 32 | FR-030 | ScheduleJobRepository | `storage/schedule_job_repo.py` | `ScheduleJobRepository` | `create`, `update_status`, `get_latest_by_schedule`, `get_latest_by_ticker`, `has_done_today_for_ticker` | schedule_jobs 상태 관리 + 재시도 | [x] |
| 33 | FR-037 | ScheduleEventRepository | `storage/schedule_event_repo.py` | `ScheduleEventRepository` | `create`, `list_by_ticker`, `list_latest_by_ticker`, `list_by_schedule_id` | schedule_job_events UPSERT (agent 기준 유니크) | [x] |
| 34 | FR-031 | 반성 집중화 | `graph/reflection.py` | `Reflector` | `reflect_on_position` | 5개 `reflect_on_*` 제거 → 1개 메서드. DB에서 reports+trades 조회 → 반성문 작성 | [x] |
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
| 52 | — | 런타임 컨텍스트 | `runtime_context.py` | — | `set_schedule_context`, `get_current_schedule_id`, `log_schedule_error` | contextvars로 스케줄 ID/Job ID 전파 | [x] |
| 53 | — | 커스텀 예외 | `errors.py` | `DataVendorError`, `DecisionParseError`, `AgentExecutionError` | — | 에러 유형별 처리 분기 지원 | [x] |
| 54 | FR-035 | Frontend SPA | `apps/web/` | — | — | Svelte 4 + TypeScript + Vite + svelte-spa-router | [x] |
| 55 | FR-037 | 이벤트 영속화 broadcast | `api/app.py` | — | `broadcast_status` | WS 송신 + schedule_job_events DB 저장 동시 수행 | [x] |

> **경로 접두사**: # 1~53 파일 경로는 `tradingagents/` 하위
> **Impl**: `[ ]` = 미구현, `[x]` = 구현 완료

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
   - Svelte 4 + svelte-spa-router + 9개 페이지

10. **Step 10: 중복 실행 방지 (FR-036)**
    - schedule_configs.last_data_date vs yfinance 최신 거래일 비교

---

## 5. Sequence Diagrams

### 5.1 Full Analysis Cycle (1 Schedule Execution)

```
┌─ 스케줄 트리거 ──────────────────────────────────────────────────────────┐
│                                                                            │
│  ScheduleRepository.create(ticker, cycle)                                  │
│  ScheduleJobRepository.create(schedule_id, 'pending')                      │
│                                                                            │
│  0. 중복 실행 방지 (FR-036)                                               │
│     schedule_configs.last_data_date vs yfinance 최신 거래일                │
│     → 동일하면 'skipped' 처리, 종료                                       │
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
│     ← TradeRepository.get_cash_balance(ticker) → 가용 현금                │
│     ← HybridMemory.get_memories(query) → RAG 검색 (있을 때만)            │
│     → allocation_pct 기반 수량 계산 + 매매 결정                           │
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
│  7. ReportRepository.create(schedule_id, position_id, summaries)           │
│  8. TradeRepository.create(position_id, report_id, action, shares, price) │
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

### 5.2 Hybrid RAG Search (PA Memory Read)

```
PA: "반도체 대형주 모멘텀 진입 경험?"
         │
    ┌────┴────┐
    ▼         ▼
 ChromaDB    Postgres FTS
 (벡터)      (GIN + ts_rank_cd)
    │         │
    │   ReflectionRepository.search_fts(query)
    │   → to_tsvector @@ plainto_tsquery → ts_rank_cd
    │         │
    └────┬────┘
         ▼
    RRF 합산: Σ 1/(60 + rank_i(d))
         ▼
    Top-K 결과 + 레이블 부착
    [✅ 성공 사례] / [⚠️ 실패 사례]
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
| GET | `/metrics` | — | 대시보드 지표 (positions, wins, losses, total_unrealized_pnl/return_pct) |
| GET | `/activity` | — | 최근 활동 피드 (?limit, ?since_hours, ?ticker) |
| GET | `/schedules` | — | 스케줄 목록 (?cursor, ?limit) |
| GET | `/schedules/summary` | — | 오늘 스케줄 실행 요약 (done/failed/skipped/running/pending) |
| POST | `/schedules` | Bearer | 새 스케줄 등록 (ticker, interval_days, display_name) |
| DELETE | `/schedules/{ticker}` | Bearer | 스케줄 삭제 + 큐 정리 |
| POST | `/schedules/{ticker}/retry` | Bearer | 실패 스케줄 재시도 |
| GET | `/schedules/{ticker}/cycles` | — | 분석 사이클 이력 (?cursor, ?limit) |
| GET | `/schedules/{ticker}/cycles/{id}/events` | — | 사이클별 에이전트 이벤트 |
| GET | `/positions` | — | 포지션 목록 (?status, ?cursor, ?limit) |
| GET | `/positions/{id}` | — | 포지션 상세 (trades + reports) |
| GET | `/positions/market` | — | 활성 포지션 + yfinance 현재가 + PnL |
| GET | `/position/{id}/graph` | — | OHLC 일봉 차트 (?days, 캐시 지원) |
| GET | `/reports` | — | 보고서 목록 (?ticker, ?position_id, ?cursor, ?limit) |
| GET | `/reports/tickers` | — | 티커별 보고서 요약 |
| GET | `/reflections` | — | 반성문 목록 (?outcome, ?cursor, ?limit) |
| GET | `/search` | — | Hybrid RAG 검색 (?query, ?limit) |
| GET | `/search/tickers` | — | Yahoo Finance 티커 검색 (?q) |
| GET | `/tickers/names` | — | 티커 display_name 맵 |
| GET | `/live/{ticker}/events` | — | 실시간 에이전트 이벤트 (?limit) |

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
| `LLM_PROVIDER` | LLM 제공자 (`gemini-cli` / `antigravity`) | `gemini-cli` |
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

---

## 8. Risks & Tradeoffs

### 설계 결정 근거

| 결정 | 선택 | 대안 (기각) | 근거 |
|------|------|------------|------|
| DB 엔진 | Postgres (Supabase 호환) | SQLite | 운영 환경 안정성, 동시 접근, 인프라 일원화 |
| DB 접근 패턴 | Repository 패턴 (테이블별 클래스, 8개) | 단일 Database 래퍼 | SRP, 테스트 용이성, 향후 확장 |
| SQL 레이어 | Raw SQL (psycopg) | SQLAlchemy Core | 의존성 최소, 쿼리 단순 (<10 테이블) |
| 반성 구조 | PA 1곳 집중 | 5에이전트 개별 반성 | LLM 호출 5→1, 데이터 오염↓, 비용↓ |
| BM25 엔진 | Postgres GIN FTS | rank_bm25 + JSONL / SQLite FTS5 | 의존성↓, 인덱스 자동관리, DB 일원화 |
| 트랜잭션 범위 | DB 쓰기만 묶음 (LLM 밖) | 전체 사이클 묶음 | DB 락 최소화 (ms급), API 동시 읽기 보장 |
| 마이그레이션 | Clean break (기존 데이터 없음) | 파일→DB 변환 스크립트 | 기존 운영 데이터 없음 |
| 리포트 저장 | 개별 컬럼 + pipeline_strategy JSON | 단일 JSON blob | 컬럼별 조회, FTS 검색, 구조 보장 |
| ChromaDB 저장 | 트랜잭션 밖 별도 저장 | 트랜잭션 내 포함 | ChromaDB는 Postgres와 별도 엔진, 원자성 불가 |
| Reflection 저장 | 트랜잭션 밖 실행 | 트랜잭션 내 포함 | 반성 실패가 매매 커밋을 롤백하면 안 됨 |
| Frontend | Svelte 4 SPA (해시 라우팅) | React / Vue / SSR | 번들 크기 최소, 모바일 최적화, 단일 사용자 |

### 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| Postgres 연결 끊김 | 분석 중단 | per-thread 재연결 + autocommit=False |
| ChromaDB 벡터 비동기 | 반성 저장 후 즉시 검색 불가 | 반성 직후 동일 사이클에서 RAG 읽기 없음 (다음 사이클부터) |
| Postgres FTS 한국어 토크나이저 부재 | 한글 검색 품질 저하 | `'simple'` 설정 + 벡터 검색이 보완 |
| 요약 품질 편차 | quick_think_llm 성능 한계 | 각 컬럼 200~400 토큰 목표 명시, 프롬프트 엔지니어링 |
| yfinance 가격 조회 실패 | 대시보드 PnL 표시 불가 | KRX 대체 심볼 fallback (`.KS` ↔ `.KQ`), 가격 null 허용 |

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
| 12 | Schedule | 중복 스케줄 등록 | ticker 기준 중복 체크 → 409 Conflict |
| 13 | Schedule | 새 데이터 없음 | schedule_job status='skipped' (FR-036) |
| 14 | Transaction | 부분 실패 | 전체 롤백, schedule_job status='failed' |
| 15 | Server | 서버 재시작 시 running job | self-heal: running→failed 마킹 후 재큐잉 |

### Authorization

| Action | Required Permission | Validation Location | On Failure |
|--------|-------------------|-------------------|-----------|
| GET 엔드포인트 | 없음 (공개) | — | — |
| POST /schedules | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| DELETE /schedules/{ticker} | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| POST /schedules/{ticker}/retry | Bearer token | `api/auth.py` `check_admin_token` | 401 |

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
| 재큐잉 1회 제한 | `_requeued_schedule_ids` set | 스킵 (로그) |

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

### 10.7 Postgres 연결 관리

| 항목 | 값 |
|------|-----|
| 전략 | **per-thread 연결 풀** (`threading.local`) |
| 메인 연결 | `__init__`에서 1개 생성 |
| 워커 연결 | 필요 시 자동 생성 (`get_connection`) |
| 체크 | `SELECT 1`로 연결 유효성 확인, 실패 시 재연결 |
| DDL | `SUPABASE_DIRECT_URL` 있으면 별도 연결로 DDL 실행 |
| autocommit | `False` (명시적 commit/rollback) |

### 10.8 CORS 설정

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

### 10.9 UI Metrics (FR-034)

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
