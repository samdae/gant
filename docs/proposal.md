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

### 1 스케줄러 = 1 티커

```
스케줄 #1: NVDA → 4일마다 분석
스케줄 #2: AAPL → 4일마다 분석
스케줄 #3: TSLA → 7일마다 분석 (종목별 주기 개별 설정 가능)
```

### 각 스케줄 실행 시

```
┌─ 티커 스케줄 1회 실행 ────────────────────────────────┐
│                                                         │
│  1. G-ANT 분석 (기존 12개 에이전트 파이프라인)          │
│     → 시장분석, 토론, 리스크 → BUY/HOLD/SELL + 의도     │
│     → reports.json에 분석 결과 추가                      │
│                                                         │
│  2. Portfolio Agent (NEW, deep_think_llm)                │
│     → trade.json + reports.json 읽기                     │
│     → 기존 전략 + 새 분석을 종합하여 행동 결정           │
│     → trade.json 업데이트                                │
│                                                         │
│  3. 매도 판단 시                                        │
│     → 전략에 따라 부분/전량 매도 → 수익률 계산          │
│     → 전량 청산 시 RAG에 (분석+결과) 쌍으로 WRITE       │
│     → reflect_and_remember(수익률) 자동 호출             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 분석 주기

- **기본: 4일 간격** — yfinance 뉴스가 최근 7일 내 기사 제공, 4일이면 새 뉴스 충분 + 연속성 유지
- 종목별 주기 개별 설정 가능
- 향후: ATR(변동성) 기반 주기 자동 조절

---

## 데이터 구조

### 디렉토리

```
virtual_trade/
└── tickers/
    ├── NVDA/
    │   ├── trade.json      ← 매매 상태 + 이력
    │   └── reports.json    ← 분석 이력 (배열)
    ├── AAPL/
    │   ├── trade.json
    │   └── reports.json
    └── TSLA/
        ├── trade.json
        └── reports.json
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

→ `reflect_and_remember()` 자동 호출 (구조화된 입력):

```python
reflect_and_remember({
    "ticker": "NVDA",
    "return_pct": 15.7,
    "holding_days": 22,
    "analysis_count": 3,          # 몇 번 분석 후 청산했는지
    "market_condition": "bullish", # 분석 시점 시장 요약
    "has_memory": True,            # RAG 참조 여부 (부트스트랩 기간 비교용)
})
```

> ⚠️ 이 입력 구조는 **처음부터 확정**. 나중에 바꾸면 기존 Memory 데이터와 호환 불가.
> 안 쓰더라도 데이터가 있으면 나중에 활용 가능하지만, 없으면 과거 데이터를 다시 만들 수 없다.

---

## Portfolio Agent 동작 규칙

### 프롬프트 판단 프레임

Portfolio Agent 프롬프트에 다음 판단 기준을 명시적으로 포함해야 한다:

| 조건 | 트리거 | 행동 |
| ---- | ------ | ---- |
| **전략 유지** | 새 분석의 방향성이 기존과 동일 | 기존 전략 유지, 확신 강화 기록 |
| **전략 수정** | 방향 전환 권고, stop-loss 근접, 또는 확신도 하락 | 전략 필드 업데이트 (비중/타점/목표가 조정) |
| **전략 폐기** | 새 분석이 SELL이거나 근본적 전제가 무너짐 | 전량 청산 → 수익률 → Memory 학습 |

> 확신도 변화도 판단 기준에 포함: 방향은 같지만 확신이 약해진 경우(예: "강력 매수" → "약한 매수")는 전략 수정으로 분류.

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
| SELL       | 있음        | 전략에 따라 부분/전량 매도 → 수익률 → Memory 학습 |
| SELL       | 없음        | 무시 (팔 게 없음)                           |

> BUY/SELL = 방향성, 전략이 실행 디테일(수량, 타점, 비중)을 결정. 매수·매도 모두 PA가 전략에 따라 수량 결정.

### BUY/SELL = 방향, 전략 = 디테일

> **BUY/SELL은 방향성**이고, **전략이 실제 행동의 디테일**(금액, 비중, 타점)을 결정한다.
> 첫 BUY의 전략이 마스터 플랜. 이후 BUY는 "확신 강화"로 기록.
> 상황이 급변하면 (예: 풀백 발생, 목표가 변경) Portfolio Agent가 전략을 수정하고 투자금 산정.

---

## RAG 아키텍처 (Hybrid BM25 + Vector)

### 왜 Hybrid인가

| 검색 방식  | 잘 찾는 것                                  | 못 찾는 것                                         |
| ---------- | ------------------------------------------- | -------------------------------------------------- |
| BM25       | "NVDA RSI 과매수" → 과거 "NVDA RSI 70 초과" | "업종 자체가 하락 추세" → 과거 유사 업종 실패 사례 |
| Vector     | "좋아 보이는데 망한 케이스" → 의미적 유사   | 정확한 종목명/지표명 매칭                          |
| **Hybrid** | **둘 다**                                   | -                                                  |

```
검색 스코어 = Σ 1/(60 + rank_i(d))  (RRF — Reciprocal Rank Fusion)
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

### 부트스트랩 기간 태깅

초기 몇 달은 RAG가 비어있어 Memory 기반 통찰이 없다. 이 기간의 분석 품질이 낮을 수 있는데, **그게 정상**이다.

- 모든 분석 결과에 `has_memory: true/false` 플래그를 추가
- 이 초기 데이터가 "Memory 없이 판단했을 때 vs Memory 있을 때"의 **비교 기준선**
- 나중에 Memory 시스템의 실제 효과를 정량 측정 가능

### Embedding

- **ChromaDB 내장 ONNX 임베딩** (`all-MiniLM-L6-v2`) 사용. API 호출 비용 없음, 별도 설치 불필요.
- persist: ChromaDB `PersistentClient`로 자동 영속화 (로컬 파일)

---

## 구현 단계

> 순차 진행: RAG가 데이터를 받아야 Portfolio Agent가 의미 있는 테스트를 할 수 있으므로 **Phase 순서를 지키되, 중간 검증 단계를 포함**한다.

### Phase 0: RAG 검색기 (선행 조건, 1일)

- [x] `FinancialSituationMemory` → `HybridMemory`로 교체 완료
  - BM25 (기존 rank_bm25 유지)
  - Vector (ChromaDB 내장 ONNX 임베딩 `all-MiniLM-L6-v2`)
  - RRF 스코어링: `rrf(d) = Σ 1/(60 + rank_i(d))`
- [x] persist: JSONL 기반 저장 + ChromaDB PersistentClient
  - `memory/data/{agent_name}.jsonl` — 모든 티커 통합 (크로스 티커 학습)
- [x] 기존 인터페이스 유지: `add_situations()`, `get_memories()`

### Phase 1: 분석 결과 WRITE (반나절)

- [x] `propagate()` 완료 후 분석 결과를 RAG에 자동 ADD
  - 상황 (시장 상태 요약) + 추천 (BUY/HOLD/SELL + 전략) 저장
  - `has_memory` 플래그 포함 (부트스트랩 기간 태깅)
- [x] `trade.json` 읽기/쓰기 유틸리티 구현
- [x] `reflect_and_remember()` 입력을 구조체로 확장 (ticker, return_pct, holding_days, analysis_count, market_condition, has_memory)

> **🔍 중간 검증**: Phase 1까지 완료 후 실제 `propagate()` 1~2회 실행하여 "분석 → RAG 저장"이 동작하는지 확인. 이 데이터가 Phase 2 테스트의 기반이 된다.

### Phase 2: Portfolio Agent (2~3일)

- [x] Portfolio Agent 프롬프트 설계 (코드보다 프롬프트가 먼저)
  - 전략 유지 / 수정 / 폐기 판단 프레임 포함
  - 확신도 변화 기준 포함
- [x] Portfolio Agent 구현 (deep_think_llm)
  - trade.json 읽기 → G-ANT 결과 읽기 → RAG 조회 → 행동 결정 → trade.json 업데이트
- [x] BUY 연속 규칙: 첫 전략이 마스터 플랜, 이후는 확신 강화 or 전략 수정
- [x] SELL 시: 전략에 따라 부분/전량 매도 → 수익률 계산 → RAG에 WRITE → reflect_and_remember(구조체)

### Phase 3: 스케줄링 (반나절)

- [x] APScheduler 기반 스케줄링 (1 스케줄 = 1 티커, 주기 개별 설정)
- [x] 셀프힐링: 시작 시 config + tickers/ 디렉토리 스캔하여 스케줄 복원

### Phase 4: 포지션 인식 분석 (1~2일)

> ⚠️ 기존 에이전트 코드를 수정하는 유일한 Phase. 위험도가 높으므로 **가장 마지막에 진행**.

- [x] `AgentState`에 `current_position: str` 필드 추가
- [x] `propagate()` 호출 전 trade.json → 포지션 요약 문자열 생성
- [x] Research Manager / Trader / Risk Manager 프롬프트에 포지션 컨텍스트 주입
  - Analyst 4명은 시장 데이터 분석이므로 수정 불필요

### Phase 5: PA 편향 방지 + Experience 아키텍처

> 12에이전트 분석의 객관성을 보장하고, 완료된 매매 사이클을 경험 데이터로 아카이빙하여 학습 기반을 강화한다.

- [ ] **분석플로우 객관성 확보**: FR-017에서 추가한 포지션 주입(Research Manager / Trader / Risk Manager)을 제거. 12에이전트 분석은 포지션 정보 없이 완전 객관적으로 수행.
- [ ] **PA 프롬프트 강화**: PA가 유일하게 포지션 정보를 받는 에이전트로서, 분석 결과(가중치 6) > 과거 경험(가중치 4) 기반 판단. 디바이어싱 지시 포함. HybridMemory에서 과거 매매 기억 검색하여 판단에 활용.
- [ ] **Experience 아카이빙**: 포지션 close 시 `tickers/{TICKER}/` 데이터를 `experience/{TICKER}/{n}/` 으로 이동하고 tickers 초기화. 분석만 하고 포지션을 잡지 않은 경우는 저장하지 않음 (포지션이 있어야 '검증'이 가능).
- [ ] **RAG 소스 전환**: 활성 매매 데이터(tickers/) 대신 완료된 경험(experience/)만 RAG 인덱싱. 미결론 데이터가 학습을 오염시키지 않도록.

---

## 설계 결정 (확정)

1. **초기 자금**: 사용자 설정, 기본값 $1,000. 스케줄 등록 시 지정.
2. **멀티 티커 자금 공유: 없음**. 목적은 가상 투자가 아닌 **분석 정확도 검증**. 종목별 독립 자금.
3. **SELL 정책**: BUY/SELL = 방향성, 전략이 실행 디테일(수량, 타점, 비중)을 결정. 매수·매도 모두 PA가 전략에 따라 수량 결정 (부분 매수/매도 지원). 분석-실행-결과의 반복으로 RAG에 풍부한 데이터가 축적되어 통찰력이 자기 개선된다.
4. **Embedding**: ChromaDB 내장 ONNX 임베딩 (`all-MiniLM-L6-v2`). API 호출 비용 없음, 별도 설치 불필요.
5. **메모리 구조**: 에이전트별 메모리 파일이지만 **티커 구분 없이 통합**. 매매 인사이트는 종목 불문 축적.
6. **reflect_and_remember 입력 구조화**: 처음부터 구조체 (ticker, return_pct, holding_days, analysis_count, market_condition, has_memory). 나중에 변경 시 기존 데이터와 호환 불가하므로 초기 확정.
7. **부트스트랩 기간 태깅**: 모든 분석에 `has_memory` 플래그. Memory 유무에 따른 수익률 비교 기준선.
8. **분석플로우 객관성**: 12에이전트 파이프라인은 포지션 정보 없이 완전 객관적 분석. 포지션 기반 판단은 PA에게만 위임.
9. **Experience 아카이빙**: 완료된 매매 사이클은 `experience/{TICKER}/{n}/`에 보관. RAG는 experience만 인덱싱 (활성 데이터 제외).

### 크로스 티커 학습

모든 티커의 분석 + 매매 결과가 **하나의 RAG**에 모인다.
→ NVDA 분석 시 과거 AAPL/TSLA 실패 사례도 참조 가능.
→ 데이터가 쌓일수록 종목 간 패턴 인식이 날카로워짐.
