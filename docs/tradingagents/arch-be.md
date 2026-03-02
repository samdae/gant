# Backend Design Doc: TradingAgents Features (FR-013~063)

> Created: 2026-02-11
> Updated: 2026-03-01
> Service: tradingagents
> Type: Backend
> Requirements document: docs/tradingagents/spec.md
> Repo layout: monorepo (`packages/tradingagents`)

## 0. Summary

### Goal

기존 TradingAgents 멀티에이전트 분석 파이프라인에 **영속 메모리(Hybrid RAG)**, **가상 매매 검증**, **스케줄 기반 자동화**를 추가하고, **Postgres 기반 데이터 저장**, **반성 집중화(반성에이전트 1곳)**, **요약에이전트**를 도입하여, AI 분석의 정확도를 정량적으로 추적·학습하는 자기 개선 시스템으로 진화시킨다. 추가로 **스케줄 테이블 재설계(9테이블)**, **통화 지원(KRW/USD)**, **자동 청산 메커니즘**, **시장별 스케줄링**, **Codex LLM 프로바이더**를 도입한다. v5에서 **RAG 검색 파이프라인 개편(맥락 인식 검색, usefulness 기반 필터링)**, **RAG Validator(경험 유용성 자동 평가)**, **매매검증 검색 기능**을 추가한다. v6에서 **회고분석 배점(analysis_accuracy, rag_contribution)**, **포트폴리오 모드(공유 자금 풀, 비서 에이전트, PortfolioManagerAgent, 주간 반성)**를 도입한다. v7에서 **시장별 매크로 지표 + 섹터 호황도 컨텍스트 주입(FR-062, FR-063)**을 도입하여 12에이전트와 PA의 판단 맥락을 강화한다.

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
- **FR-055: 회고분석 배점 — analysis_accuracy + rag_contribution 0~100 수치화** (Implemented)
- **FR-056: 포트폴리오 모드 인프라 — 전용 테이블 5개, 활성화 설정** (Implemented)
- **FR-057: 비서 에이전트 — reports 요약 압축 → 포트폴리오 PA 입력** (Implemented)
- **FR-058: PortfolioManagerAgent — 리밸런싱 결정, 매매 지시 JSON** (Implemented)
- **FR-059: 포트폴리오 공유 자금 풀 — 혼합 통화, 환율, 거래 수수료** (Implemented)
- **FR-060: 포트폴리오 RAG 교차 참조 — 모드별 컬렉션 분리** (Implemented)
- **FR-061: 포트폴리오 주간 반성 — KST 일요일 12:00, 성과 평가** (Implemented)
- **FR-062: 매크로 컨텍스트 주입 — 시장별(us/kr/crypto) 지표를 12에이전트 + PA 프롬프트에 공통 반영** (Implemented)
- **FR-063: 섹터 호황도 주입 — 섹터 자동 판별 + ETF 상대강도/추세 계산 + 캐시/폴백** (Implemented)

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
| `tradingagents/retrospective/service.py` | 회고분석 프롬프트에 배점 출력 추가 + 파싱 | modify (FR-055) |
| `tradingagents/agents/briefing_agent.py` | 비서 에이전트 — 전체 티커 reports 압축 → 브리핑 텍스트 | **new** (FR-057) |
| `tradingagents/virtual_trade/portfolio_manager_agent.py` | PortfolioManagerAgent — 리밸런싱 결정 (텍스트 + JSON) | **new** (FR-058) |
| `tradingagents/graph/portfolio_reflection.py` | PortfolioReflector — 주간 배분 품질 평가 | **new** (FR-061) |
| `tradingagents/scheduler/portfolio_pipeline.py` | 포트폴리오 일일/주간 파이프라인 오케스트레이터 | **new** (FR-056) |
| `tradingagents/virtual_trade/fee_calculator.py` | 시장별 거래 수수료 계산 | **new** (FR-059) |
| `tradingagents/virtual_trade/exchange_rate.py` | yfinance 환율 조회 + 캐시 (1시간 TTL) | **new** (FR-059) |
| `tradingagents/storage/portfolio_*_repo.py` | 포트폴리오 전용 5개 Repository (config, decision, trade, holding, reflection) | **new** (FR-056) |
| `tradingagents/api/portfolio_routes.py` | 포트폴리오 전용 API 라우터 (9개 엔드포인트) | **new** (FR-056) |
| `tradingagents/memory/hybrid_memory.py` | `collection_name` + `fts_repo` 파라미터화 → 모드별 인스턴스 분리 | modify (FR-060) |
| `tradingagents/dataflows/macro_collector.py` | 시장별 매크로 지표 + 섹터 상대강도 수집/포맷팅 + 일일 캐시 (`_macro_cache`, `_sector_cache`) | **new** (FR-062, FR-063) |
| `tradingagents/agents/utils/macro_mixin.py` | 에이전트 프롬프트 공통 매크로 블록 생성 (`get_macro_block`) | **new** (FR-062) |
| `tradingagents/agents/*` | Market/Bull/Bear/Research/Risk/Trader 프롬프트에 `macro_context` 주입 | modify (FR-062) |
| `tradingagents/scheduler/ticker_scheduler.py` | 분석 시작 전 `collect_macro_context()` 호출 후 그래프에 전달 | modify (FR-062, FR-063) |
| `tradingagents/graph/propagation.py` | `AgentState` 초기값에 `macro_context` 필드 주입 | modify (FR-062) |
| `tradingagents/virtual_trade/portfolio_agent.py` | PA 프롬프트에 매크로/섹터 컨텍스트 섹션 추가 | modify (FR-062) |

### Data

#### Postgres Schema — FR-030, FR-039~044

> 전체 DDL은 `tradingagents/storage/database.py` 참조
> **FR-039**: `schedules` 테이블 제거. `schedule_configs` 확장, `schedule_jobs` FK 통합
> v4에서 `retrospective_analyses` 추가, FR-053에서 `rag_validation_results` 추가 → 총 9테이블

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
    rag_used                          BOOLEAN NOT NULL DEFAULT FALSE, -- [v4] PA가 RAG 경험 사용 여부
    rag_docs                          JSONB,                         -- [v4] PA에 주입된 RAG 문서 구조체
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

-- ⑧ retrospective_analyses: 회고분석 (v4 도입, FR-055 배점 구현 완료)
CREATE TABLE retrospective_analyses (
    id                  BIGSERIAL PRIMARY KEY,
    position_id         BIGINT    NOT NULL UNIQUE REFERENCES positions(id),
    ticker              TEXT      NOT NULL,
    position_sequence   INTEGER   NOT NULL,
    position_status     TEXT      NOT NULL,
    status              TEXT      NOT NULL DEFAULT 'pending',
    analysis_content    TEXT,
    analysis_count      INTEGER   NOT NULL DEFAULT 1,
    analysis_accuracy   INTEGER,                              -- [FR-055] 0~100, 분석 정확도
    rag_contribution    INTEGER,                              -- [FR-055] 0~100 or NULL, RAG 기여도
    position_open_date  TIMESTAMPTZ,
    position_close_date TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(ticker, position_sequence)
);
CREATE INDEX idx_retro_ticker ON retrospective_analyses(ticker);
CREATE INDEX idx_retro_status ON retrospective_analyses(status);

-- ⑨ FTS: Postgres GIN 인덱스 (BM25 검색용) — FR-033
CREATE INDEX idx_reflections_search
    ON reflections
    USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
```

> 제외 컬럼: `sentiment_report` (시의성), `news_report` (bull/bear 논거에 반영)
> 각 요약 컬럼 목표: 200~400 토큰

#### Postgres Schema — Portfolio (FR-056~061)

> 포트폴리오 모드 전용 5테이블. 기존 `positions` 테이블과 **완전 분리**(공유는 `reports` 읽기만).
> 금액: DOUBLE PRECISION (기존 패턴 일관성), 통화 변환은 application layer에서 처리.
> 마이그레이션: `init_schema()` + `_ensure_column` 패턴 동일 적용.

```sql
-- ⑩ portfolio_configs: 포트폴리오 설정 (FR-056)
CREATE TABLE portfolio_configs (
    id               BIGSERIAL PRIMARY KEY,
    name             TEXT      NOT NULL DEFAULT 'default',
    initial_capital  DOUBLE PRECISION NOT NULL DEFAULT 100000000,  -- 1억원
    total_fund       DOUBLE PRECISION NOT NULL DEFAULT 100000000,  -- 현재 총 자산 (KRW 환산)
    available_cash   DOUBLE PRECISION NOT NULL DEFAULT 100000000,  -- 가용 현금 (KRW)
    base_currency    TEXT      NOT NULL DEFAULT 'KRW',
    fee_enabled      BOOLEAN   NOT NULL DEFAULT TRUE,
    us_fee_rate      DOUBLE PRECISION NOT NULL DEFAULT 0.001,      -- 0.1%
    kr_buy_fee_rate  DOUBLE PRECISION NOT NULL DEFAULT 0.0025,     -- 0.25%
    kr_sell_fee_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0025,     -- 0.25%
    kr_sell_tax_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0018,     -- 0.18%
    crypto_fee_rate  DOUBLE PRECISION NOT NULL DEFAULT 0.001,      -- 0.1%
    status           TEXT      NOT NULL DEFAULT 'active',          -- active / paused
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ⑪ portfolio_decisions: 일일 리밸런싱 결정 (FR-057, FR-058)
CREATE TABLE portfolio_decisions (
    id                      BIGSERIAL PRIMARY KEY,
    portfolio_config_id     BIGINT    NOT NULL REFERENCES portfolio_configs(id),
    decision_date           DATE      NOT NULL,
    briefing_summary        JSONB,                                  -- BriefingAgent 출력 (티커별 요약)
    allocation_plan         JSONB     NOT NULL,                     -- [{ticker, action, allocation_pct, shares, rationale}]
    rationale               TEXT,                                   -- 전체 배분 근거
    total_fund_snapshot     DOUBLE PRECISION NOT NULL,
    available_cash_snapshot DOUBLE PRECISION NOT NULL,
    exchange_rate_snapshot  DOUBLE PRECISION,                       -- USDKRW at decision time
    status                  TEXT      NOT NULL DEFAULT 'pending',   -- pending / executing / completed / failed
    error_message           TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_portfolio_decisions_config ON portfolio_decisions(portfolio_config_id);
CREATE UNIQUE INDEX idx_portfolio_decisions_date ON portfolio_decisions(portfolio_config_id, decision_date);

-- ⑫ portfolio_trades: 포트폴리오 매매 기록 (FR-059)
CREATE TABLE portfolio_trades (
    id                    BIGSERIAL PRIMARY KEY,
    portfolio_decision_id BIGINT    NOT NULL REFERENCES portfolio_decisions(id),
    ticker                TEXT      NOT NULL,
    action                TEXT      NOT NULL,                       -- buy / sell / hold
    shares                DOUBLE PRECISION NOT NULL DEFAULT 0,
    price                 DOUBLE PRECISION NOT NULL,                -- 현지 통화 기준 체결가
    currency              TEXT      NOT NULL DEFAULT 'USD',
    exchange_rate         DOUBLE PRECISION NOT NULL DEFAULT 1.0,    -- 매매 시점 USDKRW 스냅샷
    fee_rate              DOUBLE PRECISION NOT NULL DEFAULT 0,
    fee_amount            DOUBLE PRECISION NOT NULL DEFAULT 0,      -- KRW 환산 수수료
    amount_local          DOUBLE PRECISION NOT NULL DEFAULT 0,      -- price × shares (현지 통화)
    amount_krw            DOUBLE PRECISION NOT NULL DEFAULT 0,      -- KRW 환산 총액 (수수료 포함)
    executed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_portfolio_trades_decision ON portfolio_trades(portfolio_decision_id);
CREATE INDEX idx_portfolio_trades_ticker ON portfolio_trades(ticker);

-- ⑬ portfolio_holdings: 포트폴리오 티커별 보유 현황 (FR-059)
CREATE TABLE portfolio_holdings (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_config_id BIGINT    NOT NULL REFERENCES portfolio_configs(id),
    snapshot_date       DATE      NOT NULL,                          -- 일별 스냅샷 기준일
    ticker              TEXT      NOT NULL,
    shares              DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_cost            DOUBLE PRECISION NOT NULL DEFAULT 0,        -- 현지 통화 기준 평단가
    currency            TEXT      NOT NULL DEFAULT 'USD',
    current_value_krw   DOUBLE PRECISION NOT NULL DEFAULT 0,        -- 최신 KRW 환산 시가
    allocation_pct      DOUBLE PRECISION NOT NULL DEFAULT 0,        -- 포트폴리오 내 비중 (%)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_portfolio_holdings_unique ON portfolio_holdings(portfolio_config_id, ticker, snapshot_date);
CREATE INDEX idx_portfolio_holdings_snapshot_date ON portfolio_holdings(snapshot_date);

-- ⑭ portfolio_reflections: 주간 포트폴리오 회고 (FR-061)
CREATE TABLE portfolio_reflections (
    id                  BIGSERIAL PRIMARY KEY,
    portfolio_config_id BIGINT    NOT NULL REFERENCES portfolio_configs(id),
    week_start_date     DATE      NOT NULL,
    week_end_date       DATE      NOT NULL,
    reflection_content  TEXT,
    allocation_accuracy INTEGER,                                    -- 0~100, 배분 품질 자체 평가
    total_return_pct    DOUBLE PRECISION,                           -- 해당 주 수익률
    key_lessons         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_portfolio_reflections_config ON portfolio_reflections(portfolio_config_id);
CREATE UNIQUE INDEX idx_portfolio_reflections_week ON portfolio_reflections(portfolio_config_id, week_start_date);
```

#### 테이블 관계 (9 기본 + 5 포트폴리오 = 14테이블)

```
[기본 9테이블]
schedule_configs ─── 1:N ─── schedule_jobs ─── 1:N ─── schedule_job_events
                             schedule_jobs ─── 1:1 ─── reports
                                                       reports ──N:1── positions ─── 1:N ─── trades
                                                                        positions ─── 1:0..1 ── reflections
                                                                        positions ─── 0..1 ── retrospective_analyses
                                                       reports ──1:N── trades (report_id FK)
retrospective_analyses ─── 1:N ─── rag_validation_results
rag_validation_results ──N:1── reflections

[포트폴리오 5테이블]
portfolio_configs ─── 1:N ─── portfolio_decisions ─── 1:N ─── portfolio_trades
                 ─── 1:N ─── portfolio_holdings
                 ─── 1:N ─── portfolio_reflections
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
Postgres DB (Supabase / Docker)  ← 14 테이블 (기본 9 + 포트폴리오 5)
ChromaDB                         ← 2 컬렉션 (analysis_reflections, portfolio_reflections)
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

### Phase 4: 구현 완료 (FR-051~054)

| # | Spec Ref | Feature | File | Class | Method | Action | Impl |
|---|----------|---------|------|-------|--------|--------|------|
| 81 | FR-051 | RAG 쿼리 enrichment | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `_build_rag_query` | market/sector 텍스트 부착. `schedule_configs.market` + `yfinance Ticker.info.sector` 사용 | [x] |
| 82 | FR-052 | HybridMemory 파이프라인 재설계 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories` | FTS top-3 + ChromaDB top-3 → 중복제거 + RRF top-3 → usefulness < 40 배제 → usefulness DESC → top-K. 기존 top-10+top-10 RRF 교체 | [x] |
| 83 | FR-052 | usefulness 필터링 | `memory/hybrid_memory.py` | `HybridMemory` | `_apply_usefulness_filter` | usefulness_score < 40 하드 배제, DESC 정렬, top-K 컷. `ReflectionRepository` 연동 | [x] |
| 84 | FR-052 | reflections.usefulness_score 컬럼 | `storage/database.py` | `Database` | `init_schema` | ALTER TABLE reflections ADD COLUMN usefulness_score (ensure_column 패턴) | [x] |
| 85 | FR-052 | ReflectionRepo usefulness 메서드 | `storage/reflection_repo.py` | `ReflectionRepository` | `get_usefulness_scores(reflection_ids)`, `update_usefulness_score(reflection_id, delta)` | 벌크 조회 + ±1 업데이트 (0~100 클램핑) | [x] |
| 86 | FR-052 | RAG_TOP_K 환경변수 | `default_config.py` | — | — | `"rag_top_k": int(os.getenv("RAG_TOP_K", "1"))` 추가 | [x] |
| 87 | FR-053 | RAG Validator 모듈 | `rag_validator/__init__.py` | — | — | 새 모듈 생성 | [x] |
| 88 | FR-053 | RAG Validator 프롬프트 | `rag_validator/prompt.py` | — | `build_validation_prompt` | 회고분석 결과 + RAG 문서별 → "PA가 이 경험을 반영했는가?" 판정 프롬프트. 구조화 출력 (JSON verdict + justification) | [x] |
| 89 | FR-053 | RAG Validator 서비스 | `rag_validator/service.py` | `RAGValidatorService` | `validate(retrospective_id)`, `_evaluate_document(retro_content, rag_doc)`, `_apply_score_adjustments(results)`, `_generate_report(results)` | 오케스트레이터: 입력 수집 → 문서별 평가 → 점수 조정 → 리포트 생성 | [x] |
| 90 | FR-053 | RAG Validator 멱등성 | `rag_validator/service.py` | `RAGValidatorService` | `_is_already_evaluated(retrospective_id, reflection_id)` | (retrospective_id, reflection_id) 쌍 중복 평가 방지 | [x] |
| 91 | FR-053 | RAG Validator API | `api/routes.py` | — | `POST /rag-validator/run`, `GET /rag-validator/reports`, `GET /rag-validator/reports/{id}` | 수동 실행 트리거 + 리포트 목록/상세 조회. Bearer 인증(POST만) | [x] |
| 92 | FR-053 | RAG Validator 큐 통합 | `api/app.py` | — | `_queue_worker` | `item['type'] == 'rag_validation'` 분기. priority=2 (스케줄 0, 회고분석 1, RAG 검증 2) | [x] |
| 93 | FR-054 | 키워드 검색 | `storage/reflection_repo.py` | `ReflectionRepository` | `search_keyword(query, limit)` | `ILIKE '%{query}%'` on reflection + key_lessons | [x] |
| 94 | FR-054 | 시멘틱 검색 | `memory/hybrid_memory.py` | `HybridMemory` | `search_semantic(query, limit)` | ChromaDB 단독 쿼리 (RRF 없이) | [x] |
| 95 | FR-054 | 검색 API | `api/routes.py` | — | `GET /reflections/search?q=...&mode=keyword|semantic&limit=20` | 모드별 전략 디스패치. 공개 READ | [x] |
| 96 | FR-053 | 평가 결과 테이블 | `storage/database.py` | `Database` | `init_schema` | `rag_validation_results` CREATE TABLE + UNIQUE 인덱스 | [x] |
| 97 | FR-053 | ValidationResultRepository | `storage/rag_validation_repo.py` | `RAGValidationRepository` | `create`, `exists(retro_id, reflection_id)`, `list_by_retrospective`, `get_summary` | CRUD + 멱등성 체크 + 집계 | [x] |

### Phase 5: 구현 완료 (FR-055~061)

| # | Spec Ref | Feature | File | Class / Function | Method / Detail | Action |
|---|----------|---------|------|------------------|-----------------|--------|
| 98 | FR-055 | 회고분석 배점 프롬프트 확장 | `retrospective/service.py` | `RetrospectiveService` | `_build_prompt` 에 `analysis_accuracy`, `rag_contribution` JSON 블록 출력 지시 추가 | modify |
| 99 | FR-055 | 배점 파싱 + 저장 | `retrospective/service.py` | `RetrospectiveService` | `_parse_scores(content) → (accuracy: int, contribution: int\|None)`. `run_analysis()` 에서 파싱 후 `RetroRepository.update_scores()` 호출 | modify |
| 100 | FR-055 | RetroRepo 배점 업데이트 | `storage/retrospective_repo.py` | `RetrospectiveRepository` | `update_scores(id, accuracy, contribution)` — UPDATE SET analysis_accuracy, rag_contribution, updated_at | modify |
| 101 | FR-056 | 포트폴리오 5테이블 DDL | `storage/database.py` | `Database` | `init_schema` — 5테이블 CREATE TABLE IF NOT EXISTS + 인덱스 | modify |
| 102 | FR-056 | PortfolioConfigRepository | `storage/portfolio_config_repo.py` | `PortfolioConfigRepository` | `get_active`, `create`, `update_fund(config_id, total_fund, available_cash)`, `pause`, `resume` | **new** |
| 103 | FR-056 | PortfolioDecisionRepository | `storage/portfolio_decision_repo.py` | `PortfolioDecisionRepository` | `create`, `update_status`, `get_by_date(config_id, date)`, `list_recent(config_id, limit)` | **new** |
| 104 | FR-056 | PortfolioTradeRepository | `storage/portfolio_trade_repo.py` | `PortfolioTradeRepository` | `create_batch(trades[])`, `list_by_decision(decision_id)`, `get_summary_by_ticker(config_id)` | **new** |
| 105 | FR-056 | PortfolioHoldingRepository | `storage/portfolio_holding_repo.py` | `PortfolioHoldingRepository` | `create_snapshot(config_id, snapshot_date, ticker, shares, avg_cost, allocation_pct, …)`, `list_latest(config_id)`, `list_by_date_range(config_id, from, to)`, `cleanup_old_snapshots(days=14)` | **new** |
| 106 | FR-056 | PortfolioReflectionRepository | `storage/portfolio_reflection_repo.py` | `PortfolioReflectionRepository` | `create`, `get_by_week(config_id, week_start)`, `list_recent(config_id, limit)` | **new** |
| 107 | FR-056 | 포트폴리오 파이프라인 오케스트레이터 | `scheduler/portfolio_pipeline.py` | `PortfolioPipeline` | `run_daily(config_id)` — (1) 전체 티커 reports 수집 → (2) BriefingAgent → (3) PortfolioManagerAgent → (4) 매매 실행 → (5) holdings 갱신 | **new** |
| 108 | FR-056 | 스케줄러 연동 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_on_all_tickers_complete()` — 이벤트 기반 집계. `done+skipped==total_active && failed==0`일 때만 `portfolio_daily` 큐 등록, 멱등성 키로 중복 차단 | modify |
| 109 | FR-056 | 큐 워커 포트폴리오 분기 | `api/app.py` | — | `_queue_worker` — `item['type'] == 'portfolio_daily'` (priority=3), `'portfolio_weekly'` (priority=4) | modify |
| 110 | FR-057 | BriefingAgent | `agents/briefing_agent.py` | `BriefingAgent` | `generate_briefing(reports: list[dict]) → BriefingSummary` — 전체 티커 리포트 압축 → JSONB (ticker별 action/confidence/요약) | **new** |
| 111 | FR-057 | BriefingAgent 프롬프트 | `agents/briefing_agent.py` | — | `_BRIEFING_PROMPT` — 시스템 프롬프트: "투자 비서로서 12-agent 분석 결과를 간결히 요약하되, 각 종목의 최종 판단(buy/sell/hold)·신뢰도·핵심 근거를 유지하라" | **new** |
| 112 | FR-058 | PortfolioManagerAgent | `virtual_trade/portfolio_manager_agent.py` | `PortfolioManagerAgent` | `decide_allocation(briefing, holdings, available_cash, exchange_rate) → AllocationPlan` | **new** |
| 113 | FR-058 | PortfolioManagerAgent 프롬프트 | `virtual_trade/portfolio_manager_agent.py` | — | `_PM_PROMPT` — "포트폴리오 매니저로서 현재 보유 현황과 가용 자금을 고려하여 리밸런싱 계획을 수립하라. JSON [{ticker, action, allocation_pct, shares, rationale}] + 전체 근거 TEXT" | **new** |
| 114 | FR-058 | PM JSON 파싱 + 검증 | `virtual_trade/portfolio_manager_agent.py` | `PortfolioManagerAgent` | `_parse_plan(response) → AllocationPlan`. allocation_pct 합 100% 검증, shares × price ≤ available_cash 검증, LLM fallback on parse error | **new** |
| 115 | FR-059 | 수수료 계산기 | `virtual_trade/fee_calculator.py` | `FeeCalculator` | `calculate(market, action, amount) → FeeResult(rate, amount)`. 기본값: us 0.1%, kr buy 0.25% / sell 0.25%+0.18% tax, crypto 0.1%. `portfolio_configs` 사용자 설정값 우선 | **new** |
| 116 | FR-059 | 환율 조회 | `virtual_trade/exchange_rate.py` | `ExchangeRateService` | `get_usd_krw() → float`. yfinance `USDKRW=X`, 1시간 TTL 인메모리 캐시. 실패 시 마지막 캐시값 반환 (None이면 1380.0 하드코딩 폴백) | **new** |
| 117 | FR-059 | 매매 실행 엔진 | `scheduler/portfolio_pipeline.py` | `PortfolioPipeline` | `_execute_trades(plan, config, exchange_rate)` — plan 순회: 현가 조회 → 수수료 계산 → portfolio_trades INSERT → 일별 holdings snapshot INSERT → available_cash 차감. 실행 후 14일 이전 snapshot 정리 | modify |
| 118 | FR-060 | HybridMemory 컬렉션 분리 | `memory/hybrid_memory.py` | `HybridMemory` | `__init__` 에 `collection_name` 파라미터 추가. 기존: `"analysis_reflections"`, 포트폴리오: `"portfolio_reflections"`. FTS 쿼리 대상 테이블도 파라미터화 | modify |
| 119 | FR-060 | RAG 교차 참조 | `memory/hybrid_memory.py` | `HybridMemory` | `get_memories_cross(query, primary_collection, secondary_collection, primary_k, secondary_k)` — primary에서 top-K + secondary에서 top-1, 소스 태깅하여 반환 | **new** |
| 120 | FR-060 | PM RAG 연동 | `virtual_trade/portfolio_manager_agent.py` | `PortfolioManagerAgent` | `_inject_rag(briefing)` — `get_memories_cross("portfolio_reflections", "analysis_reflections", 2, 1)` 호출 → PM 프롬프트에 "과거 경험" 섹션 주입 | modify |
| 121 | FR-061 | PortfolioReflector | `graph/portfolio_reflection.py` | `PortfolioReflector` | `reflect_weekly(config_id, week_start, week_end) → ReflectionResult` — 해당 주 decisions + trades + holdings 변화 분석 → LLM 평가 → portfolio_reflections INSERT + ChromaDB 벡터 저장 | **new** |
| 122 | FR-061 | 주간 스케줄러 트리거 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_init_weekly_schedule()` — `CronTrigger(day_of_week='sun', hour=12, minute=0, timezone='Asia/Seoul')`. `PortfolioPipeline.run_weekly` 큐 등록 | modify |
| 123 | FR-061 | PortfolioReflector 프롬프트 | `graph/portfolio_reflection.py` | — | `_WEEKLY_REFLECTION_PROMPT` — "이번 주 포트폴리오 배분 결정을 복기하라. allocation_accuracy(0~100), 핵심 교훈, 개선 방향을 제시하라" | **new** |
| 124 | FR-056 | 포트폴리오 API 라우터 | `api/portfolio_routes.py` | — | 9개 엔드포인트 (상세 §6 참조) | **new** |

### Phase 6: 구현 완료 (FR-062~063, v7)

| # | Spec Ref | Feature | File | Class / Function | Method / Detail | Action | Impl |
|---|----------|---------|------|------------------|-----------------|--------|------|
| 125 | FR-062 | AgentState 확장 | `agents/utils/agent_states.py` | `AgentState` | `macro_context` 필드 추가 (TypedDict) | modify | [x] |
| 126 | FR-062 | 그래프 입력 경로 확장 | `graph/propagation.py`, `graph/trading_graph.py` | `Propagator`, `TradingAgentsGraph` | `create_initial_state(..., macro_context)`, `propagate(..., macro_context)` 시그니처/전달 | modify | [x] |
| 127 | FR-062 | 스케줄러 선행 수집 | `scheduler/ticker_scheduler.py` | `TickerScheduler` | `_run_analysis_cycle_impl`에서 `collect_macro_context(ticker, market)` 호출 후 그래프에 주입 | modify | [x] |
| 128 | FR-062 | 프롬프트 공통 유틸 | `agents/utils/macro_mixin.py` | `get_macro_block` | `macro_context`가 있을 때만 공통 블록 생성 | **new** | [x] |
| 129 | FR-062 | 시장 분석가 프롬프트 반영 | `agents/analysts/market_analyst.py` | `create_market_analyst` | system prompt에 매크로/섹터 컨텍스트 직접 삽입 | modify | [x] |
| 130 | FR-062 | 토론/리스크/트레이더 프롬프트 반영 | `agents/researchers/*.py`, `agents/managers/*.py`, `agents/risk_mgmt/*.py`, `agents/trader/trader.py` | Bull/Bear/Research/Risk/Trader | `get_macro_block(state)` 호출로 공통 컨텍스트 삽입 | modify | [x] |
| 131 | FR-062 | PA 프롬프트 반영 | `virtual_trade/portfolio_agent.py` | `PortfolioAgent` | `pipeline_state["macro_context"]`를 의사결정 프롬프트에 추가 | modify | [x] |
| 132 | FR-063 | 매크로 수집기 모듈 | `dataflows/macro_collector.py` | `collect_macro_context` | 시장별 수집기 `_collect_macro_us/_kr/_crypto` + 공통 포맷 | **new** | [x] |
| 133 | FR-063 | 섹터 ETF 매핑/폴백 | `dataflows/macro_collector.py` | `_collect_sector` | US 11개/KR 8개 ETF 매핑, 미매핑 시 fallback 메시지 | **new** | [x] |
| 134 | FR-063 | 섹터 강도 계산 | `dataflows/macro_collector.py` | `_relative_strength_20d`, `_trend_vs_sma` | 상대강도(최근 1개월) + 50일선 추세 계산 | **new** | [x] |
| 135 | FR-063 | 일일 캐시 전략 | `dataflows/macro_collector.py` | `_macro_cache`, `_sector_cache` | 시장별/ETF별 당일 1회 캐시로 중복 fetch 억제 | **new** | [x] |
| 136 | FR-063 | 코인/장애 허용 정책 | `dataflows/macro_collector.py` | `collect_macro_context` | crypto는 섹터 스킵, fetch 실패 시 `N/A`/빈 문자열로 graceful degradation | **new** | [x] |

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

11. **Step 11: 회고분석 배점 (FR-055)**
    - `retrospective/service.py` — 프롬프트에 analysis_accuracy, rag_contribution 출력 지시 추가
    - `_parse_scores()` 추출 → `RetroRepository.update_scores()` 저장
    - 기존 회고분석 파이프라인에 자연스럽게 통합 (파싱 단계 추가만)

12. **Step 12: 포트폴리오 인프라 (FR-056)**
    - `database.py` — 5테이블 DDL 추가 (init_schema)
    - 5개 Repository 구현 (config, decision, trade, holding, reflection)
    - `PortfolioPipeline` 오케스트레이터 스켈레톤

13. **Step 13: 브리핑 + 매니저 에이전트 (FR-057, FR-058)**
    - `BriefingAgent` — 전체 티커 리포트 압축 → BriefingSummary(JSONB)
    - `PortfolioManagerAgent` — 리밸런싱 결정 (JSON plan + TEXT rationale)
    - `PortfolioPipeline.run_daily()` 완성 — Briefing → PM → 매매 실행 → holdings 갱신

14. **Step 14: 공유 자금 풀 + 수수료 (FR-059)**
    - `FeeCalculator` — 시장별 수수료 계산 (us/kr/crypto)
    - `ExchangeRateService` — yfinance USDKRW=X + 1시간 캐시
    - `_execute_trades()` — plan 순회, 현가 조회, 수수료 적용, holdings snapshot INSERT, cash 차감
    - 스케줄러 연동 — `_on_all_tickers_complete()` → 큐 등록 (priority=3)

15. **Step 15: RAG 교차 참조 + 주간 회고 (FR-060, FR-061)**
    - `HybridMemory` — collection_name 파라미터화, `get_memories_cross()` 추가
    - `PortfolioReflector.reflect_weekly()` — 주간 decisions/trades 분석 → LLM → DB + ChromaDB
    - `CronTrigger(day_of_week='sun', hour=12, minute=0, timezone='Asia/Seoul')` 주간 스케줄 등록

16. **Step 16: 매크로/섹터 컨텍스트 주입 (FR-062, FR-063)**
    - `dataflows/macro_collector.py` 신규: 시장별 매크로 + 섹터 상대강도 수집, 일일 캐시, 폴백
    - `scheduler/ticker_scheduler.py`에서 분석 시작 전 `collect_macro_context()` 호출 후 `graph.propagate(..., macro_context=...)` 전달
    - `AgentState`/`Propagator`/`TradingGraph` 경로에 `macro_context` 필드 연결
    - 12에이전트 + PA 프롬프트에 매크로 블록 주입 (`macro_mixin` + Market Analyst 직접 블록)

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
│  0.7. 매크로/섹터 컨텍스트 수집 (FR-062, FR-063)                          │
│     collect_macro_context(ticker, market)                                  │
│     → market(us/kr/crypto)별 거시지표 + 섹터 상대강도 계산                │
│     → 실패 시 N/A/빈 문자열로 graceful degradation                         │
│                                                                            │
│  1. G-ANT 분석 (12에이전트 파이프라인, 기존 그대로)                       │
│     Market → Social → News → Fundamentals                                  │
│     → Bull ↔ Bear (N rounds) → Research Judge                             │
│     → Trader → Aggressive ↔ Conservative ↔ Neutral → Risk Judge           │
│     → Signal: BUY/HOLD/SELL + strategy_json                               │
│     ※ 12에이전트는 포지션 정보 없이 완전 객관적 분석 (FR-021)            │
│     ※ AgentState.macro_context로 시장/섹터 컨텍스트 공통 주입 (FR-062)   │
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

### 5.5 Portfolio Daily Pipeline (FR-056~059)

```
All Tickers Complete (이벤트)
         │
         ▼
TickerScheduler._on_all_tickers_complete()
         │ queue.put({type: 'portfolio_daily', priority: 3})
         ▼
_queue_worker → PortfolioPipeline.run_daily(config_id)
         │
    ┌────┴────────────────────────────────────────────┐
    │ Step 1: ReportRepository.get_today_reports()    │
    │ → 전체 티커 최신 리포트 수집                    │
    └────┬────────────────────────────────────────────┘
         │
         ▼
    BriefingAgent.generate_briefing(reports)
         │ → BriefingSummary (JSONB: 티커별 action/confidence/요약)
         ▼
    ┌────┴────────────────────────────────────────────┐
    │ ExchangeRateService.get_usd_krw()               │
    │ HoldingRepo.get_all(config_id) → 현재 보유      │
    │ ConfigRepo.get_active() → available_cash         │
    │ [선택] HybridMemory.get_memories_cross()         │
    │   → portfolio_reflections(top-2) +               │
    │     analysis_reflections(top-1)                   │
    └────┬────────────────────────────────────────────┘
         │
         ▼
    PortfolioManagerAgent.decide_allocation(
        briefing, holdings, available_cash, exchange_rate, rag_context)
         │ → AllocationPlan [{ticker, action, allocation_pct, shares, rationale}]
         ▼
    PortfolioPipeline._execute_trades(plan, config, exchange_rate)
         │
    ┌────┴────── for each ticker in plan ──────┐
    │  yfinance 현재가 조회                     │
    │  FeeCalculator.calculate(market, action,  │
    │    shares × price)                         │
    │  portfolio_trades INSERT                   │
    │  portfolio_holdings snapshot INSERT        │
    │  portfolio_configs.available_cash 차감     │
    └────┬─────────────────────────────────────┘
         │
         ▼
    portfolio_decisions UPDATE status='completed'
    + snapshot_date 기준 14일 이전 holdings 자동 정리
    WebSocket broadcast: {type: 'portfolio_daily_complete'}
```

### 5.6 Portfolio Weekly Reflection (FR-061)

```
CronTrigger(day_of_week='sun', hour=12, minute=0, timezone='Asia/Seoul')
         │ queue.put({type: 'portfolio_weekly', priority: 4})
         ▼
_queue_worker → PortfolioPipeline.run_weekly(config_id)
         │
    ┌────┴────────────────────────────────────────────┐
    │ DecisionRepo.list_by_week(config_id, week)      │
    │ TradeRepo.list_by_week(config_id, week)         │
    │ HoldingRepo.list_by_date_range(config_id, week) │
    │   → 주초 snapshot vs 주말 snapshot 비교          │
    │ 주간 수익률 계산 (snapshot KRW 시가 변화)        │
    └────┬────────────────────────────────────────────┘
         │
         ▼
    PortfolioReflector.reflect_weekly(data)
         │ deep_think_llm 호출
         │ → reflection_content + allocation_accuracy + key_lessons
         ▼
    ┌────┴──────────────┐
    │                    │
    ▼                    ▼
 Postgres             ChromaDB
 portfolio_reflections "portfolio_reflections"
 INSERT               벡터 임베딩 저장
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
| GET | `/rag-validator/reports` | — | RAG 효과 분석 리포트 목록 (?cursor, ?limit) (FR-053) |
| GET | `/rag-validator/reports/{retrospective_id}` | — | RAG 효과 분석 상세 (문서별 verdict + justification) (FR-053) |
| GET | `/portfolio/config` | — | 포트폴리오 설정 조회 (FR-056) |
| POST | `/portfolio/config` | Bearer | 포트폴리오 설정 생성/수정 (initial_capital, base_currency, fee_enabled, 시장별 fee_rate) (FR-056, FR-059) |
| POST | `/portfolio/config/pause` | Bearer | 포트폴리오 일시정지 (FR-056) |
| POST | `/portfolio/config/resume` | Bearer | 포트폴리오 재개 (FR-056) |
| GET | `/portfolio/decisions` | — | 일일 결정 목록 (?cursor, ?limit) — briefing_summary, allocation_plan 포함 (FR-057, FR-058) |
| GET | `/portfolio/decisions/{id}` | — | 결정 상세 + 해당 trades 목록 (FR-058) |
| GET | `/portfolio/holdings` | — | 최신 snapshot 기준 현재 보유 현황 (allocation_pct, current_value_krw 포함) (FR-059) |
| GET | `/portfolio/trades` | — | 매매 기록 (?ticker, ?cursor, ?limit) — 수수료·환율 포함 (FR-059) |
| GET | `/portfolio/reflections` | — | 주간 회고 목록 (?cursor, ?limit) (FR-061) |

### WebSocket

| Path | Description |
|------|-------------|
| `WS /ws/analyze/{ticker}` | 에이전트 상태 실시간 스트리밍 (step/phase 포함, timeout 1h) |
| `WS /ws/analyze/{ticker}` | (기존) `portfolio_daily_complete`, `portfolio_weekly_complete` 이벤트 타입 추가 |

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
| `PORTFOLIO_ENABLED` | 포트폴리오 모드 활성화 (FR-056) | `false` |
| `PORTFOLIO_INITIAL_CAPITAL` | 포트폴리오 초기 자금 (KRW) (FR-059) | `100000000` |
| `PORTFOLIO_FEE_ENABLED` | 거래 수수료 적용 여부 (FR-059) | `true` |
| `PORTFOLIO_SNAPSHOT_RETENTION_DAYS` | portfolio_holdings snapshot 보관 일수 (일별 정리 기준) | `14` |
| `PORTFOLIO_READ_AUTH_REQUIRED` | 포트폴리오 READ 엔드포인트 인증 강제 여부 (터널/운영 hardening) | `false` |
| `EXCHANGE_RATE_CACHE_TTL` | 환율 캐시 TTL (초) (FR-059) | `3600` |
| `EXCHANGE_RATE_FALLBACK` | 환율 조회 실패 시 폴백 값 (FR-059) | `1380.0` |
| `API_RATE_LIMIT_PER_MIN` | 리버스 프록시/게이트웨이 기준 분당 요청 제한(문서 계약값) | `120` |

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
| 매크로 데이터 소스 | yfinance 단일 | 외부 매크로 API(FRED 등) | 의존성/운영 복잡도 최소화, 기존 데이터 흐름 재사용 (FR-062) |
| 매크로 해석 방식 | 룰 기반 해석 없음 (수치 원문 주입) | 규칙 엔진 선해석 | 하드코딩 편향을 줄이고 LLM+RAG가 맥락적으로 판단 (FR-062, FR-063) |
| 금액 타입 (포트폴리오) | DOUBLE PRECISION | DECIMAL(18,4) | 기존 9테이블 패턴 일관성. 가상 매매라 소수점 정밀도 이슈 무관 (FR-056, v6 설계 토론) |
| 수수료 테이블 | `portfolio_configs` 저장 + `FeeCalculator` 기본값 fallback | 별도 fee_rates 테이블 | 사용자 조정 가능성과 단순 스키마의 균형. 단일 사용자 운영에서도 실험 파라미터 추적 가능 |
| 스케줄 완료 감지 | 이벤트 드리븐 (schedule_jobs 완료 카운트) | 폴링 | `_on_all_tickers_complete()` — 마지막 job 완료 시 active config 기준 전체 카운트 비교. 폴링 대비 즉시 반응 (FR-056, v6 설계 토론) |
| 마이그레이션 (포트폴리오) | init_schema() + ensure_column | Alembic | 기존 패턴 일관성. 단일 사용자 시스템에서 Alembic 오버헤드 불필요 (v6 설계 토론) |
| 포트폴리오 API 프리픽스 | `/portfolio/*` (9개) | `/api/v1/portfolio/*` | 기존 엔드포인트 프리픽스 없음. 일관성 우선. 리버스 프록시 필요 시 nginx에서 처리 (v6 설계 토론) |

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
| yfinance 환율 조회 실패 | 포트폴리오 KRW 환산 부정확 | 1시간 TTL 캐시 + 마지막 성공값 보존 + 1380.0 하드코딩 폴백 (FR-059) |
| PM 에이전트 JSON 파싱 실패 | 당일 포트폴리오 결정 불가 | LLM fallback (재시도 1회, 더 엄격한 프롬프트), 실패 시 decision.status='failed' + 다음 날 재시도 |
| 개별 종목 매매 실패 | 일부 리밸런싱 미실행 | 종목별 try/except → 실패 건 skip + error_message 기록 + 나머지 종목 정상 실행 (hung job 대응) |
| 포트폴리오 파이프라인 hang | daily pipeline 무한 대기 | 기존 lock acquire timeout(600s) 적용. 초과 시 status='failed' 처리 |
| yfinance 매크로 fetch 실패 | 매크로 컨텍스트 일부/전체 누락 | 지표 단위 `N/A` 표기 + 전체 실패 시 빈 컨텍스트로 분석 지속 (FR-062) |
| 섹터 판별/ETF 매핑 누락 | 섹터 컨텍스트 품질 저하 | "판별 불가/대응 ETF 없음" 폴백 메시지 + 시장 지수 기준 해석 (FR-063) |

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
| 23 | Portfolio | 환율 조회 실패 | 캐시값 반환 → 캐시 없으면 1380.0 폴백. 로그 경고 (FR-059) |
| 24 | Portfolio | PM JSON 파싱 실패 | 1회 재시도 (stricter prompt), 실패 시 decision.status='failed' (FR-058) |
| 25 | Portfolio | 개별 종목 매매 실패 | 해당 건 skip + error_message 기록, 나머지 종목 정상 진행 (FR-059) |
| 26 | Portfolio | 전체 티커 미완료 상태에서 파이프라인 트리거 | 완료 카운트 불일치 시 무시. 다음 분석 완료 시 재검사 (FR-056) |
| 27 | Portfolio | available_cash 부족 | PM 결정 중 allocation_pct 기반 배분이므로 초과 불가. 안전장치: 실행 시 잔액 재확인 → 부족 시 해당 건 skip (FR-059) |
| 28 | Portfolio | 주간 회고 LLM 실패 | portfolio_reflections INSERT 없이 로그만 남김. 다음 주에 재시도 안 함 (FR-061) |
| 29 | Macro | 매크로 지표 일부 fetch 실패 | 실패 지표만 `N/A`로 표기하고 나머지 컨텍스트/분석은 정상 진행 (FR-062) |
| 30 | Macro | 섹터 판별 실패 또는 ETF 매핑 없음 | 섹터 블록을 "판별 불가/대응 ETF 없음" 메시지로 대체 후 진행 (FR-063) |
| 31 | Macro | 매크로 수집 전체 실패 | `macro_context=""`로 파이프라인 + PA 실행 (graceful degradation) (FR-062) |

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
| POST /portfolio/config | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| POST /portfolio/config/pause | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| POST /portfolio/config/resume | Bearer token | `api/auth.py` `check_admin_token` | 401 |
| GET /portfolio/* | 기본 공개, `PORTFOLIO_READ_AUTH_REQUIRED=true` 시 Bearer 필수 | `api/auth.py` 조건부 검사 | 401 |

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
| portfolio_decisions (config_id, date) UNIQUE | decision INSERT 시 | ON CONFLICT 방지 — 하루 1회 결정 보장 |
| portfolio_holdings (config_id, ticker, snapshot_date) UNIQUE | 일별 snapshot INSERT 시 | ON CONFLICT 방지 — 동일 일자 중복 스냅샷 차단 |
| portfolio_holdings 보관기간 14일 | daily pipeline 종료 시 | `snapshot_date < current_date - 14d` 자동 삭제 |
| portfolio_reflections (config_id, week_start) UNIQUE | reflection INSERT 시 | ON CONFLICT 방지 — 주 1회 회고 보장 |
| portfolio_trades 독립성 | trade INSERT 시 | `positions` FK 미사용. 포트폴리오 모드는 전용 5테이블에서만 상태 관리 |
| portfolio available_cash ≥ 0 | 매매 실행 시 application-level | 잔액 부족 시 해당 종목 skip |
| exchange_rate > 0 | 환율 조회 시 application-level | 0 이하면 폴백값 사용 |

---

## 10. Additional Design Details

### 10.1 REST API 페이지네이션

| 항목 | 값 |
|------|-----|
| 방식 | **혼합**: `/schedules`는 offset 기반, 나머지(포트폴리오 목록 포함)는 id cursor 기반 |
| 기본 limit | 10건 |
| 최대 limit | 100건 |
| 파라미터 | `/schedules`: `?cursor={offset}&limit={n}` / 나머지: `?cursor={last_id}&limit={n}` |
| 포트폴리오 예외 | `/portfolio/holdings`는 최신 snapshot 집합 조회라 pagination 미적용 |

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

### 10.12 RAG Validator 상세 (FR-053, check에서 보완)

#### LLM 모델
`quick_think_llm` 사용. K=1(초기)일 때 판정 대상 문서가 1개뿐이라 컨텍스트가 단순하므로 충분. `RAG_TOP_K`가 2~3으로 증가하면 deep_think_llm 전환 재검토 필요.

#### 평가 결과 테이블 — `rag_validation_results`

```sql
CREATE TABLE IF NOT EXISTS rag_validation_results (
    id                BIGSERIAL PRIMARY KEY,
    retrospective_id  BIGINT NOT NULL REFERENCES retrospective_analyses(id),
    reflection_id     BIGINT NOT NULL REFERENCES reflections(id),
    verdict           TEXT NOT NULL,          -- reflected | not_reflected | ambiguous
    justification     TEXT,                   -- LLM 판정 근거
    score_delta       INTEGER NOT NULL,       -- +1, -1, 0
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(retrospective_id, reflection_id)   -- 멱등성 보장
);
CREATE INDEX IF NOT EXISTS idx_rag_validation_retro ON rag_validation_results(retrospective_id);
```

#### verdict JSON 스키마 (LLM 구조화 출력)
```json
{
  "reflection_id": 123,
  "verdict": "reflected",
  "justification": "PA가 반도체 모멘텀 경험을 진입 타이밍 근거로 인용함"
}
```

#### API 스키마

**POST /rag-validator/run** (Bearer 인증)
```yaml
request:
  body:
    retrospective_ids: [int] | null   # null이면 미평가 전체 대상
response:
  success: { enqueued: int, skipped: int }
  errors:
    - { status: 401, message: "Unauthorized" }
```

**GET /rag-validator/reports** (공개)
```yaml
params: cursor, limit (기본 10)
response:
  - retrospective_id: int
    ticker: str
    position_sequence: int
    evaluated_count: int
    reflected_count: int
    not_reflected_count: int
    ambiguous_count: int
    created_at: str
```

**GET /rag-validator/reports/{retrospective_id}** (공개) — 개별 상세
```yaml
response:
  retrospective_id: int
  ticker: str
  summary:
    evaluated_count: int
    reflected_count: int
    not_reflected_count: int
    ambiguous_count: int
  details:
    - reflection_id: int
      verdict: str
      justification: str
      score_delta: int
      created_at: str
```

**GET /reflections/search** (공개)
```yaml
params: q (필수), mode (keyword|semantic), limit (기본 20)
response:
  mode: str
  results:
    - id: int
      ticker: str
      reflection: str (truncated)
      key_lessons: str
      outcome: str
      return_pct: float
      usefulness_score: float
      created_at: str
```

#### 트리거 시점
수동만 (`POST /rag-validator/run`). 자동 트리거는 데이터 축적 후 판단.

#### LLM 타임아웃
기존 시스템 정책 그대로 — MAX_RETRIES=5, 429→30s 대기, 503→모델 폴백.

### 10.13 Graceful Shutdown (check 리뷰에서 문서화)

FastAPI lifespan에서 이미 구현된 종료 순서:

```
1. Queue worker cancel (asyncio.Task.cancel)
2. APScheduler stop (scheduler.shutdown)
3. Event loop 정리
→ 로그: "Queue worker cancelled → APScheduler stopped → shutdown complete"
```

DB 연결은 프로세스 종료 시 psycopg가 자동 정리. ChromaDB PersistentClient도 별도 정리 불필요.

### 10.14 Design Decisions from Architecture Review (2026-02-27)

| 항목 | 결정 | 근거 |
|------|------|------|
| DB 마이그레이션 전략 | `init_schema()` + `ensure_column` 패턴 유지 | 단일 사용자, Alembic 오버헤드 불필요. CREATE TABLE IF NOT EXISTS + ensure_column으로 충분 |
| API 에러 응답 포맷 | FastAPI 기본 `{"detail": str}` 유지 | 단일 사용자 대시보드, FE가 detail만 사용. 커스텀 에러 코드 불필요 |
| LLM 비용 추적 | 불필요 (Skip) | Gemini=OAuth 무료, Codex=Pro 구독 무제한. 유료 API 전환 시 추가 |
| LLM 호출 타임아웃 | LLM 클라이언트 기본 + lock acquire timeout(600s) | deep_think 긴 응답 잘림 방지. 429/503은 이미 처리 |
| WebSocket Heartbeat | 불필요 (Skip) | 에이전트 이벤트가 수십 초 간격으로 암묵적 heartbeat. 단일 사용자, 끊기면 새로고침 |
| Prompt 버전 관리 | git 커밋 이력으로 충분 (Skip) | 프롬프트가 Python 코드에 있음. 별도 분리/버전 번호는 관리 오버헤드 |

### 10.15 Design Decisions from v6 Architecture Debate (2026-02-27)

> DA(Domain Architect) 채택. 5개 쟁점 전부 DA 설계 우선. BPA 유효 포인트 3건은 DA 설계에 이미 반영됨.

| 쟁점 | DA 결정 | BPA 대안 (기각) | 근거 |
|------|---------|-----------------|------|
| 금액 데이터 타입 | DOUBLE PRECISION | DECIMAL(18,4) | 기존 9테이블 패턴 일관성. 가상 매매 시뮬레이션이라 소수점 정밀도 이슈 무관 |
| 수수료 관리 | `portfolio_configs` 사용자 설정값 + `FeeCalculator` 기본값 | 별도 fee_rates 테이블 | 단일 사용자에서도 조정 가능성을 유지하면서 스키마 복잡도는 최소화 |
| 스케줄 완료 감지 | 이벤트 드리븐 (카운트 기반) | 폴링 (interval check) | 마지막 job 완료 시 active config 전체 카운트 비교. 즉시 반응 |
| 마이그레이션 | init_schema() + ensure_column | Alembic | 기존 패턴 일관성. 단일 사용자 시스템에서 Alembic 불필요 |
| API 프리픽스 | `/portfolio/*` (프리픽스 없음) | `/api/v1/portfolio/*` | 기존 엔드포인트에 프리픽스 없음. 일관성 우선 |

**BPA 유효 포인트 (DA 설계에 반영 완료):**
- 환율 스냅샷: `portfolio_trades.exchange_rate` + `portfolio_decisions.exchange_rate_snapshot` 저장
- fee_rates 검증: `portfolio_configs` 설정값 우선 + `FeeCalculator` 기본값 fallback 검증
- hung job 대응: 종목별 try/except + skip + error_message 기록, lock acquire timeout(600s)

### 10.16 Macro & Sector Context Injection (FR-062, FR-063)

#### 수집기 개요
- 모듈: `tradingagents/dataflows/macro_collector.py`
- 진입점: `collect_macro_context(ticker, market)`
- 호출 시점: `TickerScheduler._run_analysis_cycle_impl`에서 G-ANT 파이프라인 직전
- 출력 포맷: 프롬프트 주입용 텍스트 블록 (`AgentState.macro_context`)

#### 시장별 매크로 지표
| market | 지표 |
|---|---|
| `us` | `^VIX`, `^IRX`(3M T-Bill), `^TNX-^IRX` 스프레드, `^IXIC` 50/200일선 추세 |
| `kr` | `^VIX`(VKOSPI 대체), `USDKRW=X`, `^KS11` 50/200일선 추세 |
| `crypto` | `BTC-USD` 20일 변동성(연율화), `DX-Y.NYB`, BTC 시가총액 |

#### 섹터 컨텍스트
- 섹터 판별: `yf.Ticker(ticker).info["sector"]`
- US: 11개 섹터 ETF 매핑 (`XLK`~`XLU`)
- KR: 8개 섹터 ETF 매핑 (미매핑 섹터는 fallback 메시지)
- 계산: 상대강도(최근 1개월 수익률 차) + 50일선 대비 추세
- crypto: 섹터 블록 미주입 (매크로만 사용)

#### 캐시/장애 허용
- `_macro_cache`: 시장별 당일 1회 캐시
- `_sector_cache`: ETF별 당일 1회 캐시
- 지표 fetch 실패: 해당 지표 `N/A`
- 전체 실패: 빈 컨텍스트 반환, 파이프라인은 정상 진행

### 10.17 Portfolio API Governance (check+arch 반영)

#### 인증 경계
- 기본 정책: 단일 사용자 로컬 운영 기준으로 `/portfolio/*` READ 공개 유지
- hardening 옵션: `PORTFOLIO_READ_AUTH_REQUIRED=true`일 때 `/portfolio/*` GET에도 Bearer 인증 강제
- WRITE는 기존과 동일하게 Bearer 필수

#### 페이지네이션/정렬 규약
- `/portfolio/decisions`, `/portfolio/trades`, `/portfolio/reflections`: `id DESC` 기준 cursor 페이지네이션
- 기본 `limit=10`, 최대 `limit=100`
- `/portfolio/holdings`: 최신 snapshot(당일 또는 마지막 유효일) 집합 조회 API로 페이지네이션 없음

#### 버저닝/응답 호환성
- 엔드포인트 경로는 unversioned 유지 (`/portfolio/*`)
- 주요 JSON 응답에 `schema_version` 필드 추가 권장 (초기값 `"v1"`)
- breaking change는 필드 삭제 대신 필드 추가 방식으로 점진 확장

#### Rate Limit
- 앱 내부 강제 대신 게이트웨이/프록시 정책으로 관리
- 문서 계약값: `API_RATE_LIMIT_PER_MIN=120` (분당/IP 또는 토큰 기준)

### 10.18 External API Resilience for Portfolio

- **환율 조회** (`USDKRW=X`):
  - 2회 즉시 재시도 (백오프 없음)
  - 실패 시 마지막 캐시값 사용, 캐시 없음이면 `EXCHANGE_RATE_FALLBACK`
  - stale 캐시만 남은 경우 경고 로그를 남기고 실행 지속
- **종목 현재가 조회**:
  - 1회 조회 실패 시 해당 종목은 당일 매매에서 skip
  - 종목 단위 실패는 `error_message` 누적, 파이프라인 전체는 지속
- **실행 안전성**:
  - 외부 시세 실패가 발생해도 이미 완료된 종목 매매는 롤백하지 않음
  - 실패 목록은 decision 단위로 저장하고 다음 실행에서 재평가

### 10.19 Portfolio Idempotency & Recovery Contract

- **일일 의사결정 멱등성 키**: `(portfolio_config_id, decision_date)` UNIQUE 유지
- **상태 머신**: `pending -> executing -> completed | partial_failed | failed`
- **전체 티커 완료 트리거 조건(엄격 모드)**:
  - active schedule 기준 `done + skipped == total_active`
  - 같은 날짜의 `failed == 0`
  - 위 두 조건을 모두 만족할 때만 일일 포트폴리오 큐잉
- **`_on_all_tickers_complete()` 상세(이벤트 기반, 폴링 아님)**:
  1. `schedule_jobs` 상태 변경 이벤트(완료/스킵/실패) 수신
  2. active 티커 목록과 당일 상태 집계(`done`, `skipped`, `failed`) 계산
  3. 엄격 모드 조건 충족 시에만 `portfolio_daily` 작업 enqueue
  4. enqueue 전 `(config_id, decision_date)` 멱등성 키로 중복 실행 차단
  5. 조건 불충족 시 큐잉하지 않고 다음 이벤트를 대기
- **skipped 티커 처리 정책**:
  - skipped 티커는 **직전 리포트를 재사용하지 않음** (stale 데이터 주입 방지)
  - 브리핑에는 `"오늘 분석 없음 (데이터 미갱신)"`으로 명시
  - PortfolioManagerAgent 검증 단계에서 해당 티커는 `HOLD`로 강제해 기존 포지션 유지
- **재실행 규칙**:
  - `completed`: 동일 일자 재실행 금지
  - `partial_failed`: 실패 종목만 수동 재실행 허용
  - `failed`: 전체 재실행 허용
- **snapshot 정합성**:
  - 일일 실행 완료 시점에만 snapshot INSERT
  - 14일 이전 snapshot 정리는 실행 완료 후 수행

### 10.20 LLM Guardrails for v6 Agents

- 적용 대상: `BriefingAgent`, `PortfolioManagerAgent`, `PortfolioReflector`, `RetrospectiveService`
- timeout 기본값: 120초 (deep_think 호출은 180초까지 허용 가능)
- retry budget: parse 실패/일시 오류 최대 1회 재시도
- fallback:
  - JSON 파싱 실패 시 stricter prompt로 1회 재호출
  - 최종 실패 시 `failed` 또는 `partial_failed` 상태로 종료 (무한 재시도 금지)
- 출력 검증:
  - 점수형 필드(analysis_accuracy, rag_contribution, allocation_accuracy)는 0~100 클램핑
  - 배분 합계, 잔액 초과 여부를 실행 전 검증

### 10.21 Portfolio API Request/Response Schemas

#### POST `/portfolio/config` (Bearer)

```yaml
request:
  body:
    initial_capital: number            # 필수, > 0
    base_currency: "KRW" | "USD"       # 필수
    fee_enabled: boolean               # 선택, 기본 true
    fee_rates:                         # 선택, 미지정 시 DB 기본값 사용
      us_fee_rate: number              # 예: 0.001 (0.1%)
      kr_buy_fee_rate: number          # 예: 0.0025 (0.25%)
      kr_sell_fee_rate: number         # 예: 0.0025 (0.25%)
      kr_sell_tax_rate: number         # 예: 0.0018 (0.18%)
      crypto_fee_rate: number          # 예: 0.001 (0.1%)

response:
  200:
    schema_version: "v1"
    config:
      id: integer
      initial_capital: number
      total_fund: number
      available_cash: number
      base_currency: "KRW" | "USD"
      fee_enabled: boolean
      fee_rates:
        us_fee_rate: number
        kr_buy_fee_rate: number
        kr_sell_fee_rate: number
        kr_sell_tax_rate: number
        crypto_fee_rate: number
      status: "active" | "paused"
      created_at: string
      updated_at: string
errors:
  - 400 INVALID_INPUT
  - 401 UNAUTHORIZED
```

#### GET `/portfolio/holdings`

```yaml
response:
  200:
    schema_version: "v1"
    base_currency: "KRW" | "USD"
    snapshot_date: "YYYY-MM-DD"
    holdings:
      - ticker: string
        shares: number
        avg_cost: number               # ticker 원통화 기준
        currency: "KRW" | "USD"
        current_price: number | null   # ticker 원통화 기준 (조회 실패 시 null)
        current_value_local: number    # 원통화 기준 평가금액
        current_value_base: number     # base_currency 환산 평가금액
        allocation_pct: number
```

> 정책: `current_value_local`은 종목 원통화 기준, `current_value_base`는 기준통화(`base_currency`) 환산 값.

#### GET `/portfolio/decisions/{id}`

```yaml
response:
  200:
    schema_version: "v1"
    decision:
      id: integer
      decision_date: "YYYY-MM-DD"
      status: "pending" | "executing" | "completed" | "partial_failed" | "failed"
      briefing_summary: object | null
      rationale: string | null
      allocation_plan:
        - ticker: string
          action: "BUY" | "SELL" | "HOLD"
          allocation_pct: number
          shares: number
          rationale: string | null
      total_fund_snapshot: number
      available_cash_snapshot: number
      exchange_rate_snapshot: number | null
      error_message: string | null
      created_at: string
    trades:
      - id: integer
        ticker: string
        action: "buy" | "sell" | "hold"
        shares: number
        price: number
        currency: "KRW" | "USD"
        fee_rate: number
        fee_amount: number
        amount_local: number
        amount_krw: number
        executed_at: string
errors:
  - 404 NOT_FOUND
```

### ⚠️ TBD (Skipped)

| 항목 | 사유 |
|------|------|
| DB 백업 자동화 | Supabase 자체 백업 사용 |
| CORS origins 제한 | Cloudflare 도메인 확보 후 설정 |
| interval_days 격일 스케줄 | 당분간 1(매일) 고정. 향후 `current_cycle % interval_days != 0` 스킵 방식 |
| 사용자 initial_capital 설정 UI | 현재 고정값 (USD $5,000 / KRW ₩5,000,000). 향후 확장 대비 DB 저장 |
| reflections.usefulness_score 인덱스 | 초기 데이터 소량. 대량 축적 시 부분 인덱스 (`WHERE usefulness_score >= 40`) 검토 |
| RAG Validator 자동 트리거 | 수동만 지원. 회고분석 완료 후 자동 실행은 데이터 축적 후 판단 |
