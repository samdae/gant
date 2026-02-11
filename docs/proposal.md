# Paper Trading & Tracking — 설계 제안서

## 개요

G-ANT Trader의 분석 결과를 가상 매매로 검증하는 시스템.
"AI가 BUY라고 했는데, 진짜 올랐어?"를 자동으로 추적하고, 결과를 Memory에 피드백한다.

---

## 핵심 컨셉

### 기존 G-ANT vs Paper Trading

```
기존:   분석 1회 → BUY/HOLD/SELL 판단 → 끝
Paper:  분석 N회 반복 → 의도 누적 → SELL 나올 때까지 포지션 유지 → 자동 청산 + 학습
```

### 왜 단발 분석이 아닌 연속 분석인가

G-ANT의 분석 결과는 단순한 BUY/SELL이 아니다. 아래처럼 **구체적 전략**을 포함한다:

> "25% 진입하고, 풀백 시 $264-266에서 50% 추가매수, 손절 $260, 목표 $300"

이 전략은 시간에 걸쳐 실행되어야 한다.
따라서 주기적으로 재분석하며, 이전 전략과 새 분석을 종합하여 행동을 결정해야 한다.

---

## 시스템 구조

```
┌─ 스케줄러 (4일마다) ──────────────────────────────────┐
│                                                         │
│  1. G-ANT 분석 (기존 12개 에이전트 파이프라인)          │
│     → 시장분석, 토론, 리스크 → BUY/HOLD/SELL + 의도     │
│                                                         │
│  2. Portfolio Agent (NEW, deep_think_llm)                │
│     → trade.json 읽기 (없으면 생성, $1000 시작)         │
│     → G-ANT 분석 결과 읽기                              │
│     → 기존 전략 + 새 분석을 종합하여 행동 결정           │
│     → trade.json 업데이트                                │
│                                                         │
│  3. SELL 판단 시                                        │
│     → 전량 청산 → 수익률 계산                           │
│     → reflect_and_remember(수익률) 자동 호출             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 분석 주기

- **기본: 4일 간격** — yfinance 뉴스가 최근 7일 내 기사를 가져오므로, 4일이면 새 뉴스가 충분히 쌓이면서 연속성 유지
- 1~2주는 급변장에서 너무 느릴 수 있음
- 향후: ATR(변동성) 기반으로 종목별 주기 자동 조절 가능

---

## 데이터 구조

### 디렉토리

```
virtual_trade/
└── tickers/
    ├── NVDA/
    │   └── trade.json
    ├── AAPL/
    │   └── trade.json
    └── TSLA/
        └── trade.json
```

### trade.json 스키마

```json
{
  "ticker": "NVDA",
  "initial_capital": 1000.0,
  "cash": 485.0,
  "status": "open",
  "positions": [
    { "shares": 1, "entry_price": 250.0, "entry_date": "2024-05-10" },
    { "shares": 1, "entry_price": 265.0, "entry_date": "2024-05-18" }
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
    },
    {
      "date": "2024-05-14",
      "analysis_no": 2,
      "decision": "HOLD",
      "action": "없음",
      "rationale": "풀백 미발생. 기존 전략 유지. 확신 강화.",
      "cash_after": 750.0
    },
    {
      "date": "2024-05-18",
      "analysis_no": 3,
      "decision": "BUY",
      "action": "추가매수 50% ($265 x 1주)",
      "rationale": "풀백 발생. 기존 전략대로 추가 진입.",
      "cash_after": 485.0
    }
  ]
}
```

### 청산 시 (status → closed)

```json
{
  "status": "closed",
  "closed_date": "2024-06-01",
  "realized_return_pct": 15.7,
  "total_invested": 515.0,
  "total_returned": 596.0,
  "profit": 81.0
}
```

→ `reflect_and_remember(15.7)` 자동 호출

---

## Portfolio Agent 동작 규칙

### 첫 실행 (trade.json 없음)

1. `trade.json` 생성: `initial_capital: $1000`, `status: "open"`, `positions: []`
2. G-ANT 분석 결과 읽기
3. BUY 판단 시 → 전략에 따라 포지션 진입 + strategy 필드 작성
4. HOLD 판단 시 → 기록만 남기고 대기

### 후속 실행 (trade.json 존재)

1. 기존 trade.json 읽기 (현재 포지션, 전략, 히스토리)
2. G-ANT 분석 결과 읽기
3. 판단 분기:

| G-ANT 판단 | 기존 포지션 | Portfolio Agent 행동                        |
| ---------- | ----------- | ------------------------------------------- |
| BUY        | 없음        | 신규 진입 (전략에 따라 금액/비중 결정)      |
| BUY        | 있음        | 기존 전략 참조 → 추가매수 or 확신 강화 기록 |
| HOLD       | 있음        | 턴 종료. 모니터링 기록                      |
| HOLD       | 없음        | 턴 종료. 기록만                             |
| SELL       | 있음        | 전량 청산 → 수익률 → Memory 학습            |
| SELL       | 없음        | 무시 (팔 게 없음)                           |

### BUY/SELL = 방향, 전략 = 디테일

> **BUY/SELL은 방향성**이고, **전략이 실제 행동의 디테일**(금액, 비중, 타점)을 결정한다.
> 첫 BUY의 전략이 마스터 플랜. 이후 BUY는 "확신 강화"로 기록.
> 상황이 급변하면 (예: 풀백 발생, 목표가 변경) Portfolio Agent가 전략을 수정하고 투자금 산정.
> SELL이 나오면 전량 청산 — 부분 청산 없음. 청산 시점은 시스템이 결정.

---

## RAG 아키텍처 (Hybrid BM25 + Vector)

### 왜 Hybrid인가

| 검색 방식  | 잘 찾는 것                                  | 못 찾는 것                                         |
| ---------- | ------------------------------------------- | -------------------------------------------------- |
| BM25       | "NVDA RSI 과매수" → 과거 "NVDA RSI 70 초과" | "업종 자체가 하락 추세" → 과거 유사 업종 실패 사례 |
| Vector     | "좋아 보이는데 망한 케이스" → 의미적 유사   | 정확한 종목명/지표명 매칭                          |
| **Hybrid** | **둘 다**                                   | -                                                  |

```
검색 스코어 = α × BM25_score + (1-α) × cosine_similarity
```

### READ/WRITE 의존관계

```
┌─────────────────────────────────────────────────────────┐
│              Hybrid RAG 검색기 (persist)                  │
│          BM25 index + Vector embeddings (JSON)           │
│                                                          │
│  ┌─ READ ───────────────────────────────────────┐        │
│  │  • 분석 에이전트 (Bull/Bear/Trader 등)       │        │
│  │    → "이전에 비슷한 상황에서 어떤 판단했지?" │        │
│  │  • Portfolio Agent                            │        │
│  │    → "비슷한 매매에서 결과가 어땠지?"        │        │
│  └──────────────────────────────────────────────┘        │
│                                                          │
│  ┌─ WRITE ──────────────────────────────────────┐        │
│  │  • 분석 플로우 완료 후                       │        │
│  │    → 분석 상황 + 의도 + 판단을 ADD           │        │
│  │  • Portfolio Agent 청산 후                    │        │
│  │    → 매매 결과 + 수익률 + 반성을 ADD          │        │
│  │    → reflect_and_remember(수익률) 호출        │        │
│  └──────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────┘

⚠️ 읽는 놈과 쓰는 놈이 같은 놈들.
   처음엔 RAG가 비어있으므로 과거 참조 없이 돌아가고,
   데이터가 쌓이면서 점점 학습.
```

### 부트스트랩 순서

```
1. RAG 검색기 구현 (persist 가능한 빈 껍데기) ← 이게 없으면 아무것도 안 됨
2. 분석 플로우 → 결과를 RAG에 WRITE           ← 데이터를 넣어야 READ도 됨
3. Portfolio Agent → 매매 결과를 RAG에 WRITE
4. 이후 분석부터: RAG READ로 과거 학습 시작   ← 여기서부터 진짜 가치
```

### Embedding

- 로컬 모델 (`sentence-transformers`) 사용. API 호출 비용 없음, 품질 차이 미미.
- persist: 임베딩 벡터를 numpy/JSON으로 저장, 또는 ChromaDB 로컬 파일

---

## 구현 단계

> ⚠️ 분석 플로우, Portfolio Agent, RAG는 상호 의존적이므로 순차 개발이 아닌 **동시 진행**.

### Phase 0: RAG 검색기 (선행 조건, 1일)

- [ ] `FinancialSituationMemory` → Hybrid RAG로 교체
  - BM25 (기존 rank_bm25 유지)
  - Vector (로컬 sentence-transformers)
  - 가중 합산 스코어링
- [ ] persist: JSON/파일 기반 저장/로드
  - `memory/{agent_name}.json` — 모든 티커 통합 (크로스 티커 학습)
- [ ] 기존 인터페이스 유지: `add_situations()`, `get_memories()`

### Phase 1: 분석 결과 WRITE (반나절)

- [ ] `propagate()` 완료 후 분석 결과를 RAG에 자동 ADD
  - 상황 (시장 상태 요약) + 추천 (BUY/HOLD/SELL + 전략) 저장
- [ ] `trade.json` 읽기/쓰기 유틸리티 구현

### Phase 2: Portfolio Agent (2~3일)

- [ ] Portfolio Agent 구현 (deep_think_llm)
  - trade.json 읽기 → G-ANT 결과 읽기 → RAG 조회 → 행동 결정 → trade.json 업데이트
- [ ] BUY 연속 규칙: 첫 전략이 마스터 플랜, 이후는 확신 강화 or 전략 수정
- [ ] SELL 시: 청산 → 수익률 계산 → RAG에 WRITE → reflect_and_remember()

### Phase 3: 스케줄링 + 멀티 티커 (반나절)

- [ ] cron / Windows Task Scheduler 설정 (기본 4일 간격)
- [ ] 멀티 티커 순차 실행
- [ ] 실행 로그 저장

---

## 설계 결정 (확정)

1. **초기 자금**: 사용자 설정, 기본값 $1,000. 스케줄 등록 시 지정.
2. **멀티 티커 자금 공유: 없음**. 목적은 가상 투자가 아닌 **분석 정확도 검증**. 종목별 독립 자금.
3. **BUY/SELL = 방향, 전략 = 디테일**: BUY/SELL은 방향을 의미하고, 구매 금액/비중/타점은 전략이 결정. SELL 시 전량 청산 (부분 청산 없음). 청산 시점은 시스템이 결정하므로 수동 개입 불필요.
4. **Embedding**: 로컬 모델 (`sentence-transformers`). API 호출 비용 없음, 품질 차이 미미.
5. **메모리 구조**: 에이전트별 메모리 파일이지만 **티커 구분 없이 통합**. 매매 인사이트는 종목 불문 축적.

### 크로스 티커 학습

모든 티커의 분석 + 매매 결과가 **하나의 RAG**에 모인다.
→ NVDA 분석 시 과거 AAPL/TSLA 실패 사례도 참조 가능.
→ 데이터가 쌓일수록 종목 간 패턴 인식이 날카로워짐.
