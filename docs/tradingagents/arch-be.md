# Backend Design Doc: TradingAgents Features (FR-013~033)

> Created: 2026-02-11
> Updated: 2026-02-13
> Service: tradingagents
> Type: Backend
> Requirements document: docs/tradingagents/spec.md

## 0. Summary

### Goal

기존 TradingAgents 멀티에이전트 분석 파이프라인에 **영속 메모리(Hybrid RAG)**, **가상 매매 검증**, **스케줄 기반 자동화**를 추가하고, **SQLite 기반 데이터 저장**, **반성 집중화(반성에이전트 1곳)**, **요약에이전트**를 도입하여, AI 분석의 정확도를 정량적으로 추적·학습하는 자기 개선 시스템으로 진화시킨다.

### Non-goals

- 실제 증권사 API 연동 (가상 매매만)
- ~~웹 UI/대시보드 (CLI 기반 유지)~~ → **웹 API 제공 (FR-025)**
- 멀티유저/멀티전략 지원 (단일 사용자)
- 실시간 데이터 스트리밍 (분석 시점 1회성 fetch 유지)
- 에이전트 진행현황 영속화 (실시간 스트리밍만, report에는 최종 결과만 저장)

### Success metrics

- 메모리 영속성: 프로세스 재시작 후 SQLite + ChromaDB 100% 복원
- 가상 매매: positions/trades 테이블에 완전한 매매 이력 기록
- 학습 효과: has_memory=true vs false 분석 결과 비교 가능
- 스케줄: 지정 주기대로 자동 분석 실행, 1시간 이내 완료
- 반성 품질: 청산 포지션마다 전 사이클 기반 반성문 생성

---

## 1. Scope

### In scope

- FR-015: Hybrid RAG Memory (FTS5 + Vector, chromadb 내장 ONNX 임베딩)
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
- **FR-030: SQLite 전환 — 파일 기반 저장 전면 폐기, 6테이블 + FTS5**
- **FR-031: 반성 집중화 — 반성에이전트 1곳, 청산 시에만**
- **FR-032: 요약에이전트 — 13개 개별 요약 컬럼**
- **FR-033: BM25 엔진 교체 — rank_bm25 → SQLite FTS5**

### Out of scope

- Pydantic 기반 설정 마이그레이션 (기존 dict 유지)
- 멀티스레드 병렬 분석 (순차 실행 유지)
- Event Sourcing / CQRS 패턴 (단일 트랜잭션 모델)
- 기존 파일 → SQLite 데이터 마이그레이션 (기존 데이터 없음)

---

## 1.5. Tech Stack

```yaml
tech_stack:
  project_structure: "Monolith"
  be_path: "./"
  run_command: "uv run python main.py"
  language: "Python 3.10+"
  framework: "LangGraph (langgraph>=0.4.8)"
  database: "SQLite (trading.db) — stdlib sqlite3"
  orm: "None (Raw SQL via sqlite3)"
  package_manager: "uv"
  third_party:
    - "chromadb (Vector Store + Built-in ONNX Embedding)"
    - "apscheduler (Job Scheduling)"
    - "yfinance (Market Data)"
    - "langchain-core (LLM Abstraction)"
    - "fastapi (Web API Framework)"
    - "uvicorn (ASGI Server)"
  infra: "Local / WSL2 Ubuntu 22.04"
```

> `rank-bm25` 제거됨 — SQLite FTS5 내장으로 교체 (FR-033)
> `sqlite3`는 Python 표준 라이브러리, 별도 설치 불필요

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

  # NEW — Logging
  - name: "python-json-logger"
    version: ">=3.3.0"
    purpose: "JSON 구조화 로깅 포매터"
    status: "approved"

  # REMOVED
  # - rank-bm25: SQLite FTS5로 교체 (FR-033)
```

---

## 2. Architecture Impact

### Components

| Service / Module | Responsibility | Change type |
|---|---|---|
| `tradingagents/storage/` | SQLite DB 연결, Repository 패턴 CRUD | **new** (FR-030) |
| `tradingagents/agents/summary_agent.py` | 12에이전트 raw → 13개 요약 컬럼 생성 | **new** (FR-032) |
| `tradingagents/memory/` | Hybrid RAG (FTS5 + ChromaDB), RRF | modify (FR-033) |
| `tradingagents/graph/reflection.py` | 반성 집중화: 5개 → 1개 메서드 | modify (FR-031) |
| `tradingagents/graph/trading_graph.py` | DB 연동, 구조화 반성, 트랜잭션 | modify |
| `tradingagents/virtual_trade/trade_manager.py` | DB 기반 매매 관리 (파일 I/O 제거) | modify (FR-030) |
| `tradingagents/virtual_trade/portfolio_agent.py` | PA 프롬프트 강화, HybridMemory 연결 | modify (FR-022) |
| `tradingagents/scheduler/ticker_scheduler.py` | DB 기반 스케줄 + 사이클 관리 | modify (FR-030) |
| `tradingagents/graph/propagation.py` | current_position 제거 | modify |
| `tradingagents/agents/utils/agent_states.py` | current_position 필드 제거 | modify |
| `tradingagents/api/` | FastAPI 웹 백엔드 — REST + WS + auth + UI metrics | **new** (FR-025, FR-034) |
| `tradingagents/default_config.py` | DB 경로, 스케줄러 설정 추가 | modify |
| `pyproject.toml` | chromadb, apscheduler, fastapi, uvicorn | modify |
| ~~`tradingagents/virtual_trade/report_store.py`~~ | ~~JSON array append~~ | **삭제** (FR-032로 대체) |

### Data

#### SQLite Schema (`trading.db`) — FR-030

> 전체 DDL은 `docs/proposal_v3.md` §데이터베이스 스키마 참조

```sql
-- ① schedules: 분석 실행 단위
CREATE TABLE schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    interval_days   INTEGER NOT NULL DEFAULT 4,
    scheduled_cycle INTEGER NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending/running/done/failed
    error_message   TEXT,                                 -- 실패 시 에러 메시지, 성공 시 NULL
    created_at      TEXT    NOT NULL
);
CREATE INDEX idx_schedules_ticker ON schedules(ticker);

-- ② positions: 매매 사이클 (진입 → 청산)
CREATE TABLE positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',  -- active/closed
    shares      INTEGER NOT NULL DEFAULT 0,
    avg_cost    REAL,
    return_pct  REAL,
    opened_at   TEXT    NOT NULL,
    closed_at   TEXT,
    created_at  TEXT    NOT NULL
);
CREATE INDEX idx_positions_ticker_status ON positions(ticker, status);

-- ③ reports: 에이전트별 요약 (스케줄마다 1건) — FR-032
CREATE TABLE reports (
    id                                INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id                       INTEGER NOT NULL REFERENCES schedules(id),
    position_id                       INTEGER REFERENCES positions(id),
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
    pa_opinion                        TEXT,
    created_at                        TEXT    NOT NULL
);

-- ④ trades: 개별 BUY/SELL 액션
CREATE TABLE trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL REFERENCES positions(id),
    report_id   INTEGER NOT NULL REFERENCES reports(id),
    action      TEXT    NOT NULL,  -- 'BUY' | 'SELL'
    shares      INTEGER NOT NULL,
    price       REAL    NOT NULL,
    executed_at TEXT    NOT NULL
);

-- ⑤ reflections: 청산 시 반성에이전트 산출물 — FR-031
CREATE TABLE reflections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL REFERENCES positions(id),
    reflection  TEXT    NOT NULL,
    key_lessons TEXT,
    outcome     TEXT,      -- 'win' | 'loss'
    return_pct  REAL,
    market      TEXT,
    sector      TEXT,
    industry    TEXT,
    created_at  TEXT    NOT NULL
);

-- ⑥ schedule_jobs: 에러/재시도 이력
CREATE TABLE schedule_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id   INTEGER NOT NULL REFERENCES schedules(id),
    error_type    TEXT    NOT NULL,
    error_message TEXT    NOT NULL,
    error_detail  TEXT,
    created_at    TEXT    NOT NULL
);
CREATE INDEX idx_schedule_jobs_schedule ON schedule_jobs(schedule_id);

-- ⑦ FTS5: BM25 검색용 가상 테이블 — FR-033
CREATE VIRTUAL TABLE reflections_fts USING fts5(
    reflection, key_lessons,
    content='reflections', content_rowid='id'
);

-- FTS 자동 동기화 트리거
CREATE TRIGGER reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, reflection, key_lessons)
    VALUES (new.id, new.reflection, new.key_lessons);
END;
```

> 제외 컬럼: `sentiment_report` (시의성), `news_report` (bull/bear 논거에 반영)
> 각 요약 컬럼 목표: 200~400 토큰. 13개 합계: ~3,000 토큰/사이클

#### 테이블 관계

```
schedules 1──1 reports N──1 positions 1──N trades
                │                        │
                └── report_id ←──────── trades
                                positions 1──0..1 reflections
```

#### 폐기 대상 (FR-030)

| 기존 | 대체 |
|------|------|
| `eval_results/` 로그 저장 | SQLite `reports` 테이블 |
| `memory/experience/{agent}.jsonl` (5개) | SQLite `reflections` + FTS5 |
| `memory/experience/chroma/{agent}/` (5개) | ChromaDB 단일 컬렉션 |
| `memory/trade/{TICKER}/trade.json` | SQLite `positions` + `trades` |
| `memory/trade/{TICKER}/report.json` | SQLite `reports` |
| `memory/archive/{TICKER}/{n}/` | `positions.status = 'closed'` |
| `rank_bm25` 라이브러리 | SQLite FTS5 |

#### Directory Structure (Runtime)

```
memory/
├── trading.db          ← SQLite (전체 데이터)
└── chroma/             ← ChromaDB vector index (벡터 검색 전용)
```

---

## 3. Code Mapping

### Phase 1: 구현 완료 (FR-013~020)

> 아래 항목들은 파일 기반으로 구현 완료됨. FR-030 전환 시 DB 기반으로 리팩터링 필요한 항목은 별도 표기.

| # | Spec Ref | Feature | File | Class | Method | Impl | Note |
|---|----------|---------|------|-------|--------|------|------|
| 1 | FR-015 | HybridMemory 모듈 | `memory/__init__.py` | — | — | [x] | |
| 2 | FR-015 | HybridMemory 클래스 | `memory/hybrid_memory.py` | `HybridMemory` | `__init__`, `add_situations`, `get_memories`, `_rrf_fusion` | [x] | **FR-033에서 FTS5로 리팩터링** |
| 3 | FR-015 | backward compat 재수출 | `agents/__init__.py` | — | — | [x] | |
| 4 | FR-015 | 메모리 교체 | `graph/trading_graph.py` | `TradingAgentsGraph` | `__init__` | [x] | |
| 5 | FR-015 | chromadb 의존성 | `pyproject.toml` | — | — | [x] | |
| 6 | FR-018 | 구조화된 반성 입력 | `graph/trading_graph.py` | `TradingAgentsGraph` | `reflect_and_remember` | [x] | **FR-031에서 단일 반성으로 변경** |
| 7 | FR-018 | Reflector 프롬프트 | `graph/reflection.py` | `Reflector` | `_reflect_on_component` | [x] | **FR-031에서 `reflect_on_position`으로 교체** |
| 8 | FR-018 | 메타데이터 저장 | `memory/hybrid_memory.py` | `HybridMemory` | `add_situations` | [x] | **FR-033에서 DB 저장으로 변경** |
| 9 | FR-019 | Bootstrap 태깅 | `graph/trading_graph.py` | `TradingAgentsGraph` | `propagate` | [x] | |
| 10 | FR-019 | 메모리 쿼리 추적 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | [x] | |
| 11 | FR-013 | TradeManager 모듈 | `virtual_trade/__init__.py` | — | — | [x] | |
| 12 | FR-013 | TradeManager 클래스 | `virtual_trade/trade_manager.py` | `TradeManager` | CRUD 메서드 | [x] | **FR-030에서 DB 기반으로 리팩터링** |
| 13 | FR-013 | ReportStore | `virtual_trade/report_store.py` | `ReportStore` | `append`, `load` | [x] | **FR-032에서 삭제 (SummaryAgent+DB 대체)** |
| 14 | FR-014 | PortfolioAgent | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_build_prompt` | [x] | **FR-022에서 프롬프트 강화** |
| 15 | FR-016 | Scheduler 모듈 | `scheduler/__init__.py` | — | — | [x] | |
| 16 | FR-016 | TickerScheduler | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `add_ticker`, `start`, `_run_analysis_cycle` | [x] | **FR-030에서 DB 연동 변경** |
| 17 | FR-016 | apscheduler 의존성 | `pyproject.toml` | — | — | [x] | |
| 18 | FR-017 | AgentState 필드 | `agents/utils/agent_states.py` | `AgentState` | — | [x] | |
| 19 | FR-017 | Propagator 파라미터 | `graph/propagation.py` | `Propagator` | `create_initial_state` | [x] | |
| 20 | FR-017 | TradingAgentsGraph position 전달 | `graph/trading_graph.py` | `TradingAgentsGraph` | `propagate` | [x] | |
| 21 | FR-020 | TradeManager 부분 매도 | `virtual_trade/trade_manager.py` | `TradeManager` | `close_positions` | [x] | **FR-030에서 DB 기반으로 변경** |
| 22 | FR-020 | PA 매도 수량 전략 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_parse_decision` | [x] | |
| 23 | FR-020 | Scheduler 부분 매도 분기 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | [x] | |
| 24 | ALL | DEFAULT_CONFIG 확장 | `default_config.py` | — | — | [x] | **FR-030에서 DB 경로 변경** |

### Phase 2: 신규 구현 (FR-021~033)

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 25 | FR-030 | Storage 모듈 init | `storage/__init__.py` [NEW] | — | — | 새 모듈 생성 | [x] |
| 26 | FR-030 | Database 연결 관리 | `storage/database.py` [NEW] | `Database` | `__init__`, `init_schema`, `get_connection`, `close` | SQLite 연결 + WAL 모드 + schema 초기화 | [x] |
| 27 | FR-030 | ScheduleRepository | `storage/schedule_repo.py` [NEW] | `ScheduleRepository` | `create`, `update_status`, `get_by_ticker`, `get_latest_cycle` | schedules CRUD | [x] |
| 28 | FR-030 | PositionRepository | `storage/position_repo.py` [NEW] | `PositionRepository` | `create`, `get_active`, `update_shares`, `close_position`, `get_by_id` | positions CRUD + status 전환 | [x] |
| 29 | FR-030 | ReportRepository | `storage/report_repo.py` [NEW] | `ReportRepository` | `create`, `get_by_position`, `get_by_schedule` | reports 13컬럼 INSERT + 조회 | [x] |
| 30 | FR-030 | TradeRepository | `storage/trade_repo.py` [NEW] | `TradeRepository` | `create`, `get_by_position`, `get_history` | trades CRUD | [x] |
| 31 | FR-030 | ReflectionRepository | `storage/reflection_repo.py` [NEW] | `ReflectionRepository` | `create`, `get_by_position`, `search_fts` | reflections + FTS5 검색 | [x] |
| 32 | FR-031 | 반성 집중화 | `graph/reflection.py` | `Reflector` | `reflect_on_position` | 5개 `reflect_on_*` 제거 → 1개 메서드. DB에서 reports+trades 조회 → 반성문 작성 | [x] |
| 33 | FR-031 | reflect_and_remember 변경 | `graph/trading_graph.py` | `TradingAgentsGraph` | `reflect_and_remember` | 5개 에이전트별 반성 → Reflector.reflect_on_position(position_id) 1회 호출 | [x] |
| 34 | FR-032 | 요약에이전트 | `agents/summary_agent.py` [NEW] | `SummaryAgent` | `__init__`, `summarize` | 12에이전트 raw + PA 의견 → 13개 요약 생성. quick_think_llm 사용 | [x] |
| 35 | FR-033 | FTS5 BM25 교체 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories`, `add_situations` | rank_bm25 제거, FTS5 쿼리로 교체. JSONL _load/_save 제거 | [x] |
| 36 | FR-021 | 12에이전트 포지션 주입 제거 | `agents/utils/agent_states.py`, `graph/propagation.py`, `graph/trading_graph.py` | `AgentState`, `Propagator`, `TradingAgentsGraph` | `create_initial_state`, `propagate` | current_position state 필드 제거, 12에이전트 객관적 분석 보장 | [x] |
| 37 | FR-022 | PA 프롬프트 강화 + 메모리 연결 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `decide`, `_build_prompt` | 분석(6):경험(4) 가중치, 디바이어싱, HybridMemory 검색 | [x] |
| 38 | FR-029 | 메타데이터 태깅 | `graph/trading_graph.py` | `TradingAgentsGraph` | `reflect_and_remember` | outcome/market/sector/industry 자동 추가. yf.Ticker.info fetch | [x] |
| 39 | FR-029 | RAG 결과 레이블 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | 결과에 `[✅ 성공 사례]`/`[⚠️ 실패 사례]` 레이블 부착 | [x] |
| 40 | FR-025 | FastAPI 앱 | `api/app.py` [NEW] | — | `create_app` | FastAPI 앱, CORS, lifespan에서 APScheduler+큐워커 시작 | [x] |
| 41 | FR-025 | API 라우트 | `api/routes.py` [NEW] | — | REST 엔드포인트 | GET/POST/DELETE /schedules, GET /positions, GET /positions/market, GET /metrics, GET /queue, GET /health, GET /search, GET /reports, GET /reflections, GET /activity | [x] |
| 42 | FR-025 | WebSocket | `api/ws.py` [NEW] | — | `analyze_ws` | WS /ws/analyze/{ticker}: 에이전트 상태 실시간 스트리밍 | [x] |
| 43 | FR-026 | 인증 미들웨어 | `api/auth.py` [NEW] | — | `check_admin_token` | Bearer {ADMIN_TOKEN} 검증 | [x] |
| 44 | FR-030 | TradeManager DB 리팩터링 | `virtual_trade/trade_manager.py` | `TradeManager` | 전체 | JSON I/O → PositionRepository + TradeRepository 사용 | [x] |
| 45 | FR-030 | Scheduler DB 연동 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl` | 파일 → DB 전체 전환. 트랜잭션 패턴 적용 | [x] |
| 46 | FR-030 | Config DB 경로 | `default_config.py` | — | — | `memory_dir`→`database_path`, `virtual_trade_dir` 제거 | [x] |
| 47 | FR-030 | report_store.py 삭제 | `virtual_trade/report_store.py` | — | — | 파일 삭제 (SummaryAgent + DB로 대체) | [x] |

> **경로 접두사**: 모든 파일 경로는 `tradingagents/` 하위
> **Impl**: `[ ]` = 미구현, `[x]` = 구현 완료

---

## 4. Implementation Plan

### 📂 Required Reference Files

| File | Reference Purpose |
|------|------------------|
| `tradingagents/graph/trading_graph.py` | 메모리 초기화, propagate(), reflect_and_remember() 패턴 |
| `tradingagents/graph/reflection.py` | Reflector 프롬프트 구조, 5개 reflect 메서드 → 1개로 변경 |
| `tradingagents/memory/hybrid_memory.py` | 기존 BM25+ChromaDB → FTS5로 전환 대상 |
| `tradingagents/virtual_trade/trade_manager.py` | JSON I/O → DB 전환 대상 |
| `tradingagents/virtual_trade/portfolio_agent.py` | PA 프롬프트 강화 대상 |
| `tradingagents/scheduler/ticker_scheduler.py` | 파일 → DB 전환 대상, 트랜잭션 패턴 적용 |
| `docs/proposal_v3.md` | 전체 설계 결정 + DB 스키마 참조 |

### Step-by-Step Implementation

1. **Step 1: Database Layer (FR-030)**
   - `storage/__init__.py` 생성
   - `storage/database.py`: SQLite 연결, WAL 모드 활성화, `init_schema()` (전체 CREATE TABLE 실행)
   - 5개 Repository 클래스: `schedule_repo.py`, `position_repo.py`, `report_repo.py`, `trade_repo.py`, `reflection_repo.py`
   - 각 Repository는 `Database` 인스턴스를 주입받아 raw SQL 실행

2. **Step 2: HybridMemory FTS5 전환 (FR-033)**
   - `rank_bm25` import 제거, JSONL `_load_corpus` / `_save_entry` 제거
   - BM25 경로: `ReflectionRepository.search_fts(query)` 호출로 대체
   - Vector 경로: ChromaDB 유지 (단일 컬렉션, 에이전트별 분리 제거)
   - RRF 합산 로직 유지
   - `pyproject.toml`에서 `rank-bm25` 제거

3. **Step 3: 요약에이전트 (FR-032)**
   - `agents/summary_agent.py` [NEW]: `SummaryAgent` 클래스
   - `quick_think_llm`으로 12개 raw 산출물 + PA 의견 → 13개 요약 생성
   - 반환: dict (13개 컬럼명: 요약 텍스트)
   - 각 요약 200~400 토큰 목표

4. **Step 4: 반성 집중화 (FR-031)**
   - `reflection.py`: 5개 `reflect_on_bull`, `reflect_on_bear` 등 제거
   - 새 메서드 `reflect_on_position(position_id, db)`:
     - DB에서 해당 position의 reports + trades 전체 조회
     - 전 사이클 데이터를 LLM에 전달 → 반성문 + 핵심 교훈 생성
   - `trading_graph.py`: `reflect_and_remember()` 에서 Reflector 1회 호출로 변경

5. **Step 5: TradeManager DB 리팩터링 (FR-030)**
   - JSON CRUD 제거 (`load`, `save`, tmp+rename 등)
   - `PositionRepository` + `TradeRepository` 사용으로 전환
   - `close_positions()`: DB에서 position 조회 → trade INSERT → position UPDATE
   - `report_store.py` 삭제

6. **Step 6: 분석 사이클 트랜잭션 (FR-030)**
   - `ticker_scheduler.py`의 `_run_analysis_cycle_impl` 리팩터링:
     ```
     1. G-ANT 분석 (LLM) → final_state
     2. PA 판단 (LLM) → trade_decision
     3. SummaryAgent (LLM) → 13 summaries
     4. (청산 시) Reflector (LLM) → reflection
     ── BEGIN TRANSACTION ──
     5. schedule INSERT (done)
     6. trade INSERT
     7. report INSERT
     8. (청산 시) reflection INSERT + position UPDATE 'closed'
     ── COMMIT ──
     ```

7. **Step 7: 분석 객관성 + PA 강화 (FR-021, FR-022, FR-029)**
   - 12에이전트 포지션 주입 제거
   - PA 프롬프트: 분석(6):경험(4) 가중치, 디바이어싱
   - 메타데이터 태깅: outcome/market/sector/industry
   - RAG 결과 레이블: `[✅ 성공]` / `[⚠️ 실패]`

8. **Step 8: 웹 API (FR-025~026)**
   - DB 기반 라우트 (Repository 직접 호출)
   - WebSocket: 기존 broadcast 패턴 유지
   - Bearer 인증: 기존 설계 유지

9. **Step 9: Config + 정리**
   - `default_config.py`: `database_path: memory/trading.db`, 파일 경로 설정 제거
   - `pyproject.toml`: `rank-bm25` 제거 확인
   - 불필요한 파일 삭제 (`report_store.py`, JSONL 관련 코드)

---

## 5. Sequence Diagrams

### 5.1 Full Analysis Cycle (1 Schedule Execution)

```
┌─ 스케줄 트리거 ──────────────────────────────────────────────────────────┐
│                                                                            │
│  ScheduleRepository.create(ticker, cycle)                                  │
│  ScheduleRepository.update_status('running')                               │
│                                                                            │
│  1. G-ANT 분석 (12에이전트 파이프라인, 기존 그대로)                       │
│     Market → Social → News → Fundamentals                                  │
│     → Bull ↔ Bear (N rounds) → Research Judge                             │
│     → Trader → Aggressive ↔ Conservative ↔ Neutral → Risk Judge           │
│     → Signal: BUY/HOLD/SELL + 전략                                        │
│     ※ 12에이전트는 포지션 정보 없이 완전 객관적 분석 (FR-021)            │
│                                                                            │
│  2. PA 판단 (deep_think_llm)                                              │
│     ← final_state 읽기                                                     │
│     ← PositionRepository.get_active(ticker) → current position            │
│     ← TradeRepository.get_by_position(pos_id) → trade history             │
│     ← HybridMemory.get_memories(query) → RAG 검색 (있을 때만)            │
│     → pa_opinion 작성 + 매매 결정 (trade_decision)                        │
│                                                                            │
│  3. SummaryAgent.summarize(final_state, pa_opinion)                        │
│     → 13개 요약 dict 생성 (sentiment/news 제외, quick_think_llm)          │
│                                                                            │
│  4. 청산 확인 (shares == 0 after trade?)                                   │
│     ├─ NO  → skip                                                          │
│     └─ YES → Reflector.reflect_on_position(position_id, db)               │
│              ← ReportRepository.get_by_position(pos_id) → 전 사이클 요약  │
│              ← TradeRepository.get_by_position(pos_id) → 전체 매매 이력   │
│              → reflection, key_lessons, outcome 생성                       │
│                                                                            │
│  ═══ BEGIN TRANSACTION ═══                                                  │
│  5. ScheduleRepository.update_status('done')                               │
│  6. TradeRepository.create(...) (매매가 있을 때만)                         │
│  7. ReportRepository.create(schedule_id, position_id, 13 summaries)        │
│  8. (청산 시) ReflectionRepository.create(pos_id, reflection, ...)         │
│     + HybridMemory.add_situations(reflection) → ChromaDB 벡터 저장        │
│     + PositionRepository.close_position(pos_id, return_pct)                │
│  ═══ COMMIT ═══                                                            │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

> **트랜잭션 전략**: LLM 호출(1~4)은 트랜잭션 밖에서 실행. DB 쓰기(5~8)만 하나의 트랜잭션으로 묶어 원자성 보장 + SQLite 락 최소화.
> **ChromaDB**: 트랜잭션 밖에서 별도 저장 (ChromaDB는 SQLite 트랜잭션과 무관). 실패 시 로그만 남기고 진행.

### 5.2 Hybrid RAG Search (PA Memory Read)

```
PA: "반도체 대형주 모멘텀 진입 경험?"
         │
    ┌────┴────┐
    ▼         ▼
 ChromaDB    SQLite FTS5
 (벡터)      (BM25)
    │         │
    │   ReflectionRepository.search_fts(query)
    │   → MATCH 'reflections_fts' → BM25 rank
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
Reflector.reflect_on_position(position_id, db)
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
 SQLite               ChromaDB
 reflections INSERT   벡터 임베딩 저장
 + FTS5 자동 동기화   (내장 ONNX)
```

---

## 6. API Specification

### 6.1 Storage Layer (FR-030)

#### `Database` (`storage/database.py`)

```python
class Database:
    """SQLite 연결 관리 + 스키마 초기화"""
    def __init__(self, db_path: str = "memory/trading.db"):
        """WAL 모드 활성화, foreign_keys pragma ON"""
    def init_schema(self) -> None:
        """6 테이블 + FTS5 + 트리거 생성 (IF NOT EXISTS)"""
    def get_connection(self) -> sqlite3.Connection:
        """현재 연결 반환"""
    def execute_in_transaction(self, operations: Callable) -> None:
        """operations(conn)을 하나의 트랜잭션으로 실행"""
    def close(self) -> None:
        """연결 종료"""
```

#### `ScheduleRepository` (`storage/schedule_repo.py`)

```python
class ScheduleRepository:
    def __init__(self, db: Database): ...
    def create(self, ticker: str, cycle: int) -> int: ...
    def update_status(self, schedule_id: int, status: str,
                      error_message: str | None = None) -> None: ...
    def get_by_ticker(self, ticker: str) -> list[dict]: ...
    def get_latest_cycle(self, ticker: str) -> int: ...
    def get_by_status(self, statuses: list[str]) -> list[dict]:
        """서버 재시작 시 pending/running 스케줄 복구용 (10.3)"""
```

#### `PositionRepository` (`storage/position_repo.py`)

```python
class PositionRepository:
    def __init__(self, db: Database): ...
    def create(self, ticker: str) -> int: ...
    def get_active(self, ticker: str) -> dict | None: ...
    def get_by_id(self, position_id: int) -> dict | None: ...
    def update_shares(self, position_id: int, shares: int, avg_cost: float) -> None: ...
    def close_position(self, position_id: int, return_pct: float) -> None:
        """status='closed', return_pct, closed_at 기록"""
```

#### `ReportRepository` (`storage/report_repo.py`)

```python
class ReportRepository:
    def __init__(self, db: Database): ...
    def create(self, schedule_id: int, position_id: int | None, summaries: dict) -> int:
        """summaries: 13개 컬럼명→텍스트 dict. INSERT 1건"""
    def get_by_position(self, position_id: int) -> list[dict]: ...
    def get_by_schedule(self, schedule_id: int) -> dict | None: ...
```

#### `TradeRepository` (`storage/trade_repo.py`)

```python
class TradeRepository:
    def __init__(self, db: Database): ...
    def create(self, position_id: int, report_id: int, action: str,
               shares: int, price: float) -> int: ...
    def get_by_position(self, position_id: int) -> list[dict]: ...
    def get_history(self, ticker: str, limit: int = 50) -> list[dict]: ...
```

#### `ReflectionRepository` (`storage/reflection_repo.py`)

```python
class ReflectionRepository:
    def __init__(self, db: Database): ...
    def create(self, position_id: int, reflection: str,
               key_lessons: str, outcome: str, return_pct: float) -> int:
        """INSERT + FTS5 자동 동기화 (트리거)"""
    def get_by_position(self, position_id: int) -> dict | None: ...
    def search_fts(self, query: str, limit: int = 5) -> list[dict]:
        """FTS5 BM25 검색. MATCH query → rank 정렬"""
```

### 6.2 SummaryAgent (FR-032)

```python
class SummaryAgent:
    """12에이전트 raw + PA 의견 → 13개 개별 요약 생성"""
    SUMMARY_COLUMNS = [
        "market_report", "fundamentals_report",
        "bull_history", "bear_history", "investment_debate_judge_decision",
        "aggressive_history", "conservative_history", "neutral_history",
        "trader_investment_judge_decision", "trader_investment_decision",
        "investment_plan", "final_trade_decision", "pa_opinion"
    ]
    # 제외: sentiment_report (시의성), news_report (bull/bear에 반영)

    def __init__(self, llm):
        """quick_think_llm 사용"""
    def summarize(self, final_state: dict, pa_opinion: str) -> dict:
        """Returns: {column_name: summary_text} (13개)
        각 요약 목표: 200~400 토큰"""
```

### 6.3 Reflector (FR-031 수정)

```python
class Reflector:
    """기존: 5개 reflect_on_* → 변경: 1개 reflect_on_position"""
    def __init__(self, llm):
        """deep_think_llm 사용"""

    # 삭제 예정 (FR-031):
    # - reflect_on_bull(), reflect_on_bear()
    # - reflect_on_aggressive(), reflect_on_conservative(), reflect_on_neutral()
    # - _reflect_on_component()

    def reflect_on_position(self, position_id: int, db: Database) -> dict:
        """
        1. ReportRepository.get_by_position(position_id) → 전 사이클 요약
        2. TradeRepository.get_by_position(position_id) → 매매 이력
        3. PositionRepository.get_by_id(position_id) → 메타 (수익률, 기간)
        4. LLM 호출 → 반성문 생성
        Returns: {reflection, key_lessons, outcome, return_pct}
        """
```

### 6.4 HybridMemory (FR-033 수정)

```python
class HybridMemory:
    """기존: JSONL+rank_bm25 → 변경: FTS5+ChromaDB"""
    def __init__(self, db: Database, chroma_path: str):
        """
        - db: SQLite 연결 (FTS5 BM25 검색용)
        - ChromaDB PersistentClient 초기화
        - rank_bm25 import 제거, JSONL 관련 코드 제거
        """

    def add_situations(self, reflection: str, key_lessons: str,
                       metadata: dict) -> None:
        """
        반성에이전트 전용 (WRITE).
        1. ReflectionRepository.create() → SQLite + FTS5
        2. ChromaDB collection.add() → 벡터 임베딩
        """

    def get_memories(self, query: str, top_k: int = 5,
                     ticker: str | None = None) -> list[dict]:
        """
        PA 전용 (READ). Hybrid RAG 검색.
        1. ChromaDB → 벡터 유사도 Top-K
        2. ReflectionRepository.search_fts(query) → BM25 Top-K
        3. RRF 합산 → 최종 Top-K
        4. 레이블 부착: [✅ 성공] / [⚠️ 실패] (FR-029)
        """
```

### 6.5 Web API (FR-025~026)

#### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | — | 헬스체크 |
| GET | `/schedules` | — | 등록된 스케줄 목록 |
| POST | `/schedules` | Bearer | 새 스케줄 등록 |
| DELETE | `/schedules/{ticker}` | Bearer | 스케줄 삭제 |
| GET | `/schedules/{ticker}/cycles` | — | 특정 티커 분석 이력 |
| GET | `/positions` | — | 포지션 목록 (active/closed 필터) |
| GET | `/positions/{id}` | — | 포지션 상세 (trades + reports 포함) |
| GET | `/reflections` | — | 반성문 목록 |
| GET | `/search` | — | Hybrid RAG 검색 (query param) |
| GET | `/positions/market` | — | 포지션 + 현재가 + PnL (FR-034) |
| GET | `/metrics` | — | 대시보드 지표 (총 PnL, 수익률 등) |
| GET | `/reports` | — | 보고서 목록 (ticker/position_id 필터) |
| GET | `/queue` | — | 현재 분석 큐 상태 |
| GET | `/activity` | — | 최근 활동 피드 (trades + reports) |
| POST | `/schedules/{ticker}/retry` | Bearer | 실패 스케줄 재시도 (10.4) |

#### WebSocket

| Path | Description |
|------|-------------|
| `WS /ws/analyze/{ticker}` | 에이전트 상태 실시간 스트리밍 (기존 broadcast 패턴) |

#### Authentication (FR-026)

```
READ 엔드포인트: 인증 없이 공개 접근
WRITE 엔드포인트 (POST, DELETE): Authorization: Bearer {ADMIN_TOKEN}
ADMIN_TOKEN: 환경변수 TRADINGAGENTS_ADMIN_TOKEN (미설정 시 서버 시작 차단)
```

---

## 7. Configuration

### DEFAULT_CONFIG 변경사항

```python
DEFAULT_CONFIG = {
    # 기존 유지
    "project_dir": os.path.abspath("."),
    "llm_provider": "gemini-cli",
    # ...

    # FR-030: DB 경로 (파일 경로 설정 대체)
    "database_path": "memory/trading.db",     # SQLite
    "chroma_path": "memory/chroma",           # ChromaDB

    # FR-016: 스케줄러
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": False,

    # FR-025: API
    "api_host": "0.0.0.0",
    "api_port": 8000,
}
```

---

## 8. Risks & Tradeoffs

### 설계 결정 근거

| 결정 | 선택 | 대안 (기각) | 근거 |
|------|------|------------|------|
| DB 접근 패턴 | Repository 패턴 (테이블별 클래스) | 단일 Database 래퍼 | SRP, 테스트 용이성, 향후 확장 |
| SQL 레이어 | Raw SQL (sqlite3) | SQLAlchemy Core | 의존성 제로, 쿼리 단순 (<10 테이블) |
| 반성 구조 | PA 1곳 집중 | 5에이전트 개별 반성 | LLM 호출 5→1, 데이터 오염↓, 비용↓ |
| BM25 엔진 | SQLite FTS5 | rank_bm25 + JSONL | 의존성↓, 인덱스 자동관리, 동기화 보장 |
| 트랜잭션 범위 | DB 쓰기만 묶음 (LLM 밖) | 전체 사이클 묶음 | SQLite 락 최소화 (ms급), API 동시 읽기 보장 |
| 마이그레이션 | Clean break (기존 데이터 없음) | 파일→DB 변환 스크립트 | 기존 운영 데이터 없음 |
| 리포트 저장 | 13개 개별 컬럼 | 단일 JSON blob | 컬럼별 조회, FTS 검색, 구조 보장 |
| ChromaDB 저장 | 트랜잭션 밖 별도 저장 | 트랜잭션 내 포함 | ChromaDB는 SQLite와 별도 엔진, 원자성 불가 |

### 리스크

| 리스크 | 영향 | 완화 |
|--------|------|------|
| SQLite 동시 쓰기 제한 | 분석 중 API 쓰기 대기 | WAL 모드 + 순차 실행 (max_workers=1), API는 READ 위주 |
| ChromaDB 벡터 비동기 | 반성 저장 후 즉시 검색 불가 | 반성 직후 동일 사이클에서 RAG 읽기 없음 (다음 사이클부터) |
| FTS5 한국어 토크나이저 부재 | 한글 검색 품질 저하 | key_lessons를 영어/혼합으로 작성 유도 + 벡터 검색이 보완 |
| 요약 품질 편차 | quick_think_llm 성능 한계 | 각 컬럼 200~400 토큰 목표 명시, 프롬프트 엔지니어링 |
| 단일 DB 파일 손상 | 전체 데이터 유실 | WAL 모드 corruption 방어 + 주기적 `.backup` API 또는 수동 복사 |

### 가정사항

- 단일 사용자, 순차 실행 → SQLite write lock 충돌 없음
- 분석 사이클당 ~1시간, DB 쓰기는 사이클 말미 수 ms
- 반성 데이터는 청산 시에만 생성 → 점진적 축적 (급격한 증가 없음)
- ChromaDB 내장 임베딩 (`all-MiniLM-L6-v2`) 품질이 본 용도에 충분

---

## 9. Error / Auth / Data Checklist

### Error Cases

| # | Category | Error | Handling |
|---|----------|-------|----------|
| 1 | SQLite | `sqlite3.OperationalError: database is locked` | WAL 모드 + busy_timeout(5000ms). max_workers=1로 근본 방지 |
| 2 | SQLite | `sqlite3.OperationalError: disk I/O error` | 로그 남기고 스케줄 status='failed'. 사용자에게 디스크 확인 안내 |
| 3 | SQLite | DB 파일 손상 | 앱 시작 시 `PRAGMA integrity_check` 실행. 실패 시 시작 차단 + 에러 메시지 |
| 4 | SQLite | Schema migration 불일치 | `init_schema()`에서 IF NOT EXISTS. 향후 버전 관리 필요 시 migration 테이블 추가 |
| 5 | ChromaDB | 벡터 저장 실패 | 로그 남기고 계속 진행 (SQLite 반성은 이미 저장됨). 검색 시 벡터 없으면 FTS5만 사용 |
| 6 | LLM | 요약에이전트 실패 | 13개 중 실패한 요약 = NULL 저장. 반성에이전트에는 available 컬럼만 사용 |
| 7 | LLM | 반성에이전트 실패 | 반성 없이 position status='closed'. 다음 기회에 학습 불가 (데이터 유실 아님) |
| 8 | Network | 데이터 벤더 fetch 실패 | 30s 간격 2회 재시도 후 다음 벤더 fallback, schedule_jobs 기록 |
| 9 | Auth | ADMIN_TOKEN 미설정 | 서버 시작 차단 (`raise RuntimeError`) |
| 10 | Auth | 잘못된 Bearer 토큰 | 401 Unauthorized |
| 11 | Auth | READ 엔드포인트 접근 | 인증 불필요 (공개) |
| 12 | LLM | Decision parse 실패 | 스케줄 실패 처리 + 재큐잉, schedule_jobs 기록 |
| 13 | LLM | Agent execution 실패 | 스케줄 실패 처리 + 재큐잉, schedule_jobs 기록 |
| 12 | Scheduler | 중복 스케줄 등록 | ticker 기준 중복 체크. 409 Conflict |
| 13 | Transaction | 부분 실패 | 전체 롤백. schedule status='failed'. 로그에 실패 지점 기록 |

### Data Integrity Rules

| Rule | Enforcement |
|------|-------------|
| schedule 1:1 report | FK + UNIQUE constraint 또는 application-level check |
| position 1:0..1 reflection | FK + application-level check (청산 시에만) |
| trade는 반드시 position+report 참조 | FK constraints (NOT NULL) |
| FTS5 ↔ reflections 동기화 | AFTER INSERT 트리거 (DDL 수준 보장) |
| position.shares ≥ 0 | application-level CHECK (매도 시 잔량 초과 방지) |
| ISO 8601 timestamps | application-level formatting. SQLite TEXT 타입 |

---

## 10. Additional Design Details (from Review)

> 아래 항목은 设계 검증(check) 단계에서 갭 분석을 통해 추가된 세부사항이다.

### 10.1 REST API 페이지네이션

| 항목 | 값 |
|------|-----|
| 방식 | **혼합**: `/schedules`는 offset 기반, 나머지는 id cursor 기반 |
| 기본 limit | 모바일: 5건, PC: 10건 |
| 최대 limit | 100건 |
| 파라미터 | `/schedules`: `?cursor={offset}&limit={n}` / 나머지: `?cursor={last_id}&limit={n}` |

```python
# 예시: GET /positions?cursor=42&limit=10
@app.get("/positions")
async def list_positions(cursor: int | None = None, limit: int = 10,
                         status: str | None = None):
    """cursor = 마지막으로 받은 id. 클라이언트가 전달."""
```

> 적용 대상: `GET /schedules`(offset), `GET /positions`, `GET /reflections`, `GET /schedules/{ticker}/cycles`, `GET /reports`(id cursor)

### 10.2 POST /schedules 요청 스키마

```python
class ScheduleCreateRequest(BaseModel):
    ticker: str               # 필수. 예: "NVDA"
    interval_days: int = 4    # 선택. 기본 4일
```

> `initial_capital`는 서버에서 고정값(기본 $1,000)으로 사용하며 요청에 포함하지 않음.

### 10.8 Activity Feed

| 파라미터 | 설명 |
|----------|------|
| `?limit={n}` | 최대 결과 수 (기본 20) |
| `?since_hours={n}` | 최근 N시간 필터 (기본 24h) |
| `?ticker={TICKER}` | 특정 티커 필터 |

### 10.3 큐 영속성

- `asyncio.Queue`는 메모리 기반이지만, **schedules 테이블의 `status='pending'`/`'running'`** 으로 영속화
- 서버 재시작 시 `status IN ('pending', 'running')`인 schedule을 다시 큐에 적재
- 추가 테이블 불필요 — 기존 `schedules.status` 활용

```python
# 서버 시작 시 (lifespan)
async def recover_pending_schedules(db: Database):
    """status='pending' or 'running'인 스케줄 재큐"""
    pending = ScheduleRepository(db).get_by_status(['pending', 'running'])
    for s in pending:
        await analysis_queue.put(s)
```

> `ScheduleRepository`에 메서드 추가: `get_by_status(statuses: list[str]) -> list[dict]`

### 10.4 실패 스케줄 재시도

| 항목 | 값 |
|------|-----|
| 자동 재시도 | **없음** (LLM 토큰 비용 방지) |
| 수동 재시도 | `POST /schedules/{ticker}/retry` (Bearer 인증) |
| 동작 | schedule status → 'pending', 큐에 다시 넣기 |

```
POST /schedules/{ticker}/retry  → 200 OK {"message": "Requeued"}
                                → 404 if no failed schedule
                                → 409 if already pending/running
```

> REST Endpoints 테이블에 추가:
> | POST | `/schedules/{ticker}/retry` | Bearer | 실패 스케줄 재시도 |

### 10.5 LLM 타임아웃

| 항목 | 값 |
|------|-----|
| 전체 분석 사이클 | **1800초 (30분)** |
| 개별 LLM 호출 | 명시적 timeout 없음 (사이클 전체로 관리) |
| 타임아웃 시 | schedule status='failed', 로그에 timeout 기록 |

> 분석 타임아웃은 글로벌 타이머로 강제하지 않으며, LLM client timeout과 스케줄 재큐잉으로 복원한다.

### 10.6 LLM 응답 파싱 실패

| 단계 | 방어 |
|------|------|
| 1차 | 출력 포맷 고정 (ACTION/SHARES 등)으로 파싱 안정화 |
| 2차 | 파싱 실패 시 스케줄 실패 처리 + 재큐잉 |
| 로그 | schedule_jobs에 parse_failure 기록 + raw 응답 저장 |
| report | 파싱 실패 시 DB write 중단 (실패로 처리) |

### 10.7 WebSocket 메시지 포맷

```json
{
  "agent": "Market Analyst",   // 현재 에이전트명
  "status": "running",         // running | completed | error | waiting
  "message": "시장 분석 중...", // 사람이 읽을 수 있는 상태 메시지
  "step": 1,                    // 단계 번호 (옵션)
  "phase": "Data Collection",  // 단계 그룹명 (옵션)
  "total_steps": 13,            // 전체 단계 수 (옵션)
  "timestamp": "2026-02-13T23:30:00+09:00"
}
```

### 7.1 Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `TRADINGAGENTS_ADMIN_TOKEN` | WRITE 인증 토큰 (미설정 시 서버 시작 차단) | `dev-token-...` |
| `TRADINGAGENTS_CORS_ORIGINS` | CORS 허용 도메인 목록 (쉼표 구분) | `https://app.example.com` |

### 10.8 SQLite 연결 관리

| 항목 | 값 |
|------|-----|
| 전략 | **단일 연결** + WAL 모드 |
| 설정 | `check_same_thread=False` |
| 근거 | 단일 사용자, 순차 실행(max_workers=1), API는 READ 위주 |
| 주의 | FastAPI(async)와 분석 워커(thread) 동시 접근 가능 → WAL이 READ/WRITE 분리 |
| 향후 | 문제 발생 시 연결 2개(API read용, 워커 write용)로 분리 |

```python
class Database:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")  # 10.12
```

### 10.9 에러 응답 포맷

```json
{
  "error": {
    "code": "SCHEDULE_NOT_FOUND",
    "message": "No schedule found for ticker NVDA",
    "detail": null
  }
}
```

| HTTP Status | code | 사용 |
|-------------|------|------|
| 400 | `INVALID_REQUEST` | 잘못된 요청 파라미터 |
| 401 | `UNAUTHORIZED` | Bearer 토큰 누락/불일치 |
| 404 | `NOT_FOUND` | 리소스 없음 |
| 409 | `CONFLICT` | 중복 스케줄, 이미 실행 중 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |

### 10.10 CORS 설정

```python
# .env
# TRADINGAGENTS_CORS_ORIGINS="https://{frontend-domain}"

cors_origins = os.getenv("TRADINGAGENTS_CORS_ORIGINS", "")
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

> Cloudflare Tunnel로 **frontend/back 둘 다 공개** 시, `TRADINGAGENTS_CORS_ORIGINS`에 프론트 도메인만 지정한다.

### 10.11 DB 백업

| 항목 | 값 |
|------|-----|
| 방법 | `sqlite3.Connection.backup()` API 사용 (WAL 안전) |
| 대안 | 파일 복사 시 `trading.db` + `trading.db-wal` + `trading.db-shm` 모두 복사 |
| 자동화 | 미정 (수동 복사 또는 추후 API 엔드포인트 추가 가능) |

```python
# 안전한 백업 (WAL 모드에서도 일관성 보장)
import shutil
src = sqlite3.connect("memory/trading.db")
dst = sqlite3.connect("memory/trading_backup.db")
src.backup(dst)
dst.close()
src.close()
```

### 10.12 SQLite busy_timeout

- **값: 5000ms** (5초)
- `Database.__init__`에서 `PRAGMA busy_timeout=5000` 실행
- 10.8 연결 관리 코드에 반영됨

### 10.13 UI Metrics (FR-034)

#### 목적

- UI 대시보드용 현재가/PnL/수익률 지표를 **DB 저장 없이** on-demand 계산

#### 데이터 소스

- `positions` 테이블 (active 중심)
- 현재가: yfinance 실시간 조회 (batch 요청 권장)

#### 계산식

```
pnl = (current_price - avg_cost) * shares
return_pct = (current_price - avg_cost) / avg_cost * 100

total_unrealized_pnl = Σ pnl
total_unrealized_return_pct = total_unrealized_pnl / Σ(avg_cost * shares) * 100
```

#### GET /positions/market

```json
[
  {
    "position_id": 12,
    "ticker": "AAPL",
    "shares": 50,
    "avg_cost": 165.0,
    "current_price": 185.4,
    "pnl": 1020.0,
    "return_pct": 12.36,
    "as_of": "2026-02-14T09:30:00+09:00"
  }
]
```

#### GET /metrics

```json
{
  "as_of": "2026-02-14T09:30:00+09:00",
  "active_positions": 4,
  "closed_positions": 12,
  "wins": 8,
  "losses": 4,
  "total_unrealized_pnl": 4230.5,
  "total_unrealized_return_pct": 8.5
}
```

---

### ⚠️ TBD (Skipped)

| 항목 | 사유 |
|------|------|
| CORS origins 제한 | Cloudflare 도메인 확보 후 설정 |

