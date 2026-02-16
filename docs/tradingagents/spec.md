# TradingAgents Requirements

> ⚠️ This document was reverse-engineered from code, then reinforced with proposal.md.

## 0. Requirement Summary

| Req ID     | Category   | Requirement                                                                                                                                                                                                    | Priority     | Status               |
| ---------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | -------------------- |
| FR-001     | Analysis   | Multi-agent market analysis pipeline (4 analysts)                                                                                                                                                              | High         | Implemented          |
| FR-002     | Debate     | Bull vs Bear investment debate with configurable rounds                                                                                                                                                        | High         | Implemented          |
| FR-003     | Decision   | Research Manager synthesizes debate → investment plan                                                                                                                                                          | High         | Implemented          |
| FR-004     | Trading    | Trader agent generates BUY/HOLD/SELL proposal                                                                                                                                                                  | High         | Implemented          |
| FR-005     | Risk       | 3-way risk debate (Aggressive/Conservative/Neutral)                                                                                                                                                            | High         | Implemented          |
| FR-006     | Risk       | Risk Manager renders final trade decision                                                                                                                                                                      | High         | Implemented          |
| ~~FR-007~~ | ~~Memory~~ | ~~BM25-based situation memory for agent reflection~~                                                                                                                                                           | ~~Critical~~ | Superseded by FR-015 |
| FR-008     | Learning   | Post-decision reflection writes lessons to memory                                                                                                                                                              | Critical     | Implemented          |
| FR-009     | Signal     | LLM-based signal extraction (BUY/HOLD/SELL from text)                                                                                                                                                          | Medium       | Implemented          |
| FR-010     | Data       | Multi-vendor data fetching with fallback (yfinance → Alpha Vantage)                                                                                                                                            | Medium       | Implemented          |
| FR-011     | LLM        | OAuth-based Gemini access (no API key, token refresh)                                                                                                                                                          | Medium       | Implemented          |
| FR-012     | Resilience | Rate limit (429) and capacity (503) retry with model downgrade                                                                                                                                                 | Medium       | Implemented          |
| FR-013     | Validation | 가상 매매 추적 — positions/trades/reports 테이블로 분석 정확도 검증                                                                                                                                            | High         | Implemented          |
| FR-014     | Agent      | Portfolio Agent — 기존 전략 + 새 분석 종합하여 매매 행동 결정 (deep_think_llm)                                                                                                                                 | High         | Implemented          |
| FR-015     | Memory     | Hybrid RAG (BM25 + Vector) — 영속성 있는 메모리로 FR-007 교체                                                                                                                                                  | Critical     | Implemented          |
| FR-016     | Scheduling | 스케줄 기반 반복 분석 (1 스케줄 = 1 티커, 주기 개별 설정)                                                                                                                                                      | Medium       | Implemented          |
| FR-017     | Analysis   | 포지션 인식 분석 — AgentState에 current_position 추가, 에이전트 프롬프트 주입                                                                                                                                  | Medium       | Superseded by FR-021 |
| FR-018     | Learning   | 구조화된 reflect_and_remember 입력 (ticker, return_pct, holding_days 등)                                                                                                                                       | High         | Implemented          |
| FR-019     | Learning   | 부트스트랩 태깅 — has_memory 플래그로 Memory 유무 비교 기준선                                                                                                                                                  | Medium       | Implemented          |
| FR-020     | Validation | 전략 기반 매매 실행 — TradeManager 부분 매도(close_positions, 평균단가), PA에 current_price 전달 및 매도 수량 전략 결정                                                                                        | High         | Implemented          |
| FR-021     | Analysis   | 분석플로우 객관성 확보 — 12에이전트에서 포지션 주입 제거 (FR-017 축소), 포지션 기반 판단은 PA에게만 위임                                                                                                       | Medium       | Implemented          |
| FR-022     | Agent      | PA 프롬프트 강화 — 분석 결과(가중치 6) > 경험(가중치 4) 기반 판단, 디바이어싱 지시, HybridMemory 연결                                                                                                          | High         | Designed             |
| ~~FR-023~~ | ~~Data~~   | ~~저장 경로 통합 + 아카이빙 — 포지션 close 시 trade/→archive/ 이동~~                                                                                                                                           | ~~High~~     | Superseded by FR-030 |
| ~~FR-024~~ | ~~Memory~~ | ~~저장 경로 개편 — memory/ 아래 experience + trade + archive 3분류~~                                                                                                                                           | ~~High~~     | Superseded by FR-030 |
| FR-025     | API        | FastAPI 웹 백엔드 — 스케줄 등록/조회, 매매 상태, 분석 결과, 수동 분석, WebSocket 진행현황 스트리밍                                                                                                             | High         | Implemented          |
| FR-026     | Security   | READ 공개 + WRITE 인증 — ADMIN_TOKEN(Bearer) 기반 단일 사용자 인증. Cloudflare Tunnel 배포                                                                                                                     | Medium       | Implemented          |
| ~~FR-027~~ | ~~Data~~   | ~~파일명 변경 — reports.json → report.json~~                                                                                                                                                                   | ~~Low~~      | Superseded by FR-030 |
| ~~FR-028~~ | ~~Data~~   | ~~저장 경로 명칭 — memory/data/ → memory/experience/~~                                                                                                                                                         | ~~Medium~~   | Superseded by FR-030 |
| FR-029     | Memory     | 기억 오염 방지 + 메타데이터 강화 — reflections에 outcome(win/loss), market, sector, industry 태깅. yfinance `Ticker.info` 자동 fetch. crypto는 quoteType 분기 fallback. RAG 검색 시 성공/실패 레이블 부착       | High         | Implemented          |
| FR-030     | Storage    | SQLite 전환 — 파일 기반 저장 전면 폐기 (eval_results, per-agent JSONL, trade/report JSON). SQLite 6테이블 (schedules, positions, reports, trades, reflections, schedule_jobs) + FTS5. ChromaDB는 벡터 검색 전용으로 유지 | Critical     | Implemented          |
| FR-031     | Learning   | 반성 집중화 — 5개 에이전트 개별 반성 → 반성에이전트 1곳 집중. 청산 시에만 실행 (shares == 0). reports + trades 전체 이력 기반 반성문 작성 → SQLite + ChromaDB 이중 저장                                        | High         | Designed             |
| FR-032     | Agent      | 요약에이전트 — 12에이전트 raw 산출물 + PA 의견 → 13개 개별 요약 컬럼으로 reports 테이블 저장 (sentiment_report, news_report 제외). 각 컬럼 200~400 토큰 목표                                                   | High         | Designed             |
| FR-033     | Memory     | BM25 엔진 교체 — rank_bm25 라이브러리 → SQLite FTS5 내장. JSONL 파싱 제거. reflections 테이블 트리거로 FTS 자동 동기화                                                                                         | Medium       | Designed             |
| FR-034     | API        | UI 지표용 현재가/PnL 제공 — yfinance 실시간 가격 조회로 대시보드 지표/포지션 PnL 계산 API 제공 (DB 저장 없음)                                                                                                 | Medium       | Implemented          |

> **Status**: `Implemented` = 코드 존재, `Designed` = 설계 완료 (미구현), `Draft` = proposal.md에서 추출
> **Req ID Rule**: `FR-{number}` format. New = max + 1. Never reuse deleted numbers.

## 1. Overview

### 1.1 Service Name

TradingAgents (G-ANT Trader)

### 1.2 Domain

Financial Analysis / AI-driven Investment Decision Support

### 1.3 Development Focus

- [x] Backend

## 2. Purpose

### 2.1 Goal

다중 AI 에이전트 협업을 통해 주식 투자 분석을 수행하고, 토론 기반 합의와 리스크 평가를 거쳐 **BUY/HOLD/SELL 의사결정**을 생성하는 시스템.
핵심 가치는 **반성/학습 메커니즘**을 통해 과거 판단 실패에서 학습하고 점진적으로 분석 품질을 향상시키는 것.

### 2.2 Non-goals

- **실제 매매 실행 안 함**: 가상 매매로 분석 정확도를 검증할 뿐, 증권사 API 연동이나 자동 주문 기능 없음
- **데이터 적재 안 함**: 시장 데이터는 분석 시점에 1회성으로 fetch하며, 별도 DB에 저장하지 않음
- **실제 자산 관리 안 함**: 가상 매매는 분석 검증 수단이며, 실제 자산 배분이나 리밸런싱 기능 없음
- **에이전트 진행현황 영속화 안 함**: 각 에이전트 개별 응답은 실시간 스트리밍만, report에는 최종 결과만 저장
- ~~웹 UI/대시보드 (CLI 기반 유지)~~ → **웹 API 제공 (FR-025)**

## 3. Feature Specifications

### 3.1 Core Features

| Feature                                             | Description                                                                                              | Confidence |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------- |
| Market Analysis Pipeline (FR-001)                   | 4개 전문 분석가(시장, 소셜, 뉴스, 펀더멘탈)가 순차 분석 후 리포트 생성                                   | ✅ High    |
| Investment Debate (FR-002, FR-003)                  | Bull/Bear 리서처가 N라운드 토론 후 Research Manager가 판결                                               | ✅ High    |
| Trader Decision (FR-004)                            | 투자 계획을 기반으로 구체적 BUY/HOLD/SELL 제안 생성                                                      | ✅ High    |
| Risk Assessment (FR-005, FR-006)                    | Aggressive/Conservative/Neutral 3자 토론 후 Risk Manager 최종 판결                                       | ✅ High    |
| Reflection & Learning (FR-008, FR-031)              | 반성에이전트가 청산 시 전체 사이클 기반 반성문 작성 → SQLite + ChromaDB 이중 저장                        | ✅ High    |
| Multi-vendor Data (FR-010)                          | yfinance를 기본으로 하되, 실패 시 Alpha Vantage로 자동 fallback                                          | ✅ High    |
| OAuth LLM Access (FR-011, FR-012)                   | API key 없이 Google OAuth로 Gemini 접근, rate limit 시 모델 다운그레이드                                 | ✅ High    |
| Virtual Trading Validation (FR-013, FR-014, FR-020) | 가상 매매로 분석 결과를 추적·검증, Portfolio Agent가 전략 기반 매매 수량 결정 (부분 매수/매도 지원)      | ✅ High    |
| Summary Agent (FR-032)                              | 12에이전트 raw + PA 의견 → 13개 개별 요약 컬럼으로 reports 테이블 저장                                   | ✅ High    |
| Scheduled Analysis (FR-016)                         | 티커별 주기적 반복 분석, 연속 분석으로 전략 유효성 추적                                                  | ✅ Medium  |
| Position-Aware Analysis (FR-017, FR-021)            | 분석플로우는 포지션 정보 없이 객관적 수행, PA만 포지션 인식 판단                                          | ✅ Medium  |
| Structured Learning (FR-018, FR-019, FR-029)        | 구조화된 반성 입력 + 부트스트랩 태깅 + outcome/market/sector/industry 메타데이터 태깅으로 기억 오염 방지 | ✅ High    |
| Storage Architecture (FR-030, FR-033)               | SQLite 6테이블 + FTS5 (BM25) + ChromaDB (벡터). 파일 기반 전면 폐기                                     | ✅ Critical |
| Web API (FR-025, FR-026)                            | FastAPI 백엔드 + READ 공개/WRITE 인증 + WebSocket 스트리밍                                               | ✅ High    |
| UI Metrics API (FR-034)                             | 현재가 기반 PnL/수익률 계산 API 제공 (대시보드 지표용, DB 미저장)                                        | ✅ Medium  |

### 3.2 Detailed Features

#### 3.2.1 Agent Pipeline Flow

```
Market Analyst → [Msg Clear] → Social Analyst → [Msg Clear]
    → News Analyst → [Msg Clear] → Fundamentals Analyst → [Msg Clear]
        → Bull Researcher ←→ Bear Researcher (N rounds debate)
            → Research Manager (Judge)
                → Trader Agent
                    → Aggressive ←→ Conservative ←→ Neutral (N rounds risk debate)
                        → Risk Manager (Final Judge)
                            → Signal Processing (BUY/HOLD/SELL)
```

> **Note**: Analyst 실행 순서는 `selected_analysts` 리스트 순서를 따름. 기본: market → social → news → fundamentals (순차 실행, 병렬 아님).

#### 3.2.2 Memory & Reflection (FR-015, FR-030, FR-031, FR-033)

- **Storage**: SQLite `reflections` 테이블 + FTS5 (BM25) + ChromaDB (벡터). 에이전트별 JSONL 폐기 (FR-030, FR-033)
- **Reflection Scope**: PA 1곳 집중 (반성에이전트). 5개 에이전트 개별 반성 폐기 (FR-031)
- **Reflection Trigger**: 청산 시에만 (position.shares == 0). 반성에이전트가 reports + trades 전체 이력 기반 반성문 작성
- **Memory Read**: PA만 읽음. Hybrid RAG (ChromaDB 벡터 + FTS5 BM25 → RRF 결합). 검색 결과에 `[✅ 성공 사례]` / `[⚠️ 실패 사례]` 레이블 부착 (FR-029)
- **Legacy Label**: outcome 누락된 기록은 `[❓ 미정]` 레이블로 표시
- **Memory Write**: 반성에이전트만 씀 (청산 시에만). SQLite reflections + FTS5 + ChromaDB 삼중 저장
- **Persistence**: SQLite 파일 1개 (`trading.db`) + ChromaDB PersistentClient
- **Bootstrap**: 초기 반성 데이터 없이 운영. 데이터 축적 후 자연스럽게 학습 시작 (FR-019)
- **Memory Poisoning Prevention**: outcome(win/loss), market, sector, industry 메타데이터로 기억 품질 관리 (FR-029)
- **Metadata Source**: `yfinance.Ticker(ticker).info` — market=`fullExchangeName`, sector=`sector`, industry=`industry`. crypto(`quoteType=CRYPTOCURRENCY`)는 고정값 fallback. fetch 실패 시 `null` 저장 + 정상 진행
- **Cross-ticker Learning**: 모든 티커의 반성 데이터가 하나의 RAG에 통합 → 종목 간 패턴 인식

#### 3.2.3 Virtual Trading Validation (FR-013, FR-014, FR-020, FR-032)

- **목적**: AI 분석이 실제로 맞았는지 가상 매매로 추적·검증하고, 축적된 데이터를 RAG에 피드백하여 분석 품질을 자기 개선
- **구조**: 1 스케줄 = 1 티커, 종목별 독립 자금 ($1,000 기본)
- **흐름**: 스케줄 실행 → 12에이전트 분석 → PA 판단·실행 → 요약에이전트 저장 → (청산 시) 반성에이전트
- **Portfolio Agent**: deep_think_llm, positions + trades 테이블 참조 → 전략 유지/수정/폐기 판단
- **요약에이전트**: 12에이전트 raw + PA 의견 → 13개 개별 요약 컬럼으로 reports 테이블 저장 (sentiment_report, news_report 제외) (FR-032)
- **분석 주기**: 기본 4일 간격 (yfinance 뉴스 7일 제공 기준), 종목별 개별 설정 가능
- **매매 원칙**: BUY/SELL/HOLD는 방향성, 전략이 실행 디테일(수량, 타점, 비중)을 결정. 매수·매도 모두 PA가 전략에 따라 수량 결정 (부분 매수/매도 지원)
- **청산 판정**: PA 실행 후 position.shares == 0이면 청산. 별도 플래그 불필요
- **실행 모델**: 글로벌 in-memory 큐(`asyncio.Queue`) + 순차 실행 (max_workers=1). LLM rate limit으로 병렴 불가. 스케줄 트리거 → 큐 push → 워커 1개가 순차 처리

#### 3.2.4 Data Fetching

- **Transient**: 데이터는 적재하지 않고 분석 시점에 1회성 fetch
- **Vendors**: yfinance (기본), Alpha Vantage (fallback)
- **Categories**: Stock OHLCV, Technical Indicators (8개 선택 가능), Fundamentals (재무제표 4종), News (종목/글로벌)
- **Vendor Routing**: `route_to_vendor()` → 설정 기반 벤더 선택 + 실패 시 자동 fallback
- **Retry Policy**: 벤더 실패 시 30초 간격 2회 재시도 후 다음 벤더로 fallback, 실패 이력은 schedule_jobs에 기록

#### 3.2.5 Web API (FR-025, FR-026)

- **Public READ**: `/health`, `/queue`, `/metrics`, `/positions`, `/positions/market`, `/positions/{id}`, `/schedules`, `/schedules/{ticker}/cycles`, `/reports`, `/reflections`, `/search`, `/activity`
- **Authenticated WRITE**: `POST /schedules`, `DELETE /schedules/{ticker}`, `POST /schedules/{ticker}/retry`
- **WebSocket**: `/ws/analyze/{ticker}` (에이전트 상태 스트리밍, step/phase 정보 포함)
- **UI Metrics**: 대시보드 지표/포지션 PnL 계산용 현재가는 yfinance로 on-demand 조회 (DB 저장 안 함)

## 4. Data Contracts

### 4.1 Main Entities

| Entity                                          | Fields                                                                                                                                                                                                                                                     | Source        |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `AgentState` (TypedDict)                        | messages, company_of_interest, trade_date, market_report, sentiment_report, news_report, fundamentals_report, investment_debate_state, risk_debate_state, investment_plan, trader_investment_plan, final_trade_decision, sender | Code + Draft  |
| `InvestDebateState` (TypedDict)                 | history, current_response, bull_history, bear_history, judge_decision, count                                                                                                                                                                               | Code          |
| `RiskDebateState` (TypedDict)                   | history, current_aggressive/conservative/neutral_response, aggressive/conservative/neutral_history, latest_speaker, judge_decision, count                                                                                                                  | Code          |
| `HybridMemory` (was `FinancialSituationMemory`) | name, documents, recommendations, bm25 + vector + persist — **Hybrid RAG로 교체 완료**                                                                                                                                                                     | Code (FR-015) |
| `DEFAULT_CONFIG` (Dict)                         | llm_provider, deep_think_llm, quick_think_llm, backend_url, data_vendors, tool_vendors, project_dir, data_cache_dir, max_debate_rounds, max_risk_discuss_rounds, max_recur_limit, database_path, chroma_path, default_initial_capital, schedules            | Code          |

### 4.2 Database Schema (FR-030)

> SQLite `trading.db` — 파일 기반 저장 (eval_results, per-agent JSONL, trade.json, reports.json) 전면 폐기

#### schedules (스케줄 실행 단위)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| ticker | TEXT NOT NULL | 분석 대상 티커 |
| interval_days | INTEGER NOT NULL | 분석 주기(일) |
| scheduled_cycle | INTEGER NOT NULL | 이 티커의 N번째 분석 |
| status | TEXT | 'pending' / 'running' / 'done' / 'failed' |
| error_message | TEXT | 실패 시 에러 메시지 (nullable) |
| created_at | TEXT NOT NULL | ISO 8601 |

#### positions (매매 사이클: 진입 → 청산)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| ticker | TEXT NOT NULL | 종목 |
| status | TEXT | 'active' / 'closed' |
| shares | INTEGER | 현재 보유 수량 |
| avg_cost | REAL | 평균 매입가 |
| return_pct | REAL | 청산 시 수익률 |
| opened_at | TEXT NOT NULL | 포지션 오픈 일시 |
| closed_at | TEXT | 청산 일시 |
| created_at | TEXT NOT NULL | 레코드 생성 일시 |

#### reports (에이전트별 요약, 스케줄마다 1건) — FR-032

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| schedule_id | INTEGER FK → schedules | 연결된 스케줄 |
| position_id | INTEGER FK → positions | 미보유 시 NULL |
| market_report | TEXT | 시장 분석 요약 |
| fundamentals_report | TEXT | 펀더멘탈 분석 요약 |
| bull_history | TEXT | 강세 논거 요약 |
| bear_history | TEXT | 약세 논거 요약 |
| investment_debate_judge_decision | TEXT | 투자 토론 판정 요약 |
| aggressive_history | TEXT | 공격적 리스크 의견 요약 |
| conservative_history | TEXT | 보수적 리스크 의견 요약 |
| neutral_history | TEXT | 중립 리스크 의견 요약 |
| trader_investment_judge_decision | TEXT | 트레이더 판정 요약 |
| trader_investment_decision | TEXT | 트레이더 결정 요약 |
| investment_plan | TEXT | 투자 계획 요약 |
| final_trade_decision | TEXT | 최종 거래 결정 요약 |
| pa_opinion | TEXT | PA 의견 (원본) |
| created_at | TEXT NOT NULL | 레코드 생성 일시 |

> 제외: sentiment_report (시의성), news_report (시의성, bull/bear 논거에 이미 반영)
> 각 컬럼 목표: 200~400 토큰. 13개 합계: ~3,000 토큰/사이클

#### trades (개별 BUY/SELL 액션)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| position_id | INTEGER FK → positions | 소속 포지션 |
| report_id | INTEGER FK → reports | 이 매매를 만든 분석 |
| action | TEXT NOT NULL | 'BUY' / 'SELL' |
| shares | INTEGER NOT NULL | 수량 |
| price | REAL NOT NULL | 체결 가격 |
| executed_at | TEXT NOT NULL | 체결 일시 |

#### reflections (청산 시 반성에이전트 산출물) — FR-031

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| position_id | INTEGER FK → positions | 소속 포지션 |
| reflection | TEXT NOT NULL | 반성문 전체 |
| key_lessons | TEXT | 핵심 교훈 요약 (RAG query용) |
| outcome | TEXT | 'win' / 'loss' |
| return_pct | REAL | 수익률 |
| market | TEXT | 거래소/시장 (nullable) |
| sector | TEXT | 섹터 (nullable) |
| industry | TEXT | 산업 (nullable) |
| created_at | TEXT NOT NULL | 레코드 생성 일시 |

#### schedule_jobs (에러/재시도 이력)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | 자동 증가 |
| schedule_id | INTEGER FK → schedules | 연결된 스케줄 |
| error_type | TEXT NOT NULL | vendor_retry / parse_failure / agent_failure / requeue 등 |
| error_message | TEXT NOT NULL | 요약 메시지 |
| error_detail | TEXT | 상세 메시지/스택 |
| created_at | TEXT NOT NULL | 기록 일시 |

#### reflections_fts (BM25 검색용 FTS5 가상 테이블) — FR-033

```sql
CREATE VIRTUAL TABLE reflections_fts USING fts5(
    reflection, key_lessons,
    content='reflections', content_rowid='id'
);
-- INSERT 트리거로 자동 동기화
```

#### 테이블 관계

```
schedules 1──1 reports N──1 positions 1──N trades
     │          │                        │
     └── N schedule_jobs                 └── report_id ←──────── trades
                                positions 1──0..1 reflections
```

> ⚠️ 폐기 대상: `eval_results/` 로그 저장, `memory/experience/{agent}.jsonl` 5개, `memory/data/{agent}.jsonl`, `virtual_trade/tickers/` 디렉토리

### 4.3 Configuration

```python
DEFAULT_CONFIG = {
    "project_dir": os.path.abspath("."),
    "data_cache_dir": "<project_dir>/dataflows/data_cache",
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini-cli"),
    "deep_think_llm": "gemini-3-pro-high",
    "quick_think_llm": "gemini-3-flash",
    "backend_url": None,
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},  # Tool-level override (takes precedence over data_vendors)
    "database_path": "<project_dir>/memory/trading.db",
    "chroma_path": "<project_dir>/memory/chroma",
    "default_initial_capital": 1000.0,
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": False,
}
```

> **Note**: fallback 벤더 목록은 config에 없음. `interface.py`의 `VENDOR_LIST` 순서로 자동 적용됨.

### 4.4 Storage Architecture (FR-030)

```
memory/
├── trading.db          ← SQLite (schedules, positions, reports, trades, reflections, schedule_jobs + FTS5)
└── chroma/             ← ChromaDB vector index (벡터 검색 전용)
```

> `virtual_trade/`, `eval_results/`, `memory/experience/*.jsonl`, `memory/data/*.jsonl` → 전면 폐기 (FR-030)

## 5. Exception/Error Policy

| Pattern                   | Inference                                                           |
| ------------------------- | ------------------------------------------------------------------- |
| LLM rate limit (429)      | 30s retry → model downgrade (pro → flash) → retry                   |
| LLM capacity (503)        | Exponential backoff, model downgrade                                |
| Data vendor failure       | 30s 간격 2회 재시도 후 다음 벤더로 fallback, 이력 schedule_jobs 기록 |
| Tool call returns no data | Agent continues with empty report (`report = ""`)                   |
| Decision parse failure    | 스케줄 실패 처리 + 재큐잉 (schedule_jobs 기록)                       |
| Agent execution failure   | 스케줄 실패 처리 + 재큐잉 (schedule_jobs 기록)                       |
| Empty BM25/RAG memory     | PA operates without past reference (`"No past memories found."`)    |

## 6. Unclear Items

| Item                           | Status                        | Notes                                       |
| ------------------------------ | ----------------------------- | ------------------------------------------- |
| ~~Memory persistence~~         | ✅ Resolved by FR-015         | Hybrid RAG + JSON persist                   |
| ~~Analysis result storage~~    | ✅ Resolved by FR-013         | reports 테이블 per schedule                |
| ~~Performance metrics~~        | ✅ Resolved by FR-013, FR-019 | 가상 매매 수익률 + 부트스트랩 태깅으로 추적 |
| ~~Multi-ticker orchestration~~ | ✅ Resolved by FR-016         | 스케줄 기반 티커별 반복 분석                |

## 7. Priority

| Rank | Feature                                     | Rationale                                    |
| ---- | ------------------------------------------- | -------------------------------------------- |
| 1    | Hybrid RAG Memory (FR-015)                  | 선행 조건. 영속 메모리 없이 학습 불가        |
| 2    | Structured Learning (FR-018, FR-019)        | RAG와 함께 확정해야 데이터 호환성 유지       |
| 3    | Virtual Trading (FR-013, FR-014)            | 분석 정확도 검증 — 핵심 가치                 |
| 4    | Agent Pipeline (FR-001~006, FR-008)         | 분석 자체의 품질을 결정하는 기반 (구현 완료) |
| 5    | Scheduled Analysis (FR-016)                 | 반복 분석 자동화                             |
| 6    | Position-Aware Analysis (FR-017)            | 기존 에이전트 수정 필요, 가장 마지막         |
| 7    | Data Fetching / LLM Resilience (FR-010~012) | 안정적 실행 보장 (구현 완료)                 |

---

## Reinforcement History

| Date       | Type            | Changes                                                                                                                                                                 |
| ---------- | --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-02-14 | add_requirement | UI 지표용 현재가/PnL API 추가 — FR-034                                                                                                                                    |
| 2026-02-11 | add_requirement | proposal.md → FR-013~019 추가 (7개 신규 요구사항)                                                                                                                       |
| 2026-02-11 | fill_blank      | 4개 Unclear Items 해결 (FR-013~016으로 커버)                                                                                                                            |
| 2026-02-11 | correct         | FR-007 → Superseded by FR-015, Non-goals 수정                                                                                                                           |
| 2026-02-12 | sync            | FR-013~019 Status: Designed→Implemented. SELL 정책: 전략 기반 비중 조절로 통일 (Phase 단계 제거). Memory 교체 완료 반영                                                 |
| 2026-02-12 | add_requirement | proposal.md → FR-020 추가 (전략 기반 매매 실행: 부분 매도 + PA current_price + 매도 수량 전략 결정)                                                                     |
| 2026-02-13 | add_requirement | proposal.md Phase 5 → FR-021~024 추가 (분석플로우 객관성, PA 강화, Experience 아카이빙, RAG 소스 전환)                                                                  |
| 2026-02-13 | add_requirement | proposal_v2.md → FR-025~028 추가 (웹 API, 보안, 파일명 변경, 저장경로 명칭). FR-023~024 설명 수정 (tickers/experience → trade/archive). Non-goals 수정 (웹 UI → 웹 API) |
| 2026-02-13 | add_requirement | proposal_v2.md §5-4 → FR-029 추가 (기억 오염 방지 + 메타데이터 강화: outcome/market/sector 태깅, yfinance 자동 fetch, RAG 레이블링)                                     |
| 2026-02-13 | sync            | arch-be.md 결정 역반영: +industry 필드, market→fullExchangeName, crypto quoteType fallback, fetch 실패→null. reflect_and_remember 예시 갱신                             |
| 2026-02-13 | add_requirement | 분석 실행 모델 추가: 글로벌 in-memory 큐(asyncio.Queue) + 순차 실행(max_workers=1). LLM rate limit으로 병렴 불가                                                        |
| 2026-02-13 | sync            | arch-be.md check 결과 역반영: POST /analyze 제거, GET /queue·/health 추가, 큐 중복 거부, JSON logging, WS reconnection 가이드                                           |
| 2026-02-13 | sync            | arch-be.md check Round 2 역반영: GET /queue·/health 응답 스키마, python-json-logger 의존성, POST /schedules 중복 409, DELETE /schedules 큐 정리                         |
| 2026-02-13 | sync            | 코드 검증 후 수정: WS 스트리밍 실구현(broadcast+subscriber), 큐 상태 추적, GET /positions 현재가, pyproject.toml 의존성 추가(fastapi/uvicorn/python-json-logger)        |
| 2026-02-13 | add_requirement | proposal_v3.md → FR-030~033 추가 (SQLite 전환, 반성 집중화, 요약에이전트, BM25 엔진 교체). FR-023/024/027/028 → Superseded by FR-030. 섹션 3.2.2, 4.2, 4.4 전면 갱신 |

---

## Reverse Extraction Info

| Item           | Content                                      |
| -------------- | -------------------------------------------- |
| Generated      | 2026-02-11                                   |
| Analysis scope | `packages/tradingagents/` (47 Python files, cli 제외) |
| Skill version  | reverse 2.0.0                                |
