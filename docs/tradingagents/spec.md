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
| FR-038     | Infra      | DB 리셋/마이그레이션 스크립트 — PostgreSQL FK 역순 DROP + ChromaDB 삭제 + init_schema() 재호출. `--confirm` 안전장치, `--keep-chroma` 옵션                                                                     | Critical     | Implemented          |
| FR-039     | Storage    | 스케줄 테이블 재설계 — `schedules` 테이블 제거, `schedule_configs`에 `current_cycle` 추가, `schedule_jobs`가 `schedule_config_id` FK로 사이클 기록 흡수. 8테이블→7테이블                                       | Critical     | Implemented          |
| FR-040     | Trading    | 통화(Currency) 전면 지원 — `schedule_configs`/`positions`/`trades`에 currency 컬럼, 티커 등록 시 자동 감지(.KS/.KQ→KRW), PA cash 계산 통화별 분리, UI 공통 헤더 통화 셀렉터(ALL/KRW/USD)                       | Critical     | Implemented          |
| FR-041     | Trading    | 포지션별 독립 자금 — `schedule_configs`에 `initial_capital` 저장(USD $5,000/KRW ₩5,000,000). cash_balance를 active position 기반으로 계산. 이전 포지션 trades 격리                                              | High         | Implemented          |
| FR-042     | Trading    | 자동 청산 메커니즘 — PA의 `stop_loss`/`target`을 `positions` 테이블에 저장. 사이클 시작 시 return_pct가 임계치 초과 시 PA 거치지 않고 즉시 청산 + 반성에이전트 실행. 미설정 시 ±30% 폴백                       | High         | Implemented          |
| FR-043     | Trading    | 매매 가격/시점 보정 — `_get_latest_close()`, `(price, data_date)` 튜플 반환. `trade.executed_at`과 `position.opened_at` 모두 yfinance 최신 확정 종가의 데이터 기준일로 설정. 스케줄러는 장 마감 후 실행되므로 항상 당일 확정 종가 사용 | High         | Implemented          |
| FR-044     | Scheduling | 스케줄러 시장별 실행 시간 — `schedule_configs`에 `market` 컬럼(us/kr). IntervalTrigger→CronTrigger 변경 (나스닥+코인: ET 17:00, 코스피/코스닥: KST 16:30)                                                      | High         | Implemented          |
| FR-045     | API        | 총손익 = 실현 + 미실현 — metrics API에 `total_realized_pnl`/`total_realized_return_pct` 추가. 실현손익은 closed positions의 trades 합산, 미실현손익은 active positions의 yfinance 현재가 기반                   | High         | Implemented          |
| FR-046     | Frontend   | Closed 포지션 UI — Positions 페이지에 active/closed 탭 분리, `/positions/closed` API, closed 목록에 승패·수익률·보유기간 표시                                                                                   | High         | Implemented          |
| FR-047     | Validation | Win/Loss 판정 기준 통일 — `return_pct >= 0`이면 win, `< 0`이면 loss로 일원화 (reflection.py, routes.py, Reflections.svelte 모두)                                                                               | Medium       | Implemented          |
| FR-048     | Frontend   | TradeDetail History 뱃지 동적 색상 — 하드코딩 `badge-gain` → `getDecisionClass(getReportDecision(report))` 동적 적용. BUY/매수=gain, SELL/매도=loss, HOLD/관망=muted                                           | Low          | Implemented          |
| FR-049     | Frontend   | Reflections 웹 UI — `/reflections` 라우트 + Reflections.svelte 페이지. win/loss 필터, cursor 페이지네이션, 마크다운 reflection 본문(marked+DOMPurify) + key_lessons 요약                                       | Medium       | Implemented          |
| FR-050     | LLM        | Codex(GPT-5.3) LLM Provider — `oauth-codex` PyPI 패키지, `ChatCodex(BaseChatModel)` LangChain 래퍼, Responses API + tool calling, `gpt-5.3-codex` 단일 모델                                                   | Medium       | Implemented          |
| FR-051     | Memory     | RAG 맥락 인식 검색 — 쿼리에 market/sector 텍스트 부착 (쿼리 enrichment). ChromaDB 시멘틱이 맥락 반영, FTS는 순수 키워드 매칭 유지. industry 배제, DB 하드 필터 대신 graceful degradation | High | Draft |
| FR-052     | Memory     | RAG 검색 파이프라인 재설계 — FTS top-3 + ChromaDB top-3 → 중복제거 + RRF top-3 → usefulness < 40 하드 배제 → usefulness DESC → top-K. `reflections.usefulness_score` 컬럼 추가(기본값 50). `RAG_TOP_K` 환경변수(기본 1, 추후 2~3) | Critical | Draft |
| FR-053     | Learning   | RAG Validator — 회고분석 결과 기반 RAG 문서별 usefulness_score ±1 자동 조정. RAG 문서는 반성(매매검증) 출신으로 한정. 효과 분석 리포트 생성 (사람이 읽고 판단) | High | Draft |
| FR-054     | Frontend   | 매매검증 검색 — 키워드(FTS LIKE/ILIKE) + 시멘틱(ChromaDB) 이중 검색. UI 검색창 + 모드 토글. `GET /reflections/search?q=...&mode=keyword\|semantic` | Medium | Draft |

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
| Storage Architecture (FR-030, FR-033, FR-039)       | Postgres 7테이블 + GIN FTS + ChromaDB (벡터). 파일 기반 전면 폐기                                        | ✅ Critical |
| Web API (FR-025, FR-026)                            | FastAPI 백엔드 + READ 공개/WRITE 인증 + WebSocket 스트리밍                                               | ✅ High    |
| UI Metrics API (FR-034)                             | 현재가 기반 PnL/수익률 계산 API 제공 (대시보드 지표용, DB 미저장)                                        | ✅ Medium  |
| Frontend SPA (FR-035)                               | Svelte 4 기반 모바일 최적화 대시보드, 실시간 WebSocket 모니터링, localStorage 캐싱                        | ✅ High    |
| Agent Event Persistence (FR-037)                    | 에이전트 이벤트 DB 영속화 + WS 스트리밍 동시 지원                                                        | ✅ Medium  |
| DB Reset Script (FR-038)                            | PostgreSQL FK 역순 DROP + ChromaDB 컬렉션 삭제 + 재초기화. 안전장치 포함                                 | ✅ Critical |
| Schedule Table Redesign (FR-039)                    | schedules 테이블 제거, schedule_configs 확장(current_cycle), schedule_jobs FK 통합. 8→7테이블              | ✅ Critical |
| Currency Support (FR-040, FR-041, FR-045)           | 통화별 자금 관리(USD/KRW), 포지션별 독립 자금, 총손익=실현+미실현, 통화 셀렉터 UI                        | ✅ Critical |
| Auto Liquidation (FR-042)                           | PA stop_loss/target DB 저장 + ±30% 폴백 자동 청산. 반성에이전트 학습 사이클 활성화                        | ✅ High    |
| Trade Timing Fix (FR-043)                           | 매매 시점/가격을 yfinance 데이터 기준일+종가로 보정                                                       | ✅ High    |
| Market-Aware Scheduling (FR-044)                    | CronTrigger + 타임존(나스닥 KST 07:00, 코스피 KST 16:30). 장마감 후 분석                                | ✅ High    |
| Closed Positions UI (FR-046)                        | active/closed 탭 분리, 과거 포지션 승패·수익률·보유기간 표시                                              | ✅ High    |
| Reflections Web UI (FR-049)                         | 회고 목록 페이지, win/loss 필터, cursor 페이지네이션, 마크다운 렌더링                                     | ✅ Medium  |
| Codex LLM Provider (FR-050)                         | OpenAI Codex(GPT-5.3) OAuth PKCE 기반 LangChain 래퍼                                                     | ✅ Medium  |
| RAG Context-Aware Search (FR-051)                   | 쿼리 enrichment로 market/sector 맥락 반영. 크로스 티커 노이즈 감소                                       | ⬜ High    |
| RAG Search Pipeline Redesign (FR-052)               | RRF → usefulness 순서, top-K 제어(`RAG_TOP_K`), usefulness < 40 하드 배제                                | ⬜ Critical |
| RAG Validator (FR-053)                              | 회고분석 기반 문서별 usefulness_score ±1 자동 조정. 느린 쓰레기 필터                                      | ⬜ High    |
| Reflections Search (FR-054)                         | 매매검증 키워드 + 시멘틱 이중 검색, UI 검색창 + 모드 토글                                                 | ⬜ Medium  |

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
- **RAG Query Enrichment** (FR-051): 검색 쿼리에 market/sector 텍스트 부착. ChromaDB 임베딩이 맥락을 벡터에 반영하여 같은 시장/섹터 문서의 유사도 자연 상승. FTS는 순수 키워드 매칭 유지. industry는 배제 (sector 수준이면 충분). DB 하드 필터 대신 graceful degradation — 같은 맥락 문서가 부족하면 cross-sector 문서가 낮은 유사도로 자연 상승
- **RAG Search Pipeline** (FR-052): FTS top-3 + ChromaDB top-3 → 중복제거 + RRF 융합 → top-3 (적합성 커팅) → usefulness_score < 40 하드 배제 → usefulness DESC → top-K (유용성 커팅) → PA 주입. `RAG_TOP_K` 환경변수로 주입 경험 수 제어 (기본 1, 추후 2~3). 초기 K=1은 RAG Validator의 귀인 평가 정확도를 높이기 위한 의도적 선택
- **usefulness_score** (FR-052, FR-053): `reflections` 테이블에 `usefulness_score` 컬럼 (DOUBLE PRECISION, 기본값 50). RAG Validator가 ±1 조정. 40 미만 시 검색 결과에서 하드 배제. 대부분 문서가 48~52에 머물며, 진짜 쓰레기만 서서히 하락하는 보수적 필터
- **RAG Validator** (FR-053): 회고분석 결과(`retrospective_analyses.analysis_content`)를 입력으로 받아, RAG 문서(`reports.rag_docs.memories[*]`)별로 PA가 실제로 해당 경험을 반영했는지 문서 단위 개별 평가. usefulness_score ±1 자동 조정 + 효과 분석 리포트 생성 (사람이 읽고 판단). RAG 문서는 반성(매매검증) 출신으로 한정 — 회고분석은 RAG에 저장하지 않음

#### 3.2.3 Virtual Trading Validation (FR-013, FR-014, FR-020, FR-032, FR-041, FR-042, FR-043)

- **목적**: AI 분석이 실제로 맞았는지 가상 매매로 추적·검증하고, 축적된 데이터를 RAG에 피드백하여 분석 품질을 자기 개선
- **구조**: 1 스케줄 = 1 티커, 종목별 독립 자금 (USD $5,000 / KRW ₩5,000,000). `schedule_configs.initial_capital`에 저장 (FR-041)
- **흐름**: 스케줄 실행 → 자동 청산 체크(FR-042) → 12에이전트 분석 → PA 판단·실행 → 요약에이전트 저장 → (청산 시) 반성에이전트
- **Portfolio Agent**: deep_think_llm, positions + trades 테이블 참조 → BUY/SELL/HOLD 판단 (MODIFY 액션 제거됨). `stop_loss`/`target`을 `positions` 테이블에 저장 (FR-042). stop_loss ≥ target 역전 시 무시
- **요약에이전트**: 12에이전트 raw + PA 의견 → 개별 요약 컬럼으로 reports 테이블 저장 (sentiment_report, news_report 제외) (FR-032)
- **분석 주기**: 기본 1일 간격 (종목별 개별 설정 가능), 새 시장 데이터가 없으면 스킵 (FR-036)
- **매매 원칙**: BUY/SELL/HOLD는 방향성, 전략이 실행 디테일(수량, 타점, 비중)을 결정. 매수·매도 모두 PA가 전략에 따라 수량 결정 (부분 매수/매도 지원). shares는 DOUBLE PRECISION (소수점 매매 지원)
- **청산 판정**: PA 실행 후 position.shares == 0이면 청산, 또는 자동 청산 트리거 시 즉시 청산 (FR-042). 별도 플래그 불필요
- **자동 청산** (FR-042): 사이클 시작 시 현재가 체크 → `return_pct`가 PA 설정 `stop_loss`/`target` 또는 ±30% 폴백 초과 시 PA를 거치지 않고 즉시 전량 청산. 청산 가격은 yfinance 종가 기준 (FR-043 연계)
- **독립 자금** (FR-041): 각 포지션은 `schedule_configs.initial_capital` 기준 독립 자금. cash_balance = initial_capital - 해당 포지션의 BUY 합산 + SELL 합산. 이전 포지션 trades 격리
- **매매 시점** (FR-043): `_get_latest_close()` — `(price, data_date)` 튜플 반환. `trade.executed_at`과 `position.opened_at` 모두 yfinance 최신 확정 종가의 데이터 기준일로 설정 (코드 실행 시각이 아닌 데이터 확정일). 스케줄러가 장 마감 후 실행되므로 항상 당일 확정 종가 사용. `_get_current_price()` 레거시 래퍼 삭제됨
- **실행 모델**: 글로벌 in-memory 큐(`asyncio.Queue`) + 순차 실행 (max_workers=1). LLM rate limit으로 병렬 불가. 스케줄 트리거 → 큐 push → 워커 1개가 순차 처리

#### 3.2.4 Data Fetching

- **Transient**: 데이터는 적재하지 않고 분석 시점에 1회성 fetch
- **Vendors**: yfinance (기본), Alpha Vantage (fallback)
- **Categories**: Stock OHLCV, Technical Indicators (8개 선택 가능), Fundamentals (재무제표 4종), News (종목/글로벌)
- **Vendor Routing**: `route_to_vendor()` → 설정 기반 벤더 선택 + 실패 시 자동 fallback
- **Retry Policy**: 벤더 실패 시 30초 간격 2회 재시도 후 다음 벤더로 fallback, 실패 이력은 schedule_jobs에 기록
- **Cache**: `stock_download_days` (330), `stock_download_buffer_days` (300), `stock_cache_stale_days` (3) 환경변수로 캐시 윈도 제어

#### 3.2.5 Currency & Market Support (FR-040, FR-044)

- **통화 자동 감지** (FR-040): 티커 등록 시 접미사 기반 자동 감지 — `.KS`/`.KQ` → KRW, `BTC-USD` 등 → USD, 기본 → USD
- **initial_capital**: `schedule_configs` 테이블에 저장. KRW 티커 = ₩5,000,000, USD 티커 = $5,000. 고정값이지만 향후 사용자 설정 확장 대비 DB 저장
- **통화별 분리**: 총손익/metrics 계산 시 통화별 분리 (환율 변환 안 함)
- **UI 통화 셀렉터** (FR-040): 공통 헤더에 `ALL | KRW | USD` 셀렉터
  - **ALL**: 전체 티커 표시, `showAmount=false` → 손익 퍼센트만 표시 (금액 합산 불가)
  - **KRW**: `matchesCurrency(ticker, "KRW")` 필터, `showAmount=true` → ₩ 금액 표시
  - **USD**: `matchesCurrency(ticker, "USD")` 필터, `showAmount=true` → $ 금액 표시
  - 기본값 ALL, 선택 시 localStorage(`gant_currency`) 저장. FE 클라이언트 사이드 필터링 (API에 currency 파라미터 없음)
- **시장별 스케줄링** (FR-044): `schedule_configs.market` 컬럼 (us/kr). `IntervalTrigger` → `CronTrigger` 변경. `_make_cron_trigger(market)` 정적 메서드로 트리거 생성
  - **us(나스닥 등) + crypto**: `CronTrigger(hour=17, minute=0, timezone="US/Eastern")` — 미국 장마감 1시간 후
  - **kr(코스피/코스닥)**: `CronTrigger(hour=16, minute=30, timezone="Asia/Seoul")` — 한국 장마감 1시간 후
  - `interval_days`는 DB에 유지하되 당분간 1(매일) 고정
  - **주말/공휴일**: `last_data_date` 체크로 이미 자동 스킵 처리됨 (기존 로직 유지)

#### 3.2.6 Web API (FR-025, FR-026, FR-037)

- **Public READ**:
  - `/health` — 헬스체크 (uptime, scheduler, queue)
  - `/queue` — 현재 분석 큐 상태 (running + pending)
  - `/metrics` — 대시보드 지표 (active/closed 카운트, wins/losses, total_realized_pnl + total_unrealized_pnl + total_pnl). 통화 필터 없음 — FE에서 currencyStore 기반 클라이언트 필터링 (FR-045)
  - `/positions` — 포지션 목록 (`?status=` 필터) (FR-046)
  - `/positions/{id}` — 포지션 상세 (trades + reports 포함)
  - `/positions/market` — 활성 포지션 + yfinance 현재가 + PnL
  - `/positions/closed` — 청산 포지션 목록 (outcome, return_pct, currency 포함) (FR-046)
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

#### 3.2.7 Frontend SPA (FR-035, FR-040, FR-046, FR-049)

- **Tech Stack**: Svelte 4, TypeScript, Vite, svelte-spa-router
- **라우팅**: Hash-based SPA (`/#/`, `/#/positions`, `/#/schedules`, `/#/reports`, `/#/reflections`, `/#/live`, `/#/auth`)
- **페이지**: Dashboard, Positions, TradeDetail, Schedules, ScheduleDetail, Reports, ReportDetail, Reflections, Live, Auth (10개)
- **상태 관리**: Svelte stores (`auth`, `tickerNames`, `ui`, `currency`)
- **API 통신**: fetch 기반 client (localStorage 캐싱 5분 TTL, 오프라인 폴백)
- **실시간**: WebSocket 연동 (`/ws/analyze/{ticker}`) 라이브 모니터링
- **인증**: localStorage에 admin token 저장, 401/403 시 자동 리다이렉트
- **UI**: 한국어, 모바일 최적화, 하단 6탭 네비게이션 (예약/실시간/홈/투자/AI분석/회고)
- **통화 셀렉터** (FR-040): 공통 헤더에 ALL/KRW/USD 셀렉터, localStorage 저장, currencyStore 기반
- **Closed 포지션** (FR-046): Positions 페이지 active/closed 탭 분리, closed 목록에 승패·수익률·보유기간
- **회고 페이지** (FR-049): `/reflections` 라우트, win/loss 필터, cursor 페이지네이션, 마크다운 렌더링

## 4. Data Contracts

### 4.1 Main Entities

| Entity                                          | Fields                                                                                                                                                                                                                                                     | Source        |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| `AgentState` (TypedDict)                        | messages, company_of_interest, trade_date, market_report, sentiment_report, news_report, fundamentals_report, investment_debate_state, risk_debate_state, investment_plan, trader_investment_plan, final_trade_decision, sender | Code + Draft  |
| `InvestDebateState` (TypedDict)                 | history, current_response, bull_history, bear_history, judge_decision, count                                                                                                                                                                               | Code          |
| `RiskDebateState` (TypedDict)                   | history, current_aggressive/conservative/neutral_response, aggressive/conservative/neutral_history, latest_speaker, judge_decision, count                                                                                                                  | Code          |
| `HybridMemory` (was `FinancialSituationMemory`) | name, chroma_client, chroma_collection, reflection_repo, db — **Postgres FTS + ChromaDB Hybrid RAG**                                                                                                                                                       | Code (FR-015) |
| `DEFAULT_CONFIG` (Dict)                         | llm_provider, deep_think_llm, quick_think_llm, backend_url, data_vendors, tool_vendors, project_dir, data_cache_dir, max_debate_rounds, max_risk_discuss_rounds, max_recur_limit, database_path, chroma_path, default_initial_capital, schedules, scheduler_enabled, stock_download_days, stock_download_buffer_days, stock_cache_stale_days | Code          |

### 4.2 Database Schema (FR-030, FR-039, FR-040, FR-041, FR-042)

> Postgres DB — 7테이블 (FR-039에서 `schedules` 제거, `schedule_configs` 확장). psycopg 드라이버 사용.

#### schedule_configs (티커별 설정 — 기존 + 확장)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| ticker | TEXT NOT NULL UNIQUE | 티커 (유니크) |
| interval_days | INTEGER NOT NULL DEFAULT 1 | 분석 주기(일) |
| current_cycle | INTEGER NOT NULL DEFAULT 0 | **[NEW]** 원자적 사이클 관리, MAX() 쿼리 제거 (FR-039) |
| currency | TEXT NOT NULL DEFAULT 'USD' | **[NEW]** KRW / USD. 자동 감지: .KS/.KQ → KRW (FR-040) |
| initial_capital | DOUBLE PRECISION NOT NULL DEFAULT 5000 | **[NEW]** 포지션별 독립 자금. KRW=5000000, USD=5000 (FR-041) |
| market | TEXT NOT NULL DEFAULT 'us' | **[NEW]** us / kr / crypto. CronTrigger 시간대 결정 (FR-044) |
| last_data_date | DATE | 마지막 분석에 사용된 시장일 (FR-036 중복 방지) |
| display_name | TEXT | 티커 한글명 (nullable) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

> **[REMOVED]** `schedules` 테이블 — `schedule_jobs`가 흡수 (FR-039)

#### schedule_jobs (사이클별 실행 기록 — schedules + schedule_jobs 통합)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_config_id | BIGINT NOT NULL FK → schedule_configs | **[CHANGED]** schedule_id → schedule_config_id (FR-039) |
| scheduled_cycle | INTEGER NOT NULL | **[NEW]** schedules에서 흡수 (FR-039) |
| status | TEXT NOT NULL | 'pending' / 'running' / 'done' / 'failed' / 'skipped' |
| error_type | TEXT | vendor_retry / parse_failure / agent_failure / requeue / no_data / no_update 등 |
| error_message | TEXT | 요약 메시지 |
| error_detail | TEXT | 상세 메시지/스택 |
| created_at | TIMESTAMPTZ NOT NULL | 기록 일시 |

#### positions (매매 사이클 — 기존 + 통화/청산 전략)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| ticker | TEXT NOT NULL | 종목 |
| status | TEXT NOT NULL DEFAULT 'active' | 'active' / 'closed' |
| shares | DOUBLE PRECISION NOT NULL DEFAULT 0 | 현재 보유 수량 (소수점 매매 지원) |
| avg_cost | DOUBLE PRECISION | 평균 매입가 |
| currency | TEXT NOT NULL DEFAULT 'USD' | **[NEW]** 포지션 통화 (FR-040) |
| stop_loss | DOUBLE PRECISION | **[NEW]** PA 설정 손절가. NULL이면 ±30% 폴백 (FR-042) |
| target | DOUBLE PRECISION | **[NEW]** PA 설정 목표가. NULL이면 ±30% 폴백 (FR-042) |
| return_pct | DOUBLE PRECISION | 청산 시 수익률 |
| opened_at | TIMESTAMPTZ NOT NULL | 포지션 오픈 일시 (yfinance 데이터 기준일, FR-043) |
| closed_at | TIMESTAMPTZ | 청산 일시 |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### reports (에이전트별 요약, 사이클마다 1건 — FK 변경)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_job_id | BIGINT NOT NULL FK → schedule_jobs | **[CHANGED]** schedule_id → schedule_job_id (FR-039) |
| position_id | BIGINT FK → positions | 미보유 시 NULL |
| market_report ~ pipeline_strategy | TEXT 등 | 기존과 동일 (13개 요약 컬럼 + 결정/PA 컬럼) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

> 제외: sentiment_report (시의성), news_report (시의성, bull/bear 논거에 이미 반영)
> 각 요약 컬럼 목표: 200~400 토큰

#### trades (개별 BUY/SELL 액션 — 기존 + 통화)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| position_id | BIGINT NOT NULL FK → positions | 소속 포지션 |
| report_id | BIGINT NOT NULL FK → reports | 이 매매를 만든 분석 |
| action | TEXT NOT NULL | 'BUY' / 'SELL' |
| shares | DOUBLE PRECISION NOT NULL | 수량 (소수점 지원) |
| price | DOUBLE PRECISION NOT NULL | 체결 가격 |
| currency | TEXT NOT NULL DEFAULT 'USD' | **[NEW]** 매매 통화 (FR-040) |
| executed_at | TIMESTAMPTZ NOT NULL | **[CHANGED]** datetime.now() → yfinance 데이터 기준일 (FR-043) |

#### reflections (청산 시 반성에이전트 산출물 — FR-052 usefulness_score 추가)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| position_id | BIGINT NOT NULL FK → positions | 소속 포지션 |
| reflection | TEXT NOT NULL | 반성문 전체 |
| key_lessons | TEXT | 핵심 교훈 요약 (RAG query용) |
| outcome | TEXT | 'win' / 'loss' (FR-047: `>= 0` → win 통일) |
| return_pct | DOUBLE PRECISION | 수익률 |
| market | TEXT | 거래소/시장 (nullable) |
| sector | TEXT | 섹터 (nullable) |
| industry | TEXT | 산업 (nullable) |
| usefulness_score | DOUBLE PRECISION NOT NULL DEFAULT 50 | **[NEW]** RAG Validator가 ±1 조정. 40 미만 시 검색 배제 (FR-052, FR-053) |
| created_at | TIMESTAMPTZ NOT NULL | 레코드 생성 일시 |

#### schedule_job_events (에이전트 진행 이벤트 — FK 정리)

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL PK | 자동 증가 |
| schedule_job_id | BIGINT FK → schedule_jobs | 연결된 Job |
| ticker | TEXT | 티커 (비정규화 유지, 빠른 조회용) |
| agent | TEXT | 에이전트명 (Market Analyst, system 등) |
| status | TEXT | running / completed / error / skipped |
| message | TEXT | 상태 메시지 |
| step | INTEGER | 단계 번호 (1~13) |
| phase | TEXT | 단계 그룹 (Data Collection, Investment Debate 등) |
| created_at | TIMESTAMPTZ NOT NULL | 기록 일시 |

> **[REMOVED]** `schedule_id` 컬럼 — `schedule_job_id`로 충분 (FR-039)
> UNIQUE INDEX `idx_schedule_job_events_unique` ON (schedule_job_id, agent) — 동일 job+agent 조합은 UPSERT

#### Postgres FTS (BM25 검색용) — FR-033

```sql
CREATE INDEX idx_reflections_search
    ON reflections
    USING GIN (to_tsvector('simple', coalesce(reflection, '') || ' ' || coalesce(key_lessons, '')));
```

> rank_bm25 라이브러리 제거, Postgres 내장 `to_tsvector` + `ts_rank_cd` + `plainto_tsquery` 사용

#### 테이블 관계 (FR-039 이후)

```
schedule_configs ─── 1:N ─── schedule_jobs ─── 1:N ─── schedule_job_events
                             schedule_jobs ─── 1:1 ─── reports
                                                       reports ──N:1── positions
                                                                        positions ─── 1:N ─── trades
                                                                        positions ─── 1:0..1 ── reflections
                                                       reports ──1:N── trades (report_id FK)
```

#### 스키마 변경 요약 (FR-039~044 vs 기존)

| 변경 | Before | After |
|------|--------|-------|
| `schedules` 테이블 | 존재 (8테이블) | **제거** (7테이블) |
| `schedule_configs` | ticker, interval_days, last_data_date | + `current_cycle`, `currency`, `initial_capital`, `market` |
| `schedule_jobs.schedule_id` | FK → schedules | `schedule_config_id` FK → schedule_configs + `scheduled_cycle` |
| `reports.schedule_id` | FK → schedules | `schedule_job_id` FK → schedule_jobs |
| `schedule_job_events.schedule_id` | FK → schedules | **제거** (schedule_job_id로 충분) |
| `positions` | ticker, status, shares, avg_cost | + `currency`, `stop_loss`, `target` |
| `trades` | position_id, action, shares, price | + `currency`, executed_at 의미 변경 |
| `reflections` | — | 변경 없음 |

> ⚠️ 폐기 대상: `eval_results/`, `memory/experience/{agent}.jsonl`, `memory/data/{agent}.jsonl`, `virtual_trade/tickers/`

### 4.3 Configuration

```python
DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),  # 패키지 위치 기준
    "data_cache_dir": "<project_dir>/dataflows/data_cache",
    # Data cache window (환경변수 오버라이드 가능)
    "stock_download_days": int(os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_DAYS", "330")),
    "stock_download_buffer_days": int(os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_BUFFER_DAYS", "300")),
    "stock_cache_stale_days": int(os.getenv("TRADINGAGENTS_STOCK_CACHE_STALE_DAYS", "3")),
    # LLM settings (Google OAuth, no API keys)
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini-cli"),  # "gemini-cli" / "antigravity" / "codex" (FR-050)
    "deep_think_llm": "gpt-5.3-codex" if os.getenv("LLM_PROVIDER", "").lower() == "codex" else "gemini-3-pro-high",
    "quick_think_llm": "gpt-5.3-codex" if os.getenv("LLM_PROVIDER", "").lower() == "codex" else "gemini-3-flash",
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
    "database_path": _get_database_url(),  # SUPABASE_DB_URL / TRADINGAGENTS_DB_URL / DATABASE_URL / POSTGRES_* env vars
    # FR-030: ChromaDB path (Vector store, 환경변수 오버라이드 가능)
    "chroma_path": os.getenv("TRADINGAGENTS_CHROMA_PATH", "<project_dir>/memory/chroma"),
    "default_initial_capital": 5000.0,
    # FR-052: RAG top-K (PA 주입 경험 수, 초기 1 → 추후 2~3)
    "rag_top_k": int(os.getenv("RAG_TOP_K", "1")),
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": _get_env_bool("TRADINGAGENTS_SCHEDULER_ENABLED", False),
}
```

> **Note**: `database_path`는 `SUPABASE_DB_URL`, `TRADINGAGENTS_DB_URL`, `DATABASE_URL` 또는 `POSTGRES_*` 환경변수에서 자동 구성.
> **Note**: fallback 벤더 목록은 config에 없음. `interface.py`의 `VENDOR_LIST` 순서로 자동 적용됨.

### 4.4 Storage Architecture (FR-030, FR-039)

```
Postgres DB (Supabase 호환)     ← 7 테이블 + GIN FTS 인덱스 (FR-039: schedules 제거)
    ├── schedule_configs        ← + current_cycle, currency, initial_capital, market
    ├── schedule_jobs           ← schedule_config_id FK, scheduled_cycle 추가
    ├── schedule_job_events
    ├── positions               ← + currency, stop_loss, target
    ├── reports                 ← schedule_job_id FK
    ├── trades                  ← + currency
    └── reflections

ChromaDB (PersistentClient)     ← 벡터 검색 전용
    └── memory/chroma/
```

> `virtual_trade/`, `eval_results/`, `memory/experience/*.jsonl`, `memory/data/*.jsonl` → 전면 폐기 (FR-030)
> `schedules` 테이블 → **제거** (FR-039). `schedule_jobs`가 흡수

## 5. Exception/Error Policy

| Pattern                   | Inference                                                           |
| ------------------------- | ------------------------------------------------------------------- |
| LLM rate limit (429)      | 30s 대기 후 **동일 모델** 재시도 (최대 5회)                          |
| LLM capacity (503)        | 모델 다운그레이드 fallback chain: `gemini-2.5-pro → gemini-2.5-flash`, `gemini-3-pro-high → gemini-3-pro-low → gemini-3-flash`. 체인 소진 시 exponential backoff |
| Data vendor failure       | 30s 간격 2회 재시도 후 다음 벤더로 fallback, 이력 schedule_jobs 기록 |
| Tool call returns no data | Agent continues with empty report (`report = ""`)                   |
| Decision parse failure    | 스케줄 실패 처리 + 자동 재큐잉 1회 (schedule_jobs 기록)              |
| Agent execution failure   | 스케줄 실패 처리 + 자동 재큐잉 1회 (schedule_jobs 기록)              |
| Data vendor total failure | `DataVendorError` → 스케줄 실패 처리 (재큐잉 없음)                  |
| Current price fetch fail  | yfinance 5일 히스토리 조회 → 2회 재시도(30s 간격) → 실패 시 `DataVendorError` |
| Empty BM25/RAG memory     | PA operates without past reference (`"No past memories found."`)    |
| No new market data        | 스케줄 스킵 처리 (`status='skipped'`, FR-036)                       |
| ADMIN_TOKEN 미설정        | 서버 시작 차단 (`raise RuntimeError`)                               |
| Auto-liquidation trigger  | return_pct가 stop_loss/target 또는 ±30% 초과 시 PA 거치지 않고 즉시 청산 (FR-042). stop_loss ≥ target 역전 값은 무시 |

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
| 2026-02-25 | add_requirement | proposal_v5_not_impl.md → FR-051~054 추가 (4개). RAG 맥락 인식 검색(쿼리 enrichment), RAG 검색 파이프라인 재설계(RRF→usefulness 순서, top-K, 하드 플로어 40), RAG Validator(usefulness_score ±1), 매매검증 검색. reflections 테이블 usefulness_score 컬럼 추가. Configuration에 RAG_TOP_K 환경변수 추가 |
| 2026-02-24 | code_sync       | FR-038~050 Status: Designed→Implemented (코드 전수 검증). metrics/positions `?currency=` 서버필터 → FE 클라이언트 필터링으로 정정. position.opened_at을 yfinance 데이터 기준일로 통일 (FR-043). 하단 6탭(회고 추가). CronTrigger timezone 파라미터 명시. deep_think_llm/quick_think_llm codex 조건 분기 반영 |
| 2026-02-24 | code_fix        | A-1: `_get_latest_close()` 전일종가 가드 제거 → 항상 최신 확정 종가 사용. A-2: FE 통화 표시 `formatAmount`/`formatSignedAmount` 공용화, KRW ₩ 지원. A-3: PA 프롬프트 MODIFY 제거(BUY/SELL/HOLD만). B-1~6: 데드코드 정리(`_get_current_price`, `_ticker_intervals`, reflection DEPRECATED 메서드), `_requeued_job_ids` discard, console.log 삭제, Reflections 필터 리셋. C-2: stop_loss≥target 역전 검증 |
| 2026-02-24 | add_requirement | issues_20260223.md 기반 FR-038~050 추가 (13개). DB 스키마 7테이블 재설계(schedules 제거), 통화 지원, 자동 청산, 독립 자금, 시장별 스케줄, 매매 시점 보정, Closed 포지션 UI, Reflections UI, Codex 프로바이더 |
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
| Last synced    | 2026-02-25 (proposal_v5 → FR-051~054 추가) |
| Analysis scope | `packages/tradingagents/` + `apps/` (Python + Svelte) |
| Skill version  | reverse 2.0.0                                |
