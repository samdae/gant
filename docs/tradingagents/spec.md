# TradingAgents Requirements

> ⚠️ This document was reverse-engineered from code, then reinforced with proposal.md.

## 0. Requirement Summary

| Req ID | Category | Requirement | Priority | Status |
|--------|----------|-------------|----------|--------|
| FR-001 | Analysis | Multi-agent market analysis pipeline (4 analysts) | High | Implemented |
| FR-002 | Debate | Bull vs Bear investment debate with configurable rounds | High | Implemented |
| FR-003 | Decision | Research Manager synthesizes debate → investment plan | High | Implemented |
| FR-004 | Trading | Trader agent generates BUY/HOLD/SELL proposal | High | Implemented |
| FR-005 | Risk | 3-way risk debate (Aggressive/Conservative/Neutral) | High | Implemented |
| FR-006 | Risk | Risk Manager renders final trade decision | High | Implemented |
| ~~FR-007~~ | ~~Memory~~ | ~~BM25-based situation memory for agent reflection~~ | ~~Critical~~ | Superseded by FR-015 |
| FR-008 | Learning | Post-decision reflection writes lessons to memory | Critical | Implemented |
| FR-009 | Signal | LLM-based signal extraction (BUY/HOLD/SELL from text) | Medium | Implemented |
| FR-010 | Data | Multi-vendor data fetching with fallback (yfinance → Alpha Vantage) | Medium | Implemented |
| FR-011 | LLM | OAuth-based Gemini access (no API key, token refresh) | Medium | Implemented |
| FR-012 | Resilience | Rate limit (429) and capacity (503) retry with model downgrade | Medium | Implemented |
| FR-013 | Validation | 가상 매매 추적 — 티커별 trade.json/reports.json으로 분석 정확도 검증 | High | Designed |
| FR-014 | Agent | Portfolio Agent — 기존 전략 + 새 분석 종합하여 매매 행동 결정 (deep_think_llm) | High | Designed |
| FR-015 | Memory | Hybrid RAG (BM25 + Vector) — 영속성 있는 메모리로 FR-007 교체 | Critical | Designed |
| FR-016 | Scheduling | 스케줄 기반 반복 분석 (1 스케줄 = 1 티커, 주기 개별 설정) | Medium | Designed |
| FR-017 | Analysis | 포지션 인식 분석 — AgentState에 current_position 추가, 에이전트 프롬프트 주입 | Medium | Designed |
| FR-018 | Learning | 구조화된 reflect_and_remember 입력 (ticker, return_pct, holding_days 등) | High | Designed |
| FR-019 | Learning | 부트스트랩 태깅 — has_memory 플래그로 Memory 유무 비교 기준선 | Medium | Designed |

> **Status**: `Implemented` = 코드 존재, `Draft` = proposal.md에서 추출 (미구현)
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

## 3. Feature Specifications

### 3.1 Core Features

| Feature | Description | Confidence |
|---------|-------------|------------|
| Market Analysis Pipeline (FR-001) | 4개 전문 분석가(시장, 소셜, 뉴스, 펀더멘탈)가 순차 분석 후 리포트 생성 | ✅ High |
| Investment Debate (FR-002, FR-003) | Bull/Bear 리서처가 N라운드 토론 후 Research Manager가 판결 | ✅ High |
| Trader Decision (FR-004) | 투자 계획을 기반으로 구체적 BUY/HOLD/SELL 제안 생성 | ✅ High |
| Risk Assessment (FR-005, FR-006) | Aggressive/Conservative/Neutral 3자 토론 후 Risk Manager 최종 판결 | ✅ High |
| Reflection & Learning (FR-008, FR-015) | Hybrid RAG(BM25+Vector)로 유사 상황 조회 + 반성문 생성(LLM) → 영속 메모리에 저장 | ✅ High |
| Multi-vendor Data (FR-010) | yfinance를 기본으로 하되, 실패 시 Alpha Vantage로 자동 fallback | ✅ High |
| OAuth LLM Access (FR-011, FR-012) | API key 없이 Google OAuth로 Gemini 접근, rate limit 시 모델 다운그레이드 | ✅ High |
| Virtual Trading Validation (FR-013, FR-014) | 가상 매매로 분석 결과를 추적·검증, Portfolio Agent가 전략 관리 | ✅ High |
| Scheduled Analysis (FR-016) | 티커별 주기적 반복 분석, 연속 분석으로 전략 유효성 추적 | ✅ Medium |
| Position-Aware Analysis (FR-017) | 현재 포지션 컨텍스트를 에이전트에 주입하여 더 정확한 판단 | ✅ Medium |
| Structured Learning (FR-018, FR-019) | 구조화된 반성 입력 + 부트스트랩 태깅으로 정량적 학습 효과 측정 | ✅ High |

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

#### 3.2.2 Memory & Reflection

- **Memory Storage**: `FinancialSituationMemory` 클래스 → Hybrid RAG (BM25 + Vector) 교체 예정 (FR-015)
- **Memory Scope**: 에이전트별 독립 메모리 (Bull, Bear, Trader, Judge, Risk Manager), 티커 구분 없이 통합
- **Reflection Trigger**: `reflect_and_remember(구조체)` — ticker, return_pct, holding_days, analysis_count, market_condition, has_memory (FR-018)
- **Memory Read**: 각 에이전트가 실행 시 현재 상황과 유사한 과거 메모리를 조회하여 프롬프트에 포함
- **Persistence**: JSON/파일 기반 persist (FR-015), `memory/{agent_name}.json`
- **Bootstrap**: 초기 분석에 `has_memory: false` 태깅 → Memory 효과 정량 측정 기준선 (FR-019)

#### 3.2.3 Virtual Trading Validation (NEW)

- **목적**: AI 분석이 실제로 맞았는지 가상 매매로 추적·검증
- **구조**: 1 스케줄 = 1 티커, 종목별 독립 자금 ($1,000 기본)
- **흐름**: G-ANT 분석 → Portfolio Agent → trade.json 업데이트 → SELL 시 청산 + 수익률 → Memory 학습
- **Portfolio Agent**: deep_think_llm, trade.json + reports.json 읽기 → 전략 유지/수정/폐기 판단
- **분석 주기**: 기본 4일 간격 (yfinance 뉴스 7일 제공 기준), 종목별 개별 설정 가능
- **SELL 정책**: Phase 0~3 = 전량 청산, Phase 4부터 비중 조절로 진화
- **크로스 티커 학습**: 모든 티커의 분석+매매 결과가 하나의 RAG에 통합

#### 3.2.3 Data Fetching

- **Transient**: 데이터는 적재하지 않고 분석 시점에 1회성 fetch
- **Vendors**: yfinance (기본), Alpha Vantage (fallback)
- **Categories**: Stock OHLCV, Technical Indicators (8개 선택 가능), Fundamentals (재무제표 4종), News (종목/글로벌)
- **Vendor Routing**: `route_to_vendor()` → 설정 기반 벤더 선택 + 실패 시 자동 fallback

## 4. Data Contracts

### 4.1 Main Entities

| Entity | Fields | Source |
|--------|--------|--------|
| `AgentState` (TypedDict) | messages, company_of_interest, trade_date, market_report, sentiment_report, news_report, fundamentals_report, investment_debate_state, risk_debate_state, investment_plan, trader_investment_plan, final_trade_decision, sender, current_position (FR-017) | Code + Draft |
| `InvestDebateState` (TypedDict) | history, current_response, bull_history, bear_history, judge_decision, count | Code |
| `RiskDebateState` (TypedDict) | history, current_aggressive/conservative/neutral_response, aggressive/conservative/neutral_history, latest_speaker, judge_decision, count | Code |
| `FinancialSituationMemory` | name, documents, recommendations, bm25 → **Hybrid RAG로 교체 예정** (bm25 + vector + persist) | Code → FR-015 |
| `DEFAULT_CONFIG` (Dict) | llm_provider, deep_think_llm, quick_think_llm, backend_url, data_vendors, tool_vendors, results_dir, project_dir, data_cache_dir, max_debate_rounds, max_risk_discuss_rounds, max_recur_limit | Code |

### 4.2 Virtual Trading Entities (NEW)

#### trade.json (per ticker)

```json
{
  "ticker": "NVDA",
  "initial_capital": 1000.0,
  "cash": 485.0,
  "status": "open",
  "positions": [
    { "shares": 1, "entry_price": 250.0, "entry_date": "2024-05-10" }
  ],
  "strategy": {
    "stop_loss": 260.0,
    "target": 300.0,
    "next_action": "풀백 시 $264-266에서 50% 추가매수"
  },
  "history": [
    {
      "date": "2024-05-10",
      "analysis_no": 1,
      "decision": "BUY",
      "action": "25% 진입 ($250 x 1주)",
      "rationale": "첫 진입. 풀백 대기 전략 수립.",
      "cash_after": 750.0
    }
  ]
}
```

> 청산 시 추가 필드: `closed_date`, `realized_return_pct`, `total_invested`, `total_returned`, `profit`

#### reports.json (per ticker)

분석 결과 배열. 각 항목은 G-ANT 파이프라인 1회 실행의 출력.

#### reflect_and_remember 입력 구조체 (FR-018)

```python
reflect_and_remember({
    "ticker": "NVDA",
    "return_pct": 15.7,
    "holding_days": 22,
    "analysis_count": 3,
    "market_condition": "bullish",
    "has_memory": True,
})
```

> ⚠️ 이 입력 구조는 처음부터 확정. 나중에 변경 시 기존 Memory 데이터와 호환 불가.

### 4.3 Configuration

```python
DEFAULT_CONFIG = {
    "project_dir": os.path.abspath("."),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
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
}
```

> **Note**: fallback 벤더 목록은 config에 없음. `interface.py`의 `VENDOR_LIST` 순서로 자동 적용됨.

### 4.4 Virtual Trading Directory Structure (NEW)

```
virtual_trade/
└── tickers/
    ├── NVDA/
    │   ├── trade.json      ← 매매 상태 + 이력
    │   └── reports.json    ← 분석 이력 (배열)
    └── AAPL/
        ├── trade.json
        └── reports.json
```

## 5. Exception/Error Policy

| Pattern | Inference |
|---------|-----------|
| LLM rate limit (429) | 30s retry → model downgrade (pro → flash) → retry |
| LLM capacity (503) | Exponential backoff, model downgrade |
| Data vendor failure | Fallback to next vendor in chain |
| Tool call returns no data | Agent continues with empty report (`report = ""`) |
| Empty BM25 memory | Agents operate without past reference (`"No past memories found."`) |

## 6. Unclear Items

| Item | Status | Notes |
|------|--------|-------|
| ~~Memory persistence~~ | ✅ Resolved by FR-015 | Hybrid RAG + JSON persist |
| ~~Analysis result storage~~ | ✅ Resolved by FR-013 | reports.json per ticker |
| ~~Performance metrics~~ | ✅ Resolved by FR-013, FR-019 | 가상 매매 수익률 + 부트스트랩 태깅으로 추적 |
| ~~Multi-ticker orchestration~~ | ✅ Resolved by FR-016 | 스케줄 기반 티커별 반복 분석 |

## 7. Priority

| Rank | Feature | Rationale |
|------|---------|-----------|
| 1 | Hybrid RAG Memory (FR-015) | 선행 조건. 영속 메모리 없이 학습 불가 |
| 2 | Structured Learning (FR-018, FR-019) | RAG와 함께 확정해야 데이터 호환성 유지 |
| 3 | Virtual Trading (FR-013, FR-014) | 분석 정확도 검증 — 핵심 가치 |
| 4 | Agent Pipeline (FR-001~006, FR-008) | 분석 자체의 품질을 결정하는 기반 (구현 완료) |
| 5 | Scheduled Analysis (FR-016) | 반복 분석 자동화 |
| 6 | Position-Aware Analysis (FR-017) | 기존 에이전트 수정 필요, 가장 마지막 |
| 7 | Data Fetching / LLM Resilience (FR-010~012) | 안정적 실행 보장 (구현 완료) |

---

## Reinforcement History

| Date | Type | Changes |
|------|------|--------|
| 2026-02-11 | add_requirement | proposal.md → FR-013~019 추가 (7개 신규 요구사항) |
| 2026-02-11 | fill_blank | 4개 Unclear Items 해결 (FR-013~016으로 커버) |
| 2026-02-11 | correct | FR-007 → Superseded by FR-015, Non-goals 수정 |

---

## Reverse Extraction Info

| Item | Content |
|------|------|
| Generated | 2026-02-11 |
| Analysis scope | `tradingagents/` (47 Python files, cli 제외) |
| Skill version | reverse 2.0.0 |
