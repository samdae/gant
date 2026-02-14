# Paper Trading & Tracking — 설계 제안서 v3

> v1 → v3 변경 이유: 회고(반성) 구조의 논리 오류 수정, 파일 기반 → DB 전환, RAG 아키텍처 단순화

---

## 변경 요약 (v1 → v3)

| 항목 | v1 (기존) | v3 (변경) |
|------|----------|----------|
| 저장소 | 파일 기반 (JSON/JSONL) | **SQLite** + ChromaDB |
| 회고 주체 | 5개 에이전트 개별 반성 | **PA(반성에이전트) 1곳 집중** |
| 회고 시점 | 청산 직후 즉시 | 요약에이전트 → **반성에이전트 순차** |
| 리포트 저장 | 1개 summary TEXT | **13개 개별 컬럼** (에이전트별 요약) |
| BM25 | `rank_bm25` 라이브러리 + JSONL | **SQLite FTS5** (내장, 추가 의존성 0) |
| 아카이브 | 파일 디렉토리 이동 | **`status = 'closed'`** (SQL UPDATE 1줄) |
| RAG READ | 5개 에이전트 각각 읽기 | **PA만 읽기** |
| RAG WRITE | 5개 에이전트 각각 쓰기 | **반성에이전트만 쓰기** |

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

## 워크플로우

### 기본 사이클 (매 스케줄 실행 시)

```
┌─ 티커 스케줄 1회 실행 ─────────────────────────────────────────────┐
│                                                                      │
│  1. G-ANT 분석 (기존 12개 에이전트 파이프라인)                      │
│     → 시장분석, 토론, 리스크 → 최종결론 (BUY/HOLD/SELL + 전략)     │
│     ※ 12에이전트는 포지션 정보 없이 완전 객관적으로 분석           │
│                                                                      │
│  2. PA (Portfolio Agent, deep_think_llm)                             │
│     → 최종결론 읽기                                                  │
│     → 포지션 있으면 positions/trades 참조                            │
│     → 반성 데이터 있으면 RAG 검색 (Hybrid: ChromaDB + FTS5)         │
│     → 자기 의견(pa_opinion) 작성 + 판단·실행                        │
│     → trades 테이블에 매매 기록 INSERT                               │
│                                                                      │
│  3. 요약에이전트 (quick_thinking_llm)                                │
│     → 12에이전트 raw 산출물 + PA 의견을 에이전트별로 요약            │
│     → reports 테이블에 13개 개별 컬럼으로 INSERT                     │
│     ※ sentiment_report, news_report 제외 (시의성 데이터)            │
│                                                                      │
│  4. 청산 확인 (position.shares == 0?)                                │
│     ├─ NO  → 끝                                                      │
│     └─ YES → 반성에이전트 실행 ───┐                                  │
│                                     │                                │
│  5. 반성에이전트 (청산 시에만)       │                                │
│     → reports 전 사이클 요약 읽기   │                                │
│     → trades 전체 매매 이력 읽기    │                                │
│     → 반성문 작성                   │                                │
│     → SQLite reflections INSERT     │                                │
│     → ChromaDB 벡터 임베딩 저장     │                                │
│     → position status='closed'      │                                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### PA 판단 입력 비율

| 상황 | 입력 구성 |
|------|----------|
| 신규 진입 (포지션 없음, 반성 없음) | 최종결론 = **100%** |
| 신규 진입 (포지션 없음, 반성 있음) | 최종결론 + RAG 반성데이터 |
| 기존 보유 (포지션 있음, 반성 없음) | 최종결론(**6**) : positions/trades(**4**) |
| 기존 보유 (포지션 있음, 반성 있음) | 최종결론(**6**) : positions/trades(**4**) + RAG 반성데이터 |

### PA 행동 분기

| G-ANT 판단 | 기존 포지션 | PA 행동 |
|------------|------------|---------|
| BUY | 없음 | 신규 진입 (전략에 따라 금액/비중 결정) |
| BUY | 있음 | 기존 전략 참조 → 추가매수 or 확신 강화 |
| HOLD | 있음 | 모니터링 기록 |
| HOLD | 없음 | 기록만 |
| SELL | 있음 | 전략에 따라 부분/전량 매도 |
| SELL | 없음 | 무시 (팔 게 없음) |

### 청산 판정

별도 플래그 불필요. PA 실행 후 포지션의 `shares == 0`이면 청산:

```python
# PA 실행 후
if position.shares == 0 and position.status == 'active':
    is_liquidated = True  # 요약 후 반성에이전트로 라우팅
```

---

## 데이터베이스 스키마 (SQLite)

### 테이블 구조

```sql
-- ① 스케줄: 분석 실행 단위
CREATE TABLE schedules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    scheduled_cycle INTEGER NOT NULL,     -- 이 티커의 N번째 분석
    status          TEXT    NOT NULL DEFAULT 'pending',  -- pending/running/done/failed
    created_at      TEXT    NOT NULL      -- ISO 8601
);
CREATE INDEX idx_schedules_ticker ON schedules(ticker);

-- ② 포지션: 하나의 매매 사이클 (진입 → 청산)
CREATE TABLE positions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'active',  -- active/closed
    shares      INTEGER NOT NULL DEFAULT 0,
    avg_cost    REAL,
    return_pct  REAL,                -- 청산 시 계산
    opened_at   TEXT    NOT NULL,    -- ISO 8601
    closed_at   TEXT,                -- 청산 시 기록
    created_at  TEXT    NOT NULL
);
CREATE INDEX idx_positions_ticker_status ON positions(ticker, status);

-- ③ 리포트: 에이전트별 요약 (스케줄마다 1건)
CREATE TABLE reports (
    id                                INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id                       INTEGER NOT NULL REFERENCES schedules(id),
    position_id                       INTEGER REFERENCES positions(id),  -- 미보유 시 NULL
    market_report                     TEXT,   -- 시장 분석 요약
    fundamentals_report               TEXT,   -- 펀더멘탈 분석 요약
    bull_history                      TEXT,   -- 강세 논거 요약
    bear_history                      TEXT,   -- 약세 논거 요약
    investment_debate_judge_decision  TEXT,   -- 투자 토론 판정 요약
    aggressive_history                TEXT,   -- 공격적 리스크 의견 요약
    conservative_history              TEXT,   -- 보수적 리스크 의견 요약
    neutral_history                   TEXT,   -- 중립 리스크 의견 요약
    trader_investment_judge_decision  TEXT,   -- 트레이더 판정 요약
    trader_investment_decision        TEXT,   -- 트레이더 결정 요약
    investment_plan                   TEXT,   -- 투자 계획 요약
    final_trade_decision              TEXT,   -- 최종 거래 결정 요약
    pa_opinion                        TEXT,   -- PA 의견
    created_at                        TEXT    NOT NULL
);
CREATE INDEX idx_reports_schedule ON reports(schedule_id);
CREATE INDEX idx_reports_position ON reports(position_id);

-- ④ 매매: 개별 BUY/SELL 액션
CREATE TABLE trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL REFERENCES positions(id),
    report_id   INTEGER NOT NULL REFERENCES reports(id),  -- 어떤 분석이 이 매매를 만들었는지
    action      TEXT    NOT NULL,    -- 'BUY' | 'SELL'
    shares      INTEGER NOT NULL,
    price       REAL    NOT NULL,
    executed_at TEXT    NOT NULL
);
CREATE INDEX idx_trades_position ON trades(position_id);
CREATE INDEX idx_trades_report ON trades(report_id);

-- ⑤ 반성: 청산 시 반성에이전트가 작성
CREATE TABLE reflections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER NOT NULL REFERENCES positions(id),
    reflection  TEXT    NOT NULL,    -- 반성문 전체
    key_lessons TEXT,                -- 핵심 교훈 요약 (RAG query용)
    outcome     TEXT,                -- 'win' | 'loss'
    return_pct  REAL,
    created_at  TEXT    NOT NULL
);
CREATE INDEX idx_reflections_position ON reflections(position_id);

-- ⑥ FTS5: BM25 검색용 가상 테이블
CREATE VIRTUAL TABLE reflections_fts USING fts5(
    reflection,
    key_lessons,
    content='reflections',
    content_rowid='id'
);

-- FTS 자동 동기화 트리거
CREATE TRIGGER reflections_ai AFTER INSERT ON reflections BEGIN
    INSERT INTO reflections_fts(rowid, reflection, key_lessons)
    VALUES (new.id, new.reflection, new.key_lessons);
END;
```

### 테이블 관계

```
schedules 1──1 reports
                  │
                  ├── position_id → positions 1──N trades
                  │                               │
                  └── report_id ←──────────── trades
                                  positions 1──0..1 reflections
```

### 요약 (역할별 정리)

| 테이블 | 한 줄 요약 | 누가 쓰는가 |
|--------|----------|------------|
| schedules | 언제 뭘 분석했는지 | 스케줄러 |
| positions | 뭘 들고 있는지 | PA |
| reports | 왜 그런 판단을 했는지 | 요약에이전트 |
| trades | 실제로 뭘 사고팔았는지 | PA |
| reflections | 끝나고 뭘 배웠는지 | 반성에이전트 |

---

## RAG 아키텍처 (Hybrid: ChromaDB + SQLite FTS5)

### 왜 Hybrid인가

| 검색 방식 | 잘 찾는 것 | 못 찾는 것 |
|----------|-----------|-----------|
| BM25 (FTS5) | "NVDA RSI 과매수" → 과거 "NVDA RSI 70 초과" | "업종 자체가 하락 추세" → 의미적 유사 |
| Vector (ChromaDB) | "좋아 보이는데 망한 케이스" → 의미적 유사 | 정확한 종목명/지표명 매칭 |
| **Hybrid** | **둘 다** | - |

### 검색 흐름

```
PA가 "반도체 대형주 모멘텀 진입 경험" 검색
                │
        ┌───────┴───────┐
        ▼               ▼
    ChromaDB         SQLite FTS5
   (벡터 검색)       (BM25 검색)
   의미 유사도        키워드 매칭
        │               │
        └───────┬───────┘
                ▼
          RRF 결합 → 최종 Top-K
```

```
검색 스코어 = Σ 1/(60 + rank_i(d))  (RRF — Reciprocal Rank Fusion)
```

### 이중 저장 (반성 데이터)

반성에이전트 실행 시 동일한 텍스트를 두 곳에 저장:

| 저장소 | 용도 | 쿼리 방식 |
|--------|------|----------|
| SQLite `reflections` | UI 조회 ("AAPL 아카이브 반성문 보여줘") | `WHERE position_id = 7` |
| SQLite FTS5 `reflections_fts` | BM25 키워드 검색 | `WHERE reflections_fts MATCH '반도체 모멘텀'` |
| ChromaDB | 벡터 의미 검색 ("비슷한 경험 찾기") | `collection.query(query_texts=[...])` |

### READ/WRITE 정리

```
READ:  PA만 읽음 (Hybrid RAG 검색)
       → "이전에 비슷한 상황에서 어떤 판단했지?"
       → 검색 결과를 PA 프롬프트에 주입

WRITE: 반성에이전트만 씀 (청산 시에만)
       → 반성문 → SQLite reflections + FTS5 + ChromaDB
```

> 기존 v1에서는 5개 에이전트가 각각 READ/WRITE → v3에서는 PA만 READ, 반성에이전트만 WRITE.
> LLM 호출 5회 → 1회, 데이터 오염 위험 감소, 비용 절감.

### Embedding

- **ChromaDB 내장 ONNX 임베딩** (`all-MiniLM-L6-v2`) 사용. API 호출 비용 없음, 별도 설치 불필요.
- persist: ChromaDB `PersistentClient`로 자동 영속화 (로컬 파일)

### 부트스트랩

```
1. SQLite DB 생성 + ChromaDB 빈 컬렉션            ← 선행 조건
2. 스케줄 실행 → 분석 → PA 판단 → 요약 저장        ← 데이터 축적 시작
3. 청산 발생 → 반성문 → SQLite + ChromaDB WRITE    ← RAG 데이터 생성
4. 이후 분석부터: PA가 RAG READ로 과거 학습 시작     ← 여기서부터 진짜 가치
```

초기에는 RAG가 비어있어 Memory 기반 통찰이 없다. **그게 정상**이다.
반성 데이터가 쌓이면서 점점 학습의 질이 향상된다.

---

## 요약에이전트 상세

### 역할

12에이전트 raw 산출물 + PA 의견 → 에이전트별 개별 요약 생성 → `reports` 테이블 13개 컬럼에 저장.

### 요약 대상 (13개 컬럼)

| 컬럼 | 원본 소스 | 비고 |
|------|----------|------|
| market_report | 시장 분석 raw | 기술적 지표, 트렌드 요약 |
| fundamentals_report | 펀더멘탈 raw | 재무 데이터 요약 |
| bull_history | 강세 토론 raw | 핵심 강세 논거 |
| bear_history | 약세 토론 raw | 핵심 약세 논거 |
| investment_debate_judge_decision | 투자 토론 판정 raw | 판정 결론 |
| aggressive_history | 공격적 리스크 raw | 공격적 관점 요약 |
| conservative_history | 보수적 리스크 raw | 보수적 관점 요약 |
| neutral_history | 중립 리스크 raw | 중립 관점 요약 |
| trader_investment_judge_decision | 트레이더 판정 raw | 판정 결론 |
| trader_investment_decision | 트레이더 결정 raw | 결정 내용 |
| investment_plan | 투자 계획 raw | 전략 요약 |
| final_trade_decision | 최종 결정 raw | 최종 결론 |
| pa_opinion | PA 원본 | PA가 직접 작성 (이미 간결) |

### 제외 항목

| 제외 | 이유 |
|------|------|
| sentiment_report | 소셜 미디어 센티먼트는 그날 한정, 시간 경과 후 무의미 |
| news_report | 뉴스도 그날 한정, 핵심은 이미 bull/bear 논거에 반영됨 |

### 각 컬럼 목표 크기

- 에이전트별 요약: **200~400 토큰**
- 13개 합계: **~3,000 토큰/사이클**
- 20 사이클 기준: ~60,000 토큰 (반성에이전트 컨텍스트에 충분히 수용 가능)

---

## 반성에이전트 상세

### 실행 조건

`position.shares == 0` (PA 실행 후 잔고가 0이 된 경우)

### 입력

1. **reports**: `SELECT * FROM reports WHERE position_id = ? ORDER BY created_at` (전 사이클 분석 요약)
2. **trades**: `SELECT * FROM trades WHERE position_id = ? ORDER BY executed_at` (전체 매매 이력)
3. **positions**: 포지션 메타 (수익률, 보유 기간 등)

### 출력

| 출력 | 저장소 | 용도 |
|------|--------|------|
| 반성문 전체 | SQLite `reflections.reflection` | UI 조회 |
| 핵심 교훈 | SQLite `reflections.key_lessons` + FTS5 | UI + BM25 검색 |
| 반성문 임베딩 | ChromaDB | 벡터 유사도 검색 |
| 승패 판정 | SQLite `reflections.outcome` | 통계, 필터링 |

### 실행 후 처리

```sql
-- 포지션 상태 변경 (아카이브 = 파일 이동 X, SQL UPDATE 1줄)
UPDATE positions SET status = 'closed', return_pct = ?, closed_at = ? WHERE id = ?;
```

---

## 시스템 구조

### 1 스케줄 = 1 티커

```
스케줄 #1: NVDA → 4일마다 분석
스케줄 #2: AAPL → 4일마다 분석
스케줄 #3: TSLA → 7일마다 분석 (종목별 주기 개별 설정 가능)
```

### 분석 주기

- **기본: 4일 간격** — yfinance 뉴스가 최근 7일 내 기사 제공, 4일이면 새 뉴스 충분 + 연속성 유지
- 종목별 주기 개별 설정 가능
- 향후: ATR(변동성) 기반 주기 자동 조절

---

## 크로스 티커 학습

모든 티커의 반성 데이터가 **하나의 RAG**에 모인다.
→ NVDA 분석 시 과거 AAPL/TSLA 실패 사례도 참조 가능.
→ 데이터가 쌓일수록 종목 간 패턴 인식이 날카로워짐.

---

## 설계 결정 (확정)

1. **저장소**: SQLite (trading.db) + ChromaDB. 파일 기반 스토리지 전면 폐기.
2. **회고 집중**: PA 1곳에서만 반성. 5개 에이전트 개별 반성 폐기. LLM 호출 5→1.
3. **BM25**: SQLite FTS5 내장 사용. `rank_bm25` 라이브러리 제거, JSONL 파싱 제거.
4. **아카이브**: 파일 이동 없음. `positions.status = 'closed'`로 처리.
5. **리포트**: 13개 개별 컬럼으로 에이전트별 요약 저장. 단일 summary 내지 raw 덤프 폐기.
6. **초기 자금**: 사용자 설정, 기본값 $1,000. 스케줄 등록 시 지정.
7. **멀티 티커 자금 공유: 없음**. 종목별 독립 자금.
8. **Embedding**: ChromaDB 내장 ONNX 임베딩 (`all-MiniLM-L6-v2`). API 호출 비용 없음.
9. **분석플로우 객관성**: 12에이전트 파이프라인은 포지션 정보 없이 완전 객관적 분석. 포지션 기반 판단은 PA에게만 위임.
10. **부트스트랩 기간**: 초기 반성 데이터 없이 운영. 데이터 축적 후 자연스럽게 학습 시작.
