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
| FR-006     | Risk       | Risk Manager renders final trade decision + strategy_json 구조화 출력                                                                                                                                          | High         | Implemented          |
| ~~FR-007~~ | ~~Memory~~ | ~~BM25-based situation memory for agent reflection~~                                                                                                                                                           | ~~Critical~~ | Superseded by FR-015 |
| FR-008     | Learning   | Post-decision reflection writes lessons to memory                                                                                                                                                              | Critical     | Implemented          |
| FR-009     | Signal     | LLM-based signal extraction (BUY/HOLD/SELL from text)                                                                                                                                                          | Medium       | Implemented          |
| FR-010     | Data       | Multi-vendor data fetching with fallback (yfinance → Alpha Vantage)                                                                                                                                            | Medium       | Implemented          |
| FR-011     | LLM        | OAuth-based Gemini access (no API key, token refresh)                                                                                                                                                          | Medium       | Implemented          |
| FR-012     | Resilience | Rate limit (429) and capacity (503) retry with model downgrade                                                                                                                                                 | Medium       | Implemented          |
| FR-013     | Validation | 가상 매매 추적 — positions/trades/reports 테이블로 분석 정확도 검증                                                                                                                                            | High         | Implemented          |
| FR-014     | Agent      | Portfolio Agent — 기존 전략 + 새 분석 종합하여 매매 행동 결정 (deep_think_llm)                                                                                                                                 | High         | Implemented          |
| FR-015     | Memory     | Hybrid RAG (FTS + Vector) — 영속성 있는 메모리로 FR-007 교체                                                                                                                                                   | Critical     | Implemented          |
| FR-016     | Scheduling | 스케줄 기반 반복 분석 (1 스케줄 = 1 티커, 주기 개별 설정). schedule_configs 테이블로 설정 영속화                                                                                                               | Medium       | Implemented          |
| FR-017     | Analysis   | 포지션 인식 분석 — AgentState에 current_position 추가, 에이전트 프롬프트 주입                                                                                                                                  | Medium       | Superseded by FR-021 |
| FR-018     | Learning   | 구조화된 reflect_and_remember 입력 (ticker, return_pct, holding_days 등)                                                                                                                                       | High         | Implemented          |
| FR-019     | Learning   | 부트스트랩 태깅 — has_memory 플래그로 Memory 유무 비교 기준선                                                                                                                                                  | Medium       | Implemented          |
| FR-020     | Validation | 전략 기반 매매 실행 — TradeManager 부분 매도(close_positions, 평균단가), PA에 current_price 전달 및 매도 수량 전략 결정                                                                                        | High         | Implemented          |
| FR-021     | Analysis   | 분석플로우 객관성 확보 — 12에이전트에서 포지션 주입 제거 (FR-017 축소), 포지션 기반 판단은 PA에게만 위임                                                                                                       | Medium       | Implemented          |
| FR-022     | Agent      | PA 프롬프트 강화 — 분석 결과(가중치 6) > 경험(가중치 4) 기반 판단, 디바이어싱 지시, HybridMemory 연결                                                                                                          | High         | Implemented          |
| ~~FR-023~~ | ~~Data~~   | ~~저장 경로 통합 + 아카이빙 — 포지션 close 시 trade/→archive/ 이동~~                                                                                                                                           | ~~High~~     | Superseded by FR-030 |
| ~~FR-024~~ | ~~Memory~~ | ~~저장 경로 개편 — memory/ 아래 experience + trade + archive 3분류~~                                                                                                                                           | ~~High~~     | Superseded by FR-030 |
| FR-025     | API        | FastAPI 웹 백엔드 — 스케줄 등록/조회, 매매 상태, 분석 결과, 수동 분석, WebSocket 진행현황 스트리밍                                                                                                             | High         | Implemented          |
| FR-026     | Security   | READ 공개 + WRITE 인증 — ADMIN_TOKEN(Bearer) 기반 단일 사용자 인증. Cloudflare Tunnel 배포                                                                                                                     | Medium       | Implemented          |
| ~~FR-027~~ | ~~Data~~   | ~~파일명 변경 — reports.json → report.json~~                                                                                                                                                                   | ~~Low~~      | Superseded by FR-030 |
| ~~FR-028~~ | ~~Data~~   | ~~저장 경로 명칭 — memory/data/ → memory/experience/~~                                                                                                                                                         | ~~Medium~~   | Superseded by FR-030 |
| FR-029     | Memory     | 기억 오염 방지 + 메타데이터 강화 — reflections에 outcome(win/loss), market, sector, industry 태깅. yfinance `Ticker.info` 자동 fetch. crypto는 quoteType 분기 fallback. RAG 검색 시 성공/실패 레이블 부착       | High         | Implemented          |
| FR-030     | Storage    | Postgres 전환 — 파일 기반 저장 전면 폐기. Postgres 8테이블 (schedules, schedule_configs, schedule_jobs, schedule_job_events, positions, reports, trades, reflections) + GIN FTS. ChromaDB는 벡터 검색 전용으로 유지 | Critical     | Implemented          |
| FR-031     | Learning   | 반성 집중화 — 5개 에이전트 개별 반성 → 반성에이전트 1곳 집중. 청산 시에만 실행 (shares == 0). reports + trades 전체 이력 기반 반성문 작성 → Postgres + ChromaDB 이중 저장                                       | High         | Implemented          |
| FR-032     | Agent      | 요약에이전트 — 12에이전트 raw 산출물 + PA 의견 → 개별 요약 컬럼으로 reports 테이블 저장 (sentiment_report, news_report 제외). 각 컬럼 200~400 토큰 목표                                                        | High         | Implemented          |
| FR-033     | Memory     | BM25 엔진 교체 — rank_bm25 라이브러리 → Postgres FTS (GIN 인덱스 + `to_tsvector`/`ts_rank_cd`). JSONL 파싱 제거                                                                                               | Medium       | Implemented          |
| FR-034     | API        | UI 지표용 현재가/PnL 제공 — yfinance 실시간 가격 조회로 대시보드 지표/포지션 PnL 계산 API 제공 (DB 저장 없음)                                                                                                 | Medium       | Implemented          |
| FR-035     | Frontend   | Svelte SPA 프론트엔드 — 모바일 최적화 대시보드, 포지션/스케줄/리포트/실시간 모니터링. svelte-spa-router, localStorage 캐싱, WebSocket 연동                                                                     | High         | Implemented          |
| FR-036     | Scheduling | 시장 데이터 중복 실행 방지 — schedule_configs.last_data_date와 yfinance 최신 거래일 비교하여 새 데이터 없으면 스킵                                                                                             | Medium       | Implemented          |
| FR-037     | API        | 에이전트 이벤트 영속화 — 분석 중 에이전트별 진행 이벤트를 schedule_job_events 테이블에 저장. WS 스트리밍 + DB 이력 조회 모두 지원                                                                              | Medium       | Implemented          |

> **Status**: `Implemented` = 코드 존재, `Designed` = 설계 완료 (미구현), `Draft` = proposal.md에서 추출
> **Req ID Rule**: `FR-{number}` format. New = max + 1. Never reuse deleted numbers.

## 1. Overview

### 1.1 Service Name

TradingAgents (G-ANT Trader)

### 1.2 Domain

Financial Analysis / AI-driven Investment Decision Support

### 1.3 Development Focus

- [x] Backend
- [x] Frontend

## 2. Purpose

### 2.1 Goal

다중 AI 에이전트 협업을 통해 주식 투자 분석을 수행하고, 토론 기반 합의와 리스크 평가를 거쳐 **BUY/HOLD/SELL 의사결정**을 생성하는 시스템.
핵심 가치는 **반성/학습 메커니즘**을 통해 과거 판단 실패에서 학습하고 점진적으로 분석 품질을 향상시키는 것.

### 2.2 Non-goals

- **실제 매매 실행 안 함**: 가상 매매로 분석 정확도를 검증할 뿐, 증권사 API 연동이나 자동 주문 기능 없음
- **데이터 적재 안 함**: 시장 데이터는 분석 시점에 1회성으로 fetch하며, 별도 DB에 저장하지 않음
- **실제 자산 관리 안 함**: 가상 매매는 분석 검증 수단이며, 실제 자산 배분이나 리밸런싱 기능 없음
- ~~에이전트 진행현황 영속화 안 함~~ → **에이전트 이벤트 DB 영속화 (FR-037)**: schedule_job_events 테이블에 저장, WS 스트리밍 + 이력 조회 동시 지원
- ~~웹 UI/대시보드 (CLI 기반 유지)~~ → **웹 API (FR-025) + Svelte SPA (FR-035) 제공**

## 3. Feature Specifications

### 3.1 Core Features

| Feature                                             | Description                                                                                              | Confidence |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------- |
| Market Analysis Pipeline (FR-001)                   | 4개 전문 분석가(시장, 소셜, 뉴스, 펀더멘탈)가 순차 분석 후 리포트 생성                                   | ✅ High    |
| Investment Debate (FR-002, FR-003)                  | Bull/Bear 리서처가 N라운드 토론 후 Research Manager가 판결                                               | ✅ High    |
| Trader Decision (FR-004)                            | 투자 계획을 기반으로 구체적 BUY/HOLD/SELL 제안 생성                                                      | ✅ High    |
| Risk Assessment (FR-005, FR-006)                    | Aggressive/Conservative/Neutral 3자 토론 후 Risk Manager 최종 판결 + strategy_json 구조화 출력            | ✅ High    |
| Reflection & Learning (FR-008, FR-031)              | 반성에이전트가 청산 시 전체 사이클 기반 반성문 작성 → Postgres + ChromaDB 이중 저장                       | ✅ High    |
| Multi-vendor Data (FR-010)                          | yfinance를 기본으로 하되, 실패 시 Alpha Vantage로 자동 fallback                                          | ✅ High    |
| OAuth LLM Access (FR-011, FR-012)                   | API key 없이 Google OAuth로 Gemini 접근, rate limit 시 모델 다운그레이드                                 | ✅ High    |
| Virtual Trading Validation (FR-013, FR-014, FR-020) | 가상 매매로 분석 결과를 추적·검증, Portfolio Agent가 전략 기반 매매 수량 결정 (부분 매수/매도 지원)      | ✅ High    |
| Summary Agent (FR-032)                              | 12에이전트 raw + PA 의견 → 개별 요약 컬럼으로 reports 테이블 저장                                        | ✅ High    |
| Scheduled Analysis (FR-016, FR-036)                 | 티커별 주기적 반복 분석, 중복 실행 방지(last_data_date), 연속 분석으로 전략 유효성 추적                   | ✅ Medium  |
| Position-Aware Analysis (FR-017, FR-021)            | 분석플로우는 포지션 정보 없이 객관적 수행, PA만 포지션 인식 판단                                          | ✅ Medium  |
| Structured Learning (FR-018, FR-019, FR-029)        | 구조화된 반성 입력 + 부트스트랩 태깅 + outcome/market/sector/industry 메타데이터 태깅으로 기억 오염 방지 | ✅ High    |
| Storage Architecture (FR-030, FR-033)               | Postgres 8테이블 + GIN FTS + ChromaDB (벡터). 파일 기반 전면 폐기                                        | ✅ Critical |
| Web API (FR-025, FR-026)                            | FastAPI 백엔드 + READ 공개/WRITE 인증 + WebSocket 스트리밍                                               | ✅ High    |
| UI Metrics API (FR-034)                             | 현재가 기반 PnL/수익률 계산 API 제공 (대시보드 지표용, DB 미저장)                                        | ✅ Medium  |
| Frontend SPA (FR-035)                               | Svelte 4 기반 모바일 최적화 대시보드, 실시간 WebSocket 모니터링, localStorage 캐싱                        | ✅ High    |
| Agent Event Persistence (FR-037)                    | 에이전트 이벤트 DB 영속화 + WS 스트리밍 동시 지원                                                        | ✅ Medium  |

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
                            → Signal Processing (BUY/HOLD/SELL + strategy_json)
```

> **Note**: Analyst 실행 순서는 `selected_analysts` 리스트 순서를 따름. 기본: market → social → news → fundamentals (순차 실행, 병렬 아님).
> **strategy_json**: Risk Judge가 `strategy_json` 코드블록으로 `{"action", "conviction", "allocation_pct"}` 구조화 출력. 파싱 실패 시 LLM fallback 추출.

#### 3.2.2 Memory & Reflection (FR-015, FR-030, FR-031, FR-033)

- **Storage**: Postgres `reflections` 테이블 + GIN FTS (`to_tsvector('simple', ...)` + `ts_rank_cd`) + ChromaDB (벡터). 에이전트별 JSONL 폐기 (FR-030, FR-033)
- **Reflection Scope**: PA 1곳 집중 (반성에이전트). 5개 에이전트 개별 반성 폐기 (FR-031)
- **Reflection Trigger**: 청산 시에만 (position.shares == 0). 반성에이전트가 reports + trades 전체 이력 기반 반성문 작성
- **Memory Read**: PA만 읽음. Hybrid RAG (ChromaDB 벡터 + Postgres FTS → RRF 결합). 검색 결과에 `[✅ 성공 사례]` / `[⚠️ 실패 사례]` 레이블 부착 (FR-029)
- **Legacy Label**: outcome 누락된 기록은 `[❓ 미정]` 레이블로 표시
- **Memory Write**: 반성에이전트만 씀 (청산 시에만). Postgres reflections + GIN FTS + ChromaDB 삼중 저장
- **Persistence**: Postgres DB + ChromaDB PersistentClient
- **Bootstrap**: 초기 반성 데이터 없이 운영. 데이터 축적 후 자연스럽게 학습 시작 (FR-019)
- **Memory Poisoning Prevention**: outcome(win/loss), market, sector, industry 메타데이터로 기억 품질 관리 (FR-029)
- **Metadata Source**: `yfinance.Ticker(ticker).info` — market=`fullExchangeName`, sector=`sector`, industry=`industry`. crypto(`quoteType=CRYPTOCURRENCY`)는 고정값 fallback. fetch 실패 시 `null` 저장 + 정상 진행
- **Cross-ticker Learning**: 모든 티커의 반성 데이터가 하나의 RAG에 통합 → 종목 간 패턴 인식

#### 3.2.3 Virtual Trading Validation (FR-013, FR-014, FR-020, FR-032)

- **목적**: AI 분석이 실제로 맞았는지 가상 매매로 추적·검증하고, 축적된 데이터를 RAG에 피드백하여 분석 품질을 자기 개선
- **구조**: 1 스케줄 = 1 티커, 종목별 독립 자금 ($5,000 기본)
- **흐름**: 스케줄 실행 → 12에이전트 분석 → PA 판단·실행 → 요약에이전트 저장 → (청산 시) 반성에이전트
- **Portfolio Agent**: deep_think_llm, positions + trades 테이블 참조 → 전략 유지/수정/폐기 판단
- **요약에이전트**: 12에이전트 raw + PA 의견 → 개별 요약 컬럼으로 reports 테이블 저장 (sentiment_report, news_report 제외) (FR-032)
- **분석 주기**: 기본 1일 간격 (종목별 개별 설정 가능), 새 시장 데이터가 없으면 스킵 (FR-036)
- **매매 원칙**: BUY/SELL/HOLD는 방향성, 전략이 실행 디테일(수량, 타점, 비중)을 결정. 매수·매도 모두 PA가 전략에 따라 수량 결정 (부분 매수/매도 지원). shares는 DOUBLE PRECISION (소수점 매매 지원)
- **청산 판정**: PA 실행 후 position.shares == 0이면 청산. 별도 플래그 불필요
- **실행 모델**: 글로벌 in-memory 큐(`asyncio.Queue`) + 순차 실행 (max_workers=1). LLM rate limit으로 병렬 불가. 스케줄 트리거 → 큐 push → 워커 1개가 순차 처리

#### 3.2.4 Data Fetching

- **Transient**: 데이터는 적재하지 않고 분석 시점에 1회성 fetch
- **Vendors**: yfinance (기본), Alpha Vantage (fallback)
- **Categories**: Stock OHLCV, Technical Indicators (8개 선택 가능), Fundamentals (재무제표 4종), News (종목/글로벌)
- **Vendor Routing**: `route_to_vendor()` → 설정 기반 벤더 선택 + 실패 시 자동 fallback
- **Retry Policy**: 벤더 실패 시 30초 간격 2회 재시도 후 다음 벤더로 fallback, 실패 이력은 schedule_jobs에 기록
- **Cache**: `stock_download_days` (330), `stock_download_buffer_days` (300), `stock_cache_stale_days` (3) 환경변수로 캐시 윈도 제어

#### 3.2.5 Web API (FR-025, FR-026, FR-037)

- **Public READ**:
  - `/health` — 헬스체크 (uptime, scheduler, queue)
  - `/queue` — 현재 분석 큐 상태 (running + pending)
  - `/metrics` — 대시보드 지표 (총 PnL, 수익률, 포지션 수, 승/패)
  - `/positions` — 포지션 목록 (active/closed 필터, cursor 페이지네이션)
  - `/positions/{id}` — 포지션 상세 (trades + reports 포함)
  - `/positions/market` — 활성 포지션 + yfinance 현재가 + PnL
  - `/position/{id}/graph` — OHLC 일봉 차트 데이터 (yfinance, 캐시 지원)
  - `/schedules` — 스케줄 목록
  - `/schedules/summary` — 오늘 스케줄 실행 요약 (done/failed/skipped/running)
  - `/schedules/{ticker}/cycles` — 특정 티커 분석 사이클 이력
  - `/schedules/{ticker}/cycles/{schedule_id}/events` — 사이클별 에이전트 이벤트 (FR-037)
  - `/reports` — 보고서 목록 (ticker/position_id 필터)
  - `/reports/tickers` — 티커별 보고서 요약 (최신 결정 포함)
  - `/reflections` — 반성문 목록 (outcome 필터)
  - `/search` — Hybrid RAG 검색
  - `/search/tickers` — Yahoo Finance 티커 검색
  - `/tickers/names` — 티커 display_name 맵
  - `/activity` — 최근 활동 피드 (trades + reports)
  - `/live/{ticker}/events` — 실시간 에이전트 이벤트 (최근 job)
- **Authenticated WRITE**: `POST /schedules`, `DELETE /schedules/{ticker}`, `POST /schedules/{ticker}/retry`
- **WebSocket**: `/ws/analyze/{ticker}` (에이전트 상태 스트리밍, step/phase 정보 포함)
- **UI Metrics**: 대시보드 지표/포지션 PnL 계산용 현재가는 yfinance로 on-demand 조회 (DB 저장 안 함)

#### 3.2.6 Frontend SPA (FR-035)

- **Tech Stack**: Svelte 4, TypeScript, Vite, svelte-spa-router
- **라우팅**: Hash-based SPA (`/#/`, `/#/positions`, `/#/schedules`, `/#/reports`, `/#/live`, `/#/auth`)
- **페이지**: Dashboard, Positions, TradeDetail, Schedules, ScheduleDetail, Reports, ReportDetail, Live, Auth
- **상태 관리**: Svelte stores (`auth`, `tickerNames`, `ui`)
- **API 통신**: fetch 기반 client (localStorage 캐싱 5분 TTL, 오프라인 폴백)
- **실시간**: WebSocket 연동 (`/ws/analyze/{ticker}`) 라이브 모니터링
- **인증**: localStorage에 admin token 저장, 401/403 시 자동 리다이렉트
- **UI**: 한국어, 모바일 최적화, 하단 5탭 네비게이션 (예약/실시간/홈/투자/AI분석)

## 4. Data Contracts

### 4.1 Main Entities

| Entity                                          | Fields                                                                                                                                                                                                                                                     | Source        |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `AgentState` (TypedDict)                        | messages, company_of_interest, trade_date, market_report, sentiment_report, news_report, fundamentals_report, investment_debate_state, risk_debate_state, investment_plan, trader_investment_plan, final_trade_decision, sender | Code + Draft  |
| `InvestDebateState` (TypedDict)                 | history, current_response, bull_history, bear_history, judge_decision, count                                                                                                                                                                               | Code          |
| `RiskDebateState` (TypedDict)                   | history, current_aggressive/conservative/neutral_response, aggressive/conservative/neutral_history, latest_speaker, judge_decision, count                                                                                                                  | Code          |
| `HybridMemory` (was `FinancialSituationMemory`) | name, chroma_client, chroma_collection, reflection_repo, db — **Postgres FTS + ChromaDB Hybrid RAG**                                                                                                                                                       | Code (FR-015) |
| `DEFAULT_CONFIG` (Dict)                         | llm_provider, deep_think_llm, quick_think_llm, backend_url, data_vendors, tool_vendors, project_dir, data_cache_dir, max_debate_rounds, max_risk_discuss_rounds, max_recur_limit, database_path, chroma_path, default_initial_capital, schedules, scheduler_enabled, stock_download_days, stock_download_buffer_days, stock_cache_stale_days | Code          |

### 4.2 Database Schema (FR-030)

> Postgres DB — 파일 기반 저장 (eval_results, per-agent JSONL, trade.json, reports.json) 전면 폐기. psycopg 드라이버 사용.

#### schedules (분석 실행 단위)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| ticker | TEXT NOT NULL | 분석 대상 티커 |
| interval_days | INTEGER NOT NULL DEFAULT 1 | 분석 주기(일) |
| scheduled_cycle | INTEGER NOT NULL | 이 티커의 N번째 분석 |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### schedule_configs (스케줄 설정 영속화)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| ticker | TEXT NOT NULL UNIQUE | 티커 (유니크) |
| interval_days | INTEGER NOT NULL DEFAULT 1 | 분석 주기(일) |
| last_data_date | DATE | 마지막 분석에 사용된 시장일 (FR-036 중복 방지) |
| display_name | TEXT | 티커 한글명 (nullable) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### positions (매매 사이클: 진입 → 청산)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| ticker | TEXT NOT NULL | 종목 |
| status | TEXT DEFAULT 'active' | 'active' / 'closed' |
| shares | DOUBLE PRECISION DEFAULT 0 | 현재 보유 수량 (소수점 매매 지원) |
| avg_cost | DOUBLE PRECISION | 평균 매입가 |
| return_pct | DOUBLE PRECISION | 청산 시 수익률 |
| opened_at | TIMESTAMPTZ NOT NULL | 포지션 오픈 일시 |
| closed_at | TIMESTAMPTZ | 청산 일시 |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### reports (에이전트별 요약, 스케줄마다 1건) — FR-032

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_id | BIGINT FK → schedules | 연결된 스케줄 |
| position_id | BIGINT FK → positions | 미보유 시 NULL |
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
| decision_position | TEXT | 파이프라인 결정 (BUY/SELL/HOLD) |
| portfolio_action | TEXT | PA 실행 액션 (BUY/SELL/HOLD) |
| portfolio_shares | DOUBLE PRECISION | PA 결정 수량 |
| portfolio_rationale | TEXT | PA 판단 근거 |
| pa_opinion | TEXT | PA 의견 (원본) |
| pipeline_strategy | TEXT | Risk Judge strategy_json (JSON 문자열) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

> 제외: sentiment_report (시의성), news_report (시의성, bull/bear 논거에 이미 반영)
> 각 요약 컬럼 목표: 200~400 토큰

#### trades (개별 BUY/SELL 액션)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| position_id | BIGINT FK → positions | 소속 포지션 |
| report_id | BIGINT FK → reports | 이 매매를 만든 분석 |
| action | TEXT NOT NULL | 'BUY' / 'SELL' |
| shares | DOUBLE PRECISION NOT NULL | 수량 (소수점 지원) |
| price | DOUBLE PRECISION NOT NULL | 체결 가격 |
| executed_at | TIMESTAMPTZ NOT NULL | 체결 일시 |

#### reflections (청산 시 반성에이전트 산출물) — FR-031

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| position_id | BIGINT FK → positions | 소속 포지션 |
| reflection | TEXT NOT NULL | 반성문 전체 |
| key_lessons | TEXT | 핵심 교훈 요약 (RAG query용) |
| outcome | TEXT | 'win' / 'loss' |
| return_pct | DOUBLE PRECISION | 수익률 |
| market | TEXT | 거래소/시장 (nullable) |
| sector | TEXT | 섹터 (nullable) |
| industry | TEXT | 산업 (nullable) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### schedule_jobs (스케줄 실행 이력 — 상태 + 에러/재시도)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_id | BIGINT FK → schedules | 연결된 스케줄 |
| status | TEXT NOT NULL | 'pending' / 'running' / 'done' / 'failed' / 'skipped' |
| error_type | TEXT | vendor_retry / parse_failure / agent_failure / requeue / no_data / no_update 등 |
| error_message | TEXT | 요약 메시지 |
| error_detail | TEXT | 상세 메시지/스택 |
| created_at | TIMESTAMPTZ NOT NULL | 기록 일시 |

#### schedule_job_events (에이전트 진행 이벤트) — FR-037

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_job_id | BIGINT FK → schedule_jobs | 연결된 Job |
| schedule_id | BIGINT FK → schedules | 연결된 스케줄 |
| ticker | TEXT | 티커 |
| agent | TEXT | 에이전트명 (Market Analyst, system 등) |
| status | TEXT | running / completed / error / skipped |
| message | TEXT | 상태 메시지 |
| step | INTEGER | 단계 번호 (1~13) |
| phase | TEXT | 단계 그룹 (Data Collection, Investment Debate 등) |
| created_at | TIMESTAMPTZ NOT NULL | 기록 일시 |

> UNIQUE INDEX `idx_schedule_job_events_unique` ON (schedule_job_id, agent) — 동일 job+agent 조합은 UPSERT

#### Postgres FTS (BM25 검색용) — FR-033

```sql
CREATE INDEX idx_reflections_search
    ON reflections
    USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
```

> rank_bm25 라이브러리 제거, Postgres 내장 `to_tsvector` + `ts_rank_cd` + `plainto_tsquery` 사용

#### 테이블 관계

```
schedule_configs ──── (ticker 기준 1:N) ──── schedules
schedules 1──N schedule_jobs 1──N schedule_job_events
schedules 1──1 reports N──1 positions 1──N trades
                │                        │
                └── report_id ←──────── trades
                                positions 1──0..1 reflections
```

> ⚠️ 폐기 대상: `eval_results/` 로그 저장, `memory/experience/{agent}.jsonl` 5개, `memory/data/{agent}.jsonl`, `virtual_trade/tickers/` 디렉토리

### 4.3 Configuration

```python
DEFAULT_CONFIG = {
    "project_dir": os.path.abspath("."),
    "data_cache_dir": "<project_dir>/dataflows/data_cache",
    # Data cache window
    "stock_download_days": 330,
    "stock_download_buffer_days": 300,
    "stock_cache_stale_days": 3,
    # LLM settings (Google OAuth, no API keys)
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini-cli"),
    "deep_think_llm": "gemini-3-pro-high",
    "quick_think_llm": "gemini-3-flash",
    "backend_url": None,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    "data_vendors": {
        "core_stock_apis": "yfinance",
        "technical_indicators": "yfinance",
        "fundamental_data": "yfinance",
        "news_data": "yfinance",
    },
    "tool_vendors": {},  # Tool-level override (takes precedence over data_vendors)
    # FR-030: Database URL (Postgres)
    "database_path": _get_database_url(),  # SUPABASE_DB_URL / POSTGRES_* env vars
    # FR-030: ChromaDB path (Vector store)
    "chroma_path": "<project_dir>/memory/chroma",
    "default_initial_capital": 5000.0,
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": False,  # TRADINGAGENTS_SCHEDULER_ENABLED env var
}
```

> **Note**: `database_path`는 `SUPABASE_DB_URL`, `TRADINGAGENTS_DB_URL`, `DATABASE_URL` 또는 `POSTGRES_*` 환경변수에서 자동 구성.
> **Note**: fallback 벤더 목록은 config에 없음. `interface.py`의 `VENDOR_LIST` 순서로 자동 적용됨.

### 4.4 Storage Architecture (FR-030)

```
Postgres DB (Supabase 호환)     ← 8 테이블 + GIN FTS 인덱스
    ├── schedules
    ├── schedule_configs
    ├── schedule_jobs
    ├── schedule_job_events
    ├── positions
    ├── reports
    ├── trades
    └── reflections

ChromaDB (PersistentClient)     ← 벡터 검색 전용
    └── memory/chroma/
```

> `virtual_trade/`, `eval_results/`, `memory/experience/*.jsonl`, `memory/data/*.jsonl` → 전면 폐기 (FR-030)

## 5. Exception/Error Policy

| Pattern                   | Inference                                                           |
| ------------------------- | ------------------------------------------------------------------- |
| LLM rate limit (429)      | 30s retry → model downgrade (pro → flash) → retry                   |
| LLM capacity (503)        | Exponential backoff, model downgrade                                |
| Data vendor failure       | 30s 간격 2회 재시도 후 다음 벤더로 fallback, 이력 schedule_jobs 기록 |
| Tool call returns no data | Agent continues with empty report (`report = ""`)                   |
| Decision parse failure    | 스케줄 실패 처리 + 자동 재큐잉 1회 (schedule_jobs 기록)              |
| Agent execution failure   | 스케줄 실패 처리 + 자동 재큐잉 1회 (schedule_jobs 기록)              |
| Data vendor total failure | `DataVendorError` → 스케줄 실패 처리 (재큐잉 없음)                  |
| Empty BM25/RAG memory     | PA operates without past reference (`"No past memories found."`)    |
| No new market data        | 스케줄 스킵 처리 (`status='skipped'`, FR-036)                       |
| ADMIN_TOKEN 미설정        | 서버 시작 차단 (`raise RuntimeError`)                               |

## 6. Unclear Items

| Item                           | Status                        | Notes                                       |
| ------------------------------ | ----------------------------- | ------------------------------------------- |
| ~~Memory persistence~~         | ✅ Resolved by FR-015         | Hybrid RAG + Postgres persist               |
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
| 2026-02-20 | sync            | 코드 기반 전면 최신화: SQLite→Postgres 반영, FR-022/031/032/033 Implemented 전환, FR-035~037 신규 추가 (Frontend SPA, 중복 실행 방지, 이벤트 영속화). DB 스키마 8테이블 전면 재작성 (BIGSERIAL, TIMESTAMPTZ, DOUBLE PRECISION). schedule_configs/schedule_job_events 테이블 추가. reports에 decision_position/portfolio_action/portfolio_shares/portfolio_rationale/pipeline_strategy 컬럼 추가. FTS5→Postgres GIN FTS 반영. Configuration default_initial_capital 5000, interval_days 1 반영. API 엔드포인트 23개 전체 반영. Non-goals 수정 (이벤트 영속화, 웹 UI). Section 3.2.6 Frontend SPA 추가 |
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
| Last synced    | 2026-02-20 (code-based full sync)            |
| Analysis scope | `packages/tradingagents/` + `apps/` (Python + Svelte) |
| Skill version  | reverse 2.0.0                                |
