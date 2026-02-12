# Backend Design Doc: TradingAgents Draft Features (FR-013~019)

> Created: 2026-02-11
> Updated: 2026-02-12
> Service: tradingagents
> Type: Backend
> Requirements document: docs/tradingagents/spec.md

## 0. Summary

### Goal

기존 TradingAgents 멀티에이전트 분석 파이프라인에 **영속 메모리(Hybrid RAG)**, **가상 매매 검증**, **스케줄 기반 자동화**를 추가하여, AI 분석의 정확도를 정량적으로 추적·학습하는 자기 개선 시스템으로 진화시킨다.

### Non-goals

- 실제 증권사 API 연동 (가상 매매만)
- 웹 UI/대시보드 (CLI 기반 유지)
- 멀티유저/멀티전략 지원 (단일 사용자)
- 실시간 데이터 스트리밍 (분석 시점 1회성 fetch 유지)

### Success metrics

- 메모리 영속성: 프로세스 재시작 후 기존 메모리 100% 복원
- 가상 매매: 티커별 trade.json에 완전한 매매 이력 기록
- 학습 효과: has_memory=true vs false 분석 결과 비교 가능
- 스케줄: 지정 주기대로 자동 분석 실행, 1시간 이내 완료

---

## 1. Scope

### In scope

- FR-015: Hybrid RAG Memory (BM25 + Vector, chromadb 내장 ONNX 임베딩)
- FR-018: 구조화된 reflect_and_remember 입력
- FR-019: Bootstrap 태깅 (has_memory 플래그)
- FR-013: 가상 매매 추적 (trade.json / reports.json)
- FR-014: Portfolio Agent (독립 에이전트, LangGraph 외부)
- FR-016: APScheduler 기반 티커별 스케줄링
- FR-017: AgentState에 current_position 추가, 에이전트 프롬프트 주입

### Out of scope

- Pydantic 기반 설정 마이그레이션 (기존 dict 유지)
- 멀티스레드 병렬 분석 (순차 실행 유지)
- SQLite 기반 스케줄러 영속성 (인메모리 + 셀프힐링)
- Event Sourcing / CQRS 패턴 (단일 TradeManager 유지)

---

## 1.5. Tech Stack

```yaml
tech_stack:
  project_structure: "Monolith"
  be_path: "./"
  run_command: "uv run python main.py"
  language: "Python 3.10+"
  framework: "LangGraph (langgraph>=0.4.8)"
  database: "None (file-based: JSON/JSONL)"
  orm: "None (Raw JSON I/O)"
  package_manager: "uv"
  third_party:
    - "chromadb (Vector Store + Built-in ONNX Embedding)"
    - "apscheduler (Job Scheduling)"
    - "rank-bm25 (BM25 Search)"
    - "yfinance (Market Data)"
    - "langchain-core (LLM Abstraction)"
  infra: "Local / WSL2 Ubuntu 22.04"
```

---

## 1.6. Dependencies

```yaml
package_manager: "uv"
project_type: "existing"

dependencies:
  # Existing (already in pyproject.toml)
  - name: "langchain-core"
    version: ">=0.3.81"
    purpose: "LLM abstraction layer"
    status: "approved"
  - name: "langgraph"
    version: ">=0.4.8"
    purpose: "Graph-based agent orchestration"
    status: "approved"
  - name: "rank-bm25"
    version: ">=0.2.2"
    purpose: "BM25 lexical search (Hybrid RAG의 BM25 경로)"
    status: "approved"
  - name: "yfinance"
    version: ">=0.2.63"
    purpose: "시장 데이터 fetch"
    status: "approved"

  # NEW — FR-015: Hybrid RAG
  - name: "chromadb"
    version: ">=1.5.0"
    purpose: "Vector store + 내장 임베딩 (all-MiniLM-L6-v2, ONNX Runtime)"
    status: "approved"

  # NEW — FR-016: Scheduling
  - name: "apscheduler"
    version: ">=3.11.2"
    purpose: "티커별 주기적 분석 스케줄링"
    status: "approved"
```

---

## 2. Architecture Impact

### Components

| Service / Module                                    | Responsibility                                                                 | Change type |
| --------------------------------------------------- | ------------------------------------------------------------------------------ | ----------- |
| `tradingagents/memory/`                             | Hybrid RAG Memory (BM25+Vector via ChromaDB 내장 임베딩), 영속성, RRF 스코어링 | **new**     |
| `tradingagents/virtual_trade/`                      | 가상 매매 관리, Portfolio Agent, 리포트 저장                                   | **new**     |
| `tradingagents/scheduler/`                          | APScheduler 기반 티커별 자동 분석                                              | **new**     |
| `tradingagents/graph/trading_graph.py`              | HybridMemory 도입, 구조화 반성, position 주입                                  | modify      |
| `tradingagents/graph/reflection.py`                 | 구조화된 입력 처리, 프롬프트 확장                                              | modify      |
| `tradingagents/graph/propagation.py`                | current_position 파라미터 추가                                                 | modify      |
| `tradingagents/agents/utils/agent_states.py`        | current_position 필드 추가                                                     | modify      |
| `tradingagents/agents/managers/research_manager.py` | 포지션 컨텍스트 프롬프트 주입                                                  | modify      |
| `tradingagents/agents/trader/trader.py`             | 포지션 컨텍스트 프롬프트 주입                                                  | modify      |
| `tradingagents/agents/managers/risk_manager.py`     | 포지션 컨텍스트 프롬프트 주입                                                  | modify      |
| `tradingagents/agents/__init__.py`                  | HybridMemory 재수출 (backward compat)                                          | modify      |
| `tradingagents/default_config.py`                   | 메모리/가상매매/스케줄러 설정 추가                                             | modify      |
| `pyproject.toml`                                    | chromadb, apscheduler 의존성                                                   | modify      |

### Data

#### File-Based Storage Schema

이 프로젝트는 전통적 DB를 사용하지 않으며, 모든 데이터는 JSON/JSONL 파일로 영속화합니다.

```yaml
file_storage:
  # FR-015: Hybrid RAG Memory
  memory_files:
    - path: "memory/data/{agent_name}.jsonl"
      format: "JSONL (append-only)"
      description: "BM25 corpus — source of truth. 한 줄 = 하나의 situation+recommendation"
      schema_per_line:
        situation: "string — 시장 상황 텍스트"
        recommendation: "string — LLM 반성문/조언"
        metadata:
          ticker: "string (optional)"
          return_pct: "float (optional)"
          has_memory: "boolean (optional)"
          created_at: "ISO 8601 timestamp"
          schema_version: "int (1)"
    - path: "memory/data/chroma/{agent_name}/"
      format: "ChromaDB PersistentClient directory"
      description: "Vector index — derived data. JSONL에서 재구축 가능"

  # FR-013: Virtual Trading
  trade_files:
    - path: "virtual_trade/tickers/{TICKER}/trade.json"
      format: "JSON"
      description: "티커별 매매 상태 + 이력"
      schema:
        ticker: "string"
        initial_capital: "float (default 1000.0)"
        cash: "float"
        status: "string — open | closed"
        positions:
          - shares: "int"
            entry_price: "float"
            entry_date: "string (YYYY-MM-DD)"
        strategy:
          stop_loss: "float (nullable)"
          target: "float (nullable)"
          next_action: "string"
        history:
          - date: "string (YYYY-MM-DD)"
            analysis_no: "int"
            decision: "string — BUY | SELL | HOLD"
            action: "string"
            rationale: "string"
            cash_after: "float"
        # 청산 시 추가 필드
        closed_date: "string (nullable)"
        realized_return_pct: "float (nullable)"
        total_invested: "float (nullable)"
        total_returned: "float (nullable)"
        profit: "float (nullable)"

    - path: "virtual_trade/tickers/{TICKER}/reports.json"
      format: "JSON array"
      description: "분석 이력. G-ANT 파이프라인 1회 실행의 요약"
      schema_per_entry:
        date: "string (YYYY-MM-DD)"
        analysis_no: "int"
        decision: "string — BUY | SELL | HOLD"
        strategy_summary: "string"
        has_memory: "boolean"
        state_summary:
          market_report_excerpt: "string (first 500 chars)"
          final_decision_excerpt: "string (first 500 chars)"

  # Agent name enumeration
  agent_names:
    - "bull_memory"
    - "bear_memory"
    - "trader_memory"
    - "invest_judge_memory"
    - "risk_manager_memory"
```

#### Directory Structure (Runtime)

```
tradingagents/
├── memory/
│   └── data/
│       ├── bull_memory.jsonl
│       ├── bear_memory.jsonl
│       ├── trader_memory.jsonl
│       ├── invest_judge_memory.jsonl
│       ├── risk_manager_memory.jsonl
│       └── chroma/
│           ├── bull_memory/
│           ├── bear_memory/
│           ├── trader_memory/
│           ├── invest_judge_memory/
│           └── risk_manager_memory/
│
└── (project_root)/
    └── virtual_trade/
        └── tickers/
            ├── NVDA/
            │   ├── trade.json
            │   └── reports.json
            └── AAPL/
                ├── trade.json
                └── reports.json
```

---

## 3. Code Mapping

| #   | Spec Ref | Feature                        | File                                                | Class                | Method                                                                                                                                                            | Action                                                                                                                 | Impl |
| --- | -------- | ------------------------------ | --------------------------------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---- |
| 1   | FR-015   | HybridMemory 모듈 init         | `tradingagents/memory/__init__.py`                  | —                    | —                                                                                                                                                                 | 새 모듈 생성, `HybridMemory` 재수출                                                                                    | [x]  |
| 2   | FR-015   | HybridMemory 클래스            | `tradingagents/memory/hybrid_memory.py`             | `HybridMemory`       | `__init__`, `add_situations`, `get_memories`, `clear`, `_load_corpus`, `_save_entry`, `_rebuild_bm25`, `_get_or_create_collection`, `_rrf_fusion`                 | 새 파일: BM25+Vector Hybrid Memory, RRF 스코어링, JSONL 영속성, ChromaDB PersistentClient                              | [x]  |
| 3   | FR-015   | backward compat 재수출         | `tradingagents/agents/__init__.py`                  | —                    | —                                                                                                                                                                 | `from tradingagents.memory.hybrid_memory import HybridMemory as FinancialSituationMemory` 로 변경                      | [x]  |
| 4   | FR-015   | TradingAgentsGraph 메모리 교체 | `tradingagents/graph/trading_graph.py`              | `TradingAgentsGraph` | `__init__`                                                                                                                                                        | `FinancialSituationMemory` → `HybridMemory` import 변경, 5개 인스턴스 생성 시 config 전달                              | [x]  |
| 5   | FR-015   | 의존성 추가                    | `pyproject.toml`                                    | —                    | —                                                                                                                                                                 | dependencies에 `chromadb` 추가 (자체 임베딩 엔진 사용)                                                                 | [x]  |
| 6   | FR-018   | 구조화된 반성 입력             | `tradingagents/graph/trading_graph.py`              | `TradingAgentsGraph` | `reflect_and_remember`                                                                                                                                            | 시그니처 `(self, returns_losses)` 유지하되 `Union[int, float, dict]` 처리. 숫자 입력 시 `{"return_pct": value}`로 래핑 | [x]  |
| 7   | FR-018   | Reflector 프롬프트 확장        | `tradingagents/graph/reflection.py`                 | `Reflector`          | `_reflect_on_component`                                                                                                                                           | 구조화된 context 블록 추가 (ticker, return_pct, holding_days 등)                                                       | [x]  |
| 8   | FR-018   | JSONL 메타데이터 저장          | `tradingagents/memory/hybrid_memory.py`             | `HybridMemory`       | `add_situations`                                                                                                                                                  | 각 엔트리에 metadata (ticker, return_pct, has_memory, schema_version) 함께 저장                                        | [x]  |
| 9   | FR-019   | Bootstrap 태깅                 | `tradingagents/graph/trading_graph.py`              | `TradingAgentsGraph` | `propagate`                                                                                                                                                       | 실행 후 `self._last_had_memory` 플래그 설정 (메모리 쿼리 결과 기반)                                                    | [x]  |
| 10  | FR-019   | 메모리 쿼리 결과 추적          | `tradingagents/memory/hybrid_memory.py`             | `HybridMemory`       | `get_memories`                                                                                                                                                    | 반환값에 결과 수 포함 + `self.last_query_had_results: bool` 플래그 설정                                                | [x]  |
| 11  | FR-013   | TradeManager 모듈              | `tradingagents/virtual_trade/__init__.py`           | —                    | —                                                                                                                                                                 | 새 모듈 생성                                                                                                           | [x]  |
| 12  | FR-013   | TradeManager 클래스            | `tradingagents/virtual_trade/trade_manager.py`      | `TradeManager`       | `__init__`, `load`, `save`, `create_initial_trade`, `open_position`, `close_all_positions`, `get_position_summary`, `calculate_realized_return`, `append_history` | 새 파일: trade.json CRUD, 원자적 쓰기 (tmp+rename)                                                                     | [x]  |
| 13  | FR-013   | ReportStore 클래스             | `tradingagents/virtual_trade/report_store.py`       | `ReportStore`        | `__init__`, `append`, `load`, `get_analysis_count`                                                                                                                | 새 파일: reports.json 관리 (JSON array append)                                                                         | [x]  |
| 14  | FR-014   | Portfolio Agent                | `tradingagents/virtual_trade/portfolio_agent.py`    | `PortfolioAgent`     | `__init__`, `decide`                                                                                                                                              | 새 파일: deep_think_llm 사용, trade.json+reports.json 읽기, maintain/modify/abandon 결정                               | [ ]  |
| 15  | FR-016   | TickerScheduler 모듈           | `tradingagents/scheduler/__init__.py`               | —                    | —                                                                                                                                                                 | 새 모듈 생성                                                                                                           | [ ]  |
| 16  | FR-016   | TickerScheduler 클래스         | `tradingagents/scheduler/ticker_scheduler.py`       | `TickerScheduler`    | `__init__`, `add_ticker`, `remove_ticker`, `start`, `stop`, `list_schedules`, `_run_analysis_cycle`, `_self_heal`                                                 | 새 파일: APScheduler BackgroundScheduler 래퍼, per-ticker IntervalTrigger                                              | [ ]  |
| 17  | FR-016   | 의존성 추가                    | `pyproject.toml`                                    | —                    | —                                                                                                                                                                 | dependencies에 `apscheduler` 추가                                                                                      | [x]  |
| 18  | FR-017   | AgentState 필드 추가           | `tradingagents/agents/utils/agent_states.py`        | `AgentState`         | —                                                                                                                                                                 | `current_position: Annotated[str, "Current virtual trading position summary"]` 추가                                    | [ ]  |
| 19  | FR-017   | Propagator 파라미터 추가       | `tradingagents/graph/propagation.py`                | `Propagator`         | `create_initial_state`                                                                                                                                            | `current_position: str = ""` 파라미터 추가, initial state dict에 포함                                                  | [ ]  |
| 20  | FR-017   | Research Manager 포지션 주입   | `tradingagents/agents/managers/research_manager.py` | —                    | `research_manager_node`                                                                                                                                           | 프롬프트에 `state.get("current_position", "")` 주입: "Current Trading Position: {position}"                            | [ ]  |
| 21  | FR-017   | Trader 포지션 주입             | `tradingagents/agents/trader/trader.py`             | —                    | `trader_node`                                                                                                                                                     | system prompt에 current_position 컨텍스트 추가                                                                         | [ ]  |
| 22  | FR-017   | Risk Manager 포지션 주입       | `tradingagents/agents/managers/risk_manager.py`     | —                    | `risk_manager_node`                                                                                                                                               | 프롬프트에 current_position 컨텍스트 추가                                                                              | [ ]  |
| 23  | FR-017   | TradingAgentsGraph 포지션 전달 | `tradingagents/graph/trading_graph.py`              | `TradingAgentsGraph` | `propagate`                                                                                                                                                       | `current_position` 파라미터 추가, Propagator에 전달                                                                    | [ ]  |
| 24  | ALL      | DEFAULT_CONFIG 확장            | `tradingagents/default_config.py`                   | —                    | —                                                                                                                                                                 | memory_dir, virtual_trade_dir, default_initial_capital, schedules, scheduler_enabled 추가                              | [ ]  |

> **Spec Ref**: spec.md의 Req ID에 대응 (1 Req ID → 복수 Code Mapping 가능)
> **Impl column**: `[ ]` = not implemented, `[x]` = implemented (build 후 업데이트)

---

## 4. Implementation Plan

### 📂 Required Reference Files (Must read before implementation)

| File                                                | Reference Purpose                                                    |
| --------------------------------------------------- | -------------------------------------------------------------------- |
| `tradingagents/agents/utils/memory.py`              | 기존 BM25 메모리 인터페이스 확인 — HybridMemory가 동일 API 유지 필수 |
| `tradingagents/graph/trading_graph.py`              | 메모리 초기화, propagate(), reflect_and_remember() 패턴 확인         |
| `tradingagents/graph/reflection.py`                 | Reflector 프롬프트 구조 + 5개 reflect 메서드 패턴 확인               |
| `tradingagents/agents/managers/research_manager.py` | 프롬프트 주입 패턴 확인 (포지션 컨텍스트 추가 위치)                  |
| `tradingagents/agents/trader/trader.py`             | system prompt 패턴 확인                                              |
| `tradingagents/agents/managers/risk_manager.py`     | 프롬프트 패턴 확인                                                   |
| `tradingagents/graph/propagation.py`                | create_initial_state 시그니처 확인                                   |
| `tradingagents/agents/__init__.py`                  | 재수출 패턴 확인                                                     |
| `tradingagents/default_config.py`                   | 기존 config 키 구조 확인                                             |

⚠️ **When running build skill, read above files first to understand patterns**

### Step-by-Step Implementation

1. **Step 1: HybridMemory 클래스 구현 (FR-015)**
   - `tradingagents/memory/__init__.py` 생성
   - `tradingagents/memory/hybrid_memory.py` 구현
     - BM25 경로: 기존 `memory.py`의 `_tokenize`, `_rebuild_index` 로직 그대로 복사
     - Vector 경로: `chromadb.PersistentClient` + 내장 ONNX 임베딩 (`all-MiniLM-L6-v2`)
     - RRF 스코어링: `rrf_score(d) = sum(1 / (60 + rank_i(d)))` for each retriever
     - JSONL 영속성: `add_situations()` 시 append, `__init__` 시 load + BM25 rebuild
     - Lazy init: ChromaDB는 첫 `get_memories()` 호출 시 초기화
     - Graceful degradation: ChromaDB 로드 실패 시 BM25-only 모드로 fallback (경고 로그)
   - `tradingagents/agents/__init__.py` 수정: `HybridMemory as FinancialSituationMemory` 재수출
   - `tradingagents/graph/trading_graph.py` 수정: import 변경
   - `pyproject.toml` 수정: `chromadb` 추가 (완료)

2. **Step 2: 구조화된 학습 + Bootstrap 태깅 (FR-018, FR-019)**
   - `tradingagents/graph/trading_graph.py` — `reflect_and_remember()` 시그니처 변경
     - `Union[int, float, dict]` 처리, 숫자 시 `{"return_pct": value}` 래핑
   - `tradingagents/graph/reflection.py` — 프롬프트에 구조화 context 블록 추가
   - `tradingagents/memory/hybrid_memory.py` — `add_situations()` 에 metadata 저장
   - `tradingagents/graph/trading_graph.py` — `propagate()` 후 `_last_had_memory` 플래그 설정

3. **Step 3: 가상 매매 모듈 (FR-013)**
   - `tradingagents/virtual_trade/__init__.py` 생성
   - `tradingagents/virtual_trade/trade_manager.py` 구현
     - JSON CRUD, 원자적 쓰기 (tmp + `os.replace()`), 수익률 계산
   - `tradingagents/virtual_trade/report_store.py` 구현
     - reports.json array append/read

4. **Step 4: Portfolio Agent (FR-014)**
   - `tradingagents/virtual_trade/portfolio_agent.py` 구현
     - `deep_think_llm` 사용, trade.json + reports.json 읽기
     - 프롬프트: 현재 포지션 + 최신 분석 + 과거 이력 → maintain/modify/abandon 결정
     - 수동 호출로 먼저 프롬프트 품질 검증 후 스케줄러에 연결

5. **Step 5: 스케줄러 (FR-016)**
   - `tradingagents/scheduler/__init__.py` 생성
   - `tradingagents/scheduler/ticker_scheduler.py` 구현
     - APScheduler `BackgroundScheduler` + `IntervalTrigger`
     - `_run_analysis_cycle()`: load → propagate → report → portfolio → trade → reflect
     - Per-ticker `threading.Lock` (timeout=600초)
     - Self-healing: 시작 시 config + virtual_trade/tickers/ 스캔
     - 단순 재시도: 예외 시 1회 retry, 실패 시 로깅
   - `pyproject.toml`: `apscheduler` 추가 (완료)

6. **Step 6: Position-Aware Analysis (FR-017)**
   - `tradingagents/agents/utils/agent_states.py` — `current_position: str` 추가
   - `tradingagents/graph/propagation.py` — `current_position` 파라미터 추가
   - `tradingagents/agents/managers/research_manager.py` — 프롬프트 주입
   - `tradingagents/agents/trader/trader.py` — system prompt 주입
   - `tradingagents/agents/managers/risk_manager.py` — 프롬프트 주입
   - `tradingagents/graph/trading_graph.py` — `propagate()` 에 `current_position` 파라미터

7. **Step 7: Config 업데이트**
   - `tradingagents/default_config.py` — 모든 새 설정 키 추가

---

## 5. Sequence Diagram

### 5.1 스케줄 기반 분석 사이클 (Full Flow)

```mermaid
sequenceDiagram
    participant Scheduler as TickerScheduler
    participant TM as TradeManager
    participant RS as ReportStore
    participant Graph as TradingAgentsGraph
    participant PA as PortfolioAgent
    participant Mem as HybridMemory
    participant Ref as Reflector

    Scheduler->>TM: load(ticker)
    TM-->>Scheduler: trade_state + position_summary

    Scheduler->>Graph: propagate(ticker, today, depth, current_position)
    Note over Graph: LangGraph Pipeline 실행<br/>(Analysts → Debate → Trader → Risk)
    Graph->>Mem: get_memories(situation) [각 에이전트]
    Mem-->>Graph: matched memories + had_results flag
    Graph-->>Scheduler: final_state, decision

    Scheduler->>RS: append(ticker, report_entry)
    RS-->>Scheduler: ok

    Scheduler->>PA: decide(ticker, decision, final_state)
    Note over PA: trade.json + reports.json 읽기<br/>→ maintain/modify/abandon 결정
    PA-->>Scheduler: {action, rationale, strategy_update}

    alt action = BUY
        Scheduler->>TM: open_position(shares, price, date)
        TM-->>Scheduler: updated trade_state
    else action = SELL
        Scheduler->>TM: close_all_positions(current_price, date)
        TM-->>Scheduler: realized_return
        Scheduler->>Graph: reflect_and_remember(structured_dict)
        Graph->>Ref: _reflect_on_component(structured_context)
        Ref->>Mem: add_situations([(situation, reflection)])
        Mem-->>Ref: persisted to JSONL + ChromaDB
    else action = HOLD
        Scheduler->>TM: append_history(hold_entry)
    end

    Scheduler->>TM: save(ticker)
```

### 5.2 HybridMemory 검색 흐름 (RRF)

```mermaid
sequenceDiagram
    participant Agent as Agent Node
    participant HM as HybridMemory
    participant BM25 as BM25 Index
    participant Chroma as ChromaDB (내장 ONNX 임베딩)

    Agent->>HM: get_memories(situation, n=2)

    par BM25 경로
        HM->>BM25: get_scores(tokenize(situation))
        BM25-->>HM: scores[] → rank by score
    and Vector 경로
        HM->>Chroma: query(documents=[situation], n_results=10)
        Note over Chroma: 내장 all-MiniLM-L6-v2 ONNX로 자동 임베딩
        Chroma-->>HM: results[] → rank by distance
    end

    Note over HM: RRF Fusion<br/>rrf(d) = Σ 1/(60 + rank_i(d))
    HM-->>Agent: top-N results sorted by RRF score
```

---

## 6. API Specification

> 이 프로젝트는 HTTP API 서버가 아닌 Python 라이브러리입니다.
> 아래는 공개 Python 인터페이스 명세입니다.

### 6.1 HybridMemory (FR-015)

```yaml
python_api:
  - name: "HybridMemory"
    module: "tradingagents.memory.hybrid_memory"
    description: "BM25+Vector Hybrid RAG Memory with JSONL persistence"
    constructor:
      params:
        - name: "name"
          type: "str"
          required: true
          description: "메모리 인스턴스 이름 (e.g., 'bull_memory')"
        - name: "config"
          type: "dict"
          required: false
          description: "설정 dict (memory_dir 사용)"
    methods:
      - name: "add_situations"
        params:
          - name: "situations_and_advice"
            type: "List[Tuple[str, str]]"
            description: "(situation, recommendation) 쌍 리스트"
          - name: "metadata"
            type: "dict"
            required: false
            description: "저장할 메타데이터 (ticker, return_pct, has_memory, schema_version)"
        returns: "None"
        description: "BM25 corpus(JSONL) + ChromaDB에 동시 추가"
      - name: "get_memories"
        params:
          - name: "current_situation"
            type: "str"
            description: "검색 쿼리 (현재 시장 상황)"
          - name: "n_matches"
            type: "int"
            default: 1
            description: "반환할 매치 수"
        returns: "List[dict] — {matched_situation, recommendation, rrf_score}"
        description: "RRF로 BM25+Vector 결과 융합, top-N 반환"
      - name: "clear"
        returns: "None"
        description: "메모리 초기화 (JSONL + ChromaDB 모두)"
```

### 6.2 TradingAgentsGraph 변경사항 (FR-017, FR-018)

```yaml
python_api:
  - name: "TradingAgentsGraph.propagate"
    changes: "current_position 파라미터 추가"
    params:
      - name: "company_name"
        type: "str"
      - name: "trade_date"
        type: "str"
      - name: "depth"
        type: "int"
        required: false
      - name: "current_position"
        type: "str"
        default: '""'
        description: "가상 매매 포지션 요약 (e.g., 'Holding 2 shares NVDA avg $257.50')"
    returns: "Tuple[dict, str] — (final_state, decision)"

  - name: "TradingAgentsGraph.reflect_and_remember"
    changes: "Union[int, float, dict] 입력 지원"
    params:
      - name: "returns_losses"
        type: "Union[int, float, dict]"
        description: |
          숫자: backward compat — {"return_pct": value}로 래핑
          dict: 구조화된 입력
            {
              "ticker": str,
              "return_pct": float,
              "holding_days": int,
              "analysis_count": int,
              "market_condition": str,
              "has_memory": bool,
              "schema_version": 1
            }
    returns: "None"
```

### 6.3 TradeManager (FR-013)

```yaml
python_api:
  - name: "TradeManager"
    module: "tradingagents.virtual_trade.trade_manager"
    constructor:
      params:
        - name: "base_dir"
          type: "str"
          description: "virtual_trade/tickers/ 기본 경로"
    methods:
      - name: "load"
        params: [{ name: "ticker", type: "str" }]
        returns: "dict — trade.json 내용"
      - name: "save"
        params: [{ name: "ticker", type: "str" }]
        returns: "None"
        description: "원자적 쓰기 (tmp + os.replace)"
      - name: "create_initial_trade"
        params:
          - { name: "ticker", type: "str" }
          - { name: "initial_capital", type: "float", default: 1000.0 }
        returns: "dict — 초기 trade.json"
      - name: "open_position"
        params:
          - { name: "ticker", type: "str" }
          - { name: "shares", type: "int" }
          - { name: "price", type: "float" }
          - { name: "date", type: "str" }
        returns: "dict — updated trade state"
      - name: "close_all_positions"
        params:
          - { name: "ticker", type: "str" }
          - { name: "current_price", type: "float" }
          - { name: "date", type: "str" }
        returns: "dict — {realized_return_pct, profit, total_invested, total_returned}"
      - name: "get_position_summary"
        params: [{ name: "ticker", type: "str" }]
        returns: "str — 포지션 요약 (e.g., 'Holding 2 shares NVDA avg $257.50')"
```

### 6.4 PortfolioAgent (FR-014)

```yaml
python_api:
  - name: "PortfolioAgent"
    module: "tradingagents.virtual_trade.portfolio_agent"
    constructor:
      params:
        - { name: "llm", type: "BaseChatModel", description: "deep_think_llm" }
        - { name: "trade_manager", type: "TradeManager" }
        - { name: "report_store", type: "ReportStore" }
    methods:
      - name: "decide"
        params:
          - { name: "ticker", type: "str" }
          - {
              name: "pipeline_decision",
              type: "str",
              description: "BUY/SELL/HOLD",
            }
          - {
              name: "pipeline_state",
              type: "dict",
              description: "propagate() 반환 final_state",
            }
        returns: |
          dict — {
            "action": "BUY | SELL | HOLD | MODIFY",
            "shares": int,           # BUY 시 매수 수량 (LLM이 cash 잔고 기반으로 결정)
            "rationale": str,
            "strategy_update": dict
          }
        notes: |
          매수 수량은 PortfolioAgent LLM이 결정.
          프롬프트에 현재 cash 잔고 + 현재가를 포함하여 LLM이 적정 수량 산출.
          current_price는 yfinance 당일 종가: yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
```

### 6.5 TickerScheduler (FR-016)

```yaml
python_api:
  - name: "TickerScheduler"
    module: "tradingagents.scheduler.ticker_scheduler"
    constructor:
      params:
        - { name: "graph", type: "TradingAgentsGraph" }
        - { name: "config", type: "dict" }
    methods:
      - name: "add_ticker"
        params:
          - { name: "ticker", type: "str" }
          - { name: "interval_days", type: "int", default: 4 }
          - { name: "initial_capital", type: "float", default: 1000.0 }
        returns: "None"
      - name: "remove_ticker"
        params: [{ name: "ticker", type: "str" }]
        returns: "None"
      - name: "start"
        returns: "None"
        description: "스케줄러 시작 + self-heal 스캔"
      - name: "stop"
        returns: "None"
        description: "즉시 중단 (scheduler.shutdown(wait=False)). 원자적 쓰기로 파일 안전성 보장"
      - name: "list_schedules"
        returns: "List[dict] — 활성 스케줄 목록"
```

---

## 7. Infra/Ops

### Environment Variables

| Variable                    | Description                                   | Default                                |
| --------------------------- | --------------------------------------------- | -------------------------------------- |
| `LLM_PROVIDER`              | LLM 프로바이더 (`gemini-cli` / `antigravity`) | `gemini-cli`                           |
| `TRADINGAGENTS_RESULTS_DIR` | 분석 결과 저장 경로                           | `./results`                            |
| `TRADINGAGENTS_MEMORY_DIR`  | 메모리 데이터 경로 (override)                 | `<project_dir>/memory/data`            |
| `TRADINGAGENTS_TRADE_DIR`   | 가상 매매 데이터 경로 (override)              | `<project_root>/virtual_trade/tickers` |

### Config 추가 키 (DEFAULT_CONFIG)

```python
# Memory (FR-015)
"memory_dir": os.path.join(PROJECT_DIR, "memory/data"),

# Virtual Trading (FR-013)
"virtual_trade_dir": os.path.join(os.path.dirname(PROJECT_DIR), "virtual_trade/tickers"),
"default_initial_capital": 1000.0,

# Scheduler (FR-016)
"schedules": [],  # List[{"ticker": str, "interval_days": int, "initial_capital": float}]
"scheduler_enabled": False,
```

### Deployment Changes

- `uv add chromadb apscheduler` 실행 필요 (완료)
- 첫 실행 시 ChromaDB가 `all-MiniLM-L6-v2` ONNX 모델 자동 다운로드 (~80MB, 1회)
- `memory/data/` 및 `virtual_trade/tickers/` 디렉토리는 자동 생성 (makedirs)

---

## 8. Risks & Tradeoffs (Debate Conclusion)

### Chosen Option

- **Domain Architect 방안 채택**: 프로젝트 현실(10 티커, 단일 사용자, 4일 간격)에 맞는 실용적 설계
- **BPA에서 수용**: RRF 스코어링, JSONL 영속성, 원자적 쓰기, schema_version, 우아한 실패 처리

### Rejected Alternatives

| 제안                             | 거부 사유                                                                             |
| -------------------------------- | ------------------------------------------------------------------------------------- |
| Event Sourcing / CQRS (가상매매) | 1 ticker에 4일에 1회 쓰기. 4개 클래스 분리는 과도한 추상화                            |
| Pydantic Settings                | 기존 10+파일이 `config["key"]` 패턴 사용. 전면 리팩토링 비용 > 이득                   |
| SQLiteJobStore (APScheduler)     | 스케줄은 config에 정의. 재시작 시 config에서 재생성. SQLite 불필요                    |
| TypedDict V1→V2 버저닝           | AgentState는 일시적 (propagate 동안만 존재). 영속 데이터 아님                         |
| ThreadPoolExecutor 병렬화        | TradingAgentsGraph에 공유 mutable state (curr_state, ticker 등). 스레드 안전성 미확보 |
| Per-role LLM Config              | 현재 2-tier (deep/quick) 모델로 충분. 10+개 config 키 추가는 불필요한 복잡성          |
| Linear alpha blending (메모리)   | BM25/cosine 스코어 분포 비대칭 문제. RRF가 파라미터 프리로 우월                       |

### Reasoning

- **프로젝트 제약**: 단일 사용자, 10 티커 미만, 로컬 실행. Enterprise 패턴은 과도
- **Best Practice 수용**: RRF, JSONL, 원자적 쓰기, schema_version — 비용 대비 효과 높은 항목만 선별 채택
- **향후 개선 시점**: 멀티유저/100+ 티커 시 Pydantic 마이그레이션, 병렬화, SQLite 검토

### Assumptions

- **Confirmed**: RRF k=60 상수는 IR 문헌 표준값 (Cormack et al., 2009)
- **Confirmed**: all-MiniLM-L6-v2는 속도/품질 밸런스 최적 (~80MB, CPU 가능)
- **Confirmed**: ChromaDB PersistentClient는 HNSW 기반, 1M 문서까지 스케일
- **Estimated**: 포지션 주입이 Research Manager/Trader/Risk Manager에만 필요 (분석가는 객관성 유지). 실제 프롬프트 테스트로 검증 필요
- **Estimated**: Portfolio Agent 프롬프트 품질은 수동 테스트 후 스케줄러에 연결해야 함

---

## 9. Error/Auth/Data Checklist (3 Essential Checks)

### Error Handling

| Situation                                      | Location                                 | Handling Method                                                          | Response                                                                    |
| ---------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| ChromaDB 로드 실패 (import error, 디스크 오류) | `HybridMemory.__init__`                  | try/except → BM25-only fallback + `logging.warning`                      | 메모리 기능 degraded (벡터 검색 없이 동작)                                  |
| ChromaDB ONNX 모델 다운로드 실패               | `HybridMemory._lazy_init_vector`         | try/except → BM25-only fallback + 경고                                   | 메모리 기능 degraded                                                        |
| JSONL 파일 손상 (불완전한 줄)                  | `HybridMemory._load_corpus`              | 줄 단위 파싱, 실패 줄 skip + 경고                                        | 손상 줄 제외 후 나머지 로드                                                 |
| ChromaDB 인덱스 손상                           | `HybridMemory.get_memories`              | 예외 시 BM25-only 결과 반환 + JSONL에서 chroma 재구축 예약               | 일시적 degraded                                                             |
| trade.json 쓰기 중 프로세스 종료               | `TradeManager.save`                      | 원자적 쓰기 (tmp + `os.replace()`)                                       | 기존 파일 보존 (tmp 파일만 유실)                                            |
| LLM API timeout (429/503)                      | `PortfolioAgent.decide`, 파이프라인 내부 | 기존 retry 로직 (30s → model downgrade)                                  | 재시도 후 실패 시 해당 분석 스킵 + 로깅                                     |
| PortfolioAgent LLM timeout                     | `PortfolioAgent.decide`                  | 600초 timeout (deep_think_llm)                                           | timeout 시 pipeline_decision 직접 사용 (LLM 판단 없이 BUY/SELL/HOLD 그대로) |
| 스케줄러 분석 실패                             | `TickerScheduler._run_analysis_cycle`    | 1회 재시도, 실패 시 해당 ticker만 skip + 다음 주기에 재시도              | 다른 티커 스케줄 영향 없음                                                  |
| yfinance 데이터 fetch 실패                     | `dataflows/interface.py` (기존)          | Alpha Vantage fallback (기존 동작)                                       | fallback 벤더로 자동 전환                                                   |
| yfinance 현재가 fetch 실패                     | `TickerScheduler._run_analysis_cycle`    | close_all_positions 시 당일 종가 fetch 실패 → 해당 주기 SELL skip + 로깅 | 다음 주기에 재시도                                                          |

### Authorization

| Action           | Required Permission                   | Validation Location                | On Failure                            |
| ---------------- | ------------------------------------- | ---------------------------------- | ------------------------------------- |
| Gemini LLM 호출  | OAuth token (`~/.gemini` credentials) | `llm_clients/gemini_cli_client.py` | 자동 token refresh, 실패 시 분석 중단 |
| 파일 시스템 쓰기 | 로컬 파일 권한                        | OS level                           | `PermissionError` → 로깅 + 작업 중단  |

> 이 프로젝트는 HTTP API 서버가 아니므로 전통적 인증/인가(RBAC)는 해당 없음.
> 모든 보안은 OAuth 기반 LLM 접근 + 로컬 파일 시스템 권한으로 처리.

### Data Integrity

| Validation Item                                  | Validation Timing                               | On Failure                                                           |
| ------------------------------------------------ | ----------------------------------------------- | -------------------------------------------------------------------- |
| trade.json 필수 필드 존재 (ticker, cash, status) | `TradeManager.load()` 시                        | KeyError → `create_initial_trade()` 로 재초기화 + 경고               |
| positions 배열 유효성 (shares > 0, price > 0)    | `TradeManager.open_position()` 시               | `ValueError` → 포지션 미개설, 로깅                                   |
| cash 잔고 충분 여부                              | `TradeManager.open_position()` 시               | `ValueError("Insufficient cash")` → 매수 거부                        |
| JSONL 엔트리 schema_version 확인                 | `HybridMemory._load_corpus()` 시                | 미인식 버전 → skip + 경고 (미래 호환성)                              |
| reports.json 중복 analysis_no                    | `ReportStore.append()` 시                       | 마지막 analysis_no + 1 자동 채번 (중복 방지)                         |
| 스케줄러 동시 실행 방지                          | `TickerScheduler._run_analysis_cycle()` 진입 시 | per-ticker `threading.Lock(timeout=600)` → timeout 시 해당 주기 skip |

⚠️ **이 섹션이 비어있으면 구현의 80%가 불안정해집니다** — 반드시 완성

---

## 10. Additional Design Details (from Review)

### 매수 수량 결정

- **결정**: PortfolioAgent LLM이 매수 수량 결정
- 프롬프트에 현재 cash 잔고 + 현재가 포함 → LLM이 적정 수량 산출
- `decide()` 반환 dict에 `shares: int` 필드 포함

### 현재가 소스

- **결정**: yfinance 당일 종가
- `yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]`
- `close_all_positions()` 및 `open_position()` 시 사용
- fetch 실패 시 해당 주기 매매 skip

### PortfolioAgent Timeout

- **결정**: 600초 (기존 LLM timeout과 동일)
- timeout 시 PortfolioAgent 판단 없이 pipeline_decision 직접 사용

### Scheduler Stop 동작

- **결정**: 즉시 중단 (`scheduler.shutdown(wait=False)`)
- 명시적 stop() 호출 = 사용자 의도 = 즉시 중단
- 원자적 쓰기로 파일 안전성 보장 (tmp + rename)

### 이전 Check에서 이관된 항목

- **yfinance timeout**: 60초
- **LLM timeout**: 600초 일률 적용
- **Caching**: 불필요 (30일 lookback 기준 데이터 양이 적음, 1회성 분석)
- **Prompt versioning**: 현재 에이전트 파일 내 하드코딩 유지 (향후 분리 검토)

---

## 11. Pre-build Preparation (from Pre-build Check)

> Added: 2026-02-12 via `/pre-build` skill

### External Services Status

| Service      | Status   | Notes                                                                     |
| ------------ | -------- | ------------------------------------------------------------------------- |
| Gemini OAuth | ✅ Ready | `~/.gemini` credentials, 기존 작동 확인                                   |
| yfinance     | ✅ Ready | 무료 API, 인증 불필요                                                     |
| chromadb     | ✅ Local | 로컬 라이브러리 + 내장 ONNX 임베딩, 첫 실행 시 모델 자동 다운로드 (~80MB) |
| apscheduler  | ✅ Local | 로컬 라이브러리, 인증 불필요                                              |

### Infrastructure Status

| Component | Status | Notes                      |
| --------- | ------ | -------------------------- |
| Database  | ⬜ N/A | 파일 기반 (JSON/JSONL)     |
| Docker    | ⬜ N/A | 로컬 실행, 컨테이너 불필요 |
| Cache     | ⬜ N/A | 1회성 분석, 캐시 불필요    |

### Business Logic Definitions

| Logic                        | Formula                                                    |
| ---------------------------- | ---------------------------------------------------------- |
| RRF 스코어링                 | `rrf(d) = Σ 1/(60 + rank_i(d))` — 이미 §4에 정의           |
| 수익률 (realized_return_pct) | `(total_returned - total_invested) / total_invested × 100` |
| total_invested               | `Σ(shares × entry_price)` for all positions                |
| total_returned               | `Σ(shares × current_price)` for all positions              |
| 평균단가                     | N/A — positions 배열에 매수 건별 분리 저장, 개별 청산      |

### Mock Data Status

⬜ N/A — 기존 프로젝트, yfinance 실시간 데이터 사용, 별도 mock 불필요

---

## Sync History

| Date       | Action  | Skill     | Description                                                                       |
| ---------- | ------- | --------- | --------------------------------------------------------------------------------- |
| 2026-02-11 | create  | arch      | Cursor arch skill로 FR-013~019 설계 문서 생성 (24 code mappings, 7 steps)         |
| 2026-02-12 | review  | check     | 설계 완성도 검증 — 8개 gap 발견, 3개 결정(매수수량/현재가/PA timeout), 5개 skip   |
| 2026-02-12 | prepare | pre-build | 구현 준비 검증 — 외부서비스/인프라 all clear, 수익률 수식 확정                    |
| 2026-02-12 | update  | manual    | ChromaDB 자체 임베딩 엔진으로 통일, #5/#17 완료 마킹, embedding_model config 삭제 |
