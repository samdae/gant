# 회고분석(Retrospective Analysis) 설계 제안서 v4

> 기반: proposal_v3.md (Paper Trading 설계 확정), 현재 운영 중인 PostgreSQL 17 + ChromaDB 시스템
> 일자: 2026-02-24
> 상태: 설계 확정 구현 완료

---

## 1. 개요

### 1.1 기능 정의

회고분석은 **과거 의사결정의 의도가 구조적으로 타당했는가**를 평가하는 기능이다.
기존 Reflection(반성)과는 목적이 다르다.

| 구분 | Reflection (반성) | Retrospective Analysis (회고분석) |
|------|------------------|----------------------------------|
| 시점 | 포지션 청산 직후 자동 실행 | 사용자 요청 시 수동 실행 |
| 관점 | **결과 중심** (얼마 벌었/잃었나) | **과정 중심** (왜 그렇게 판단했나) |
| 평가 대상 | 최종 수익률, 핵심 교훈 | 매 분석 사이클의 판단 근거와 정합성 |
| 입력 | trades + positions | 전 사이클 reports + trades + positions |
| 출력 | 반성문 + key_lessons → RAG 저장 | 구조적 타당성 평가 → DB 저장 |
| 대상 | closed 포지션만 | open + closed 포지션 |

### 1.2 핵심 질문

회고분석 LLM이 답해야 하는 질문:

1. 각 분석 사이클에서 12에이전트의 판단 근거는 일관되었는가?
2. PA의 행동(BUY/SELL/HOLD)은 파이프라인 결론과 정합했는가?
3. 전략 변경(예: 손절선 조정)의 근거가 합리적이었는가?
4. RAG 경험이 주입된 경우, 그것이 판단에 적절히 반영되었는가?
5. (closed인 경우) 전체 포지션 라이프사이클을 통해 의사결정 패턴에 어떤 편향이 있었는가?

---

## 2. 설계 결정 사항

| # | 항목 | 결정 | 근거 |
|---|------|------|------|
| 1 | 분석 모델 | 기존 모델 유지, 프롬프트 강화 | 모델 교체보다 프롬프트 설계가 분석 품질에 더 직접적 |
| 2 | DB 저장 | 회고분석은 RAG에 저장하지 않음. 용도는 RAG 검증 및 사용자 시각화로 한정 | RAG 소스 단일화(반성만), 역할 명확화 |
| 3 | open/closed | 둘 다 분석, `position_status` 컬럼으로 구분 | open은 사람이 중간 점검, closed는 최종 판정 |
| 4 | 덮어쓰기 | 1 포지션 = 1 행, 재분석 시 덮어쓰기 | closed는 재분석 불필요·최종 판정만 보존하면 됨 |
| 5 | 자동청산 컨텍스트 | 프롬프트에 ±30% 규칙 + 현재 손익 주입 | 스키마 변경 없이 프롬프트로 해결 |
| 6 | 트리거 | 사용자 수동 요청 (UI) | 티커 / 날짜 / 전체 모드 선택 |
| 7 | 큐 | 기존 큐에 합류, PriorityQueue 교체 | 스케줄 분석 우선(0), 회고분석 후순위(1) |
| 8 | rag_docs | 구조화된 memories + raw_context | 문자열 파싱 불필요, 구조체를 직접 캡처 |
| 9 | 분석 상태 | `status` 컬럼 (pending/running/completed/failed) | 분석 진행 상태를 DB에 명시적 반영 |

---

## 3. 스키마 변경

### 3.1 reports 테이블 확장

기존 `reports` 테이블에 2개 컬럼 추가:

```sql
ALTER TABLE reports ADD COLUMN rag_used BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE reports ADD COLUMN rag_docs  JSONB;
```

`rag_docs` JSONB 구조:

```json
{
  "memories": [
    {
      "outcome_label": "Win — AAPL 3주 보유 +12%",
      "matched_situation": "반도체 업종 강세 국면에서 모멘텀 진입...",
      "return_pct": 12.3
    }
  ],
  "raw_context": "\n**Past Experiences (from RAG):**\n1. Win — AAPL ..."
}
```

| 필드 | 설명 |
|------|------|
| `memories` | ChromaDB `get_memories()` 반환 구조체를 그대로 캡처한 배열 |
| `raw_context` | PA 프롬프트에 실제 주입된 문자열 원문 |

> 저장 시점: `portfolio_agent.py`에서 `rag_context` 문자열 빌드 직후, 동일 스코프의 `memories` 리스트를 함께 캡처. 문자열 → 구조체 파싱은 불필요하다.

### 3.2 retrospective_analyses 신규 테이블

```sql
CREATE TABLE IF NOT EXISTS retrospective_analyses (
    id                  BIGSERIAL PRIMARY KEY,
    position_id         BIGINT    NOT NULL UNIQUE REFERENCES positions(id),
    ticker              TEXT      NOT NULL,
    position_sequence   INTEGER   NOT NULL,
    position_status     TEXT      NOT NULL,
    status              TEXT      NOT NULL DEFAULT 'pending',
    analysis_content    TEXT,
    analysis_count      INTEGER   NOT NULL DEFAULT 1,
    position_open_date  TIMESTAMPTZ,
    position_close_date TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(ticker, position_sequence)
);
CREATE INDEX IF NOT EXISTS idx_retro_ticker ON retrospective_analyses(ticker);
CREATE INDEX IF NOT EXISTS idx_retro_status ON retrospective_analyses(status);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `position_id` | BIGINT FK, UNIQUE | positions 테이블 참조. 1 포지션 = 1 행 보장 |
| `ticker` | TEXT | 종목 코드 |
| `position_sequence` | INTEGER | 해당 티커의 N번째 포지션 (1-based, `ROW_NUMBER()` 도출) |
| `position_status` | TEXT | `'open'` \| `'closed'` — 분석 요청 시 `positions.status`에서 읽어서 세팅 |
| `status` | TEXT | `'pending'` \| `'running'` \| `'completed'` \| `'failed'` — 분석 작업 상태 |
| `analysis_content` | TEXT | LLM 회고분석 결과 본문 |
| `analysis_count` | INTEGER | 이 포지션에 대해 총 몇 회 분석했는지 (메타) |
| `error_message` | TEXT | `status='failed'` 시 에러 내용 |

> RAG 사용 여부 및 RAG 데이터는 `reports.rag_used` / `reports.rag_docs`에 이미 리포트별로 기록되므로 여기서 중복 저장하지 않는다. 회고분석 LLM이 리포트를 읽을 때 함께 참조한다.

### 3.3 position_sequence 도출

`positions` 테이블에서 자동 계산:

```sql
SELECT id, ticker, status, opened_at, closed_at, return_pct,
       ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY opened_at) AS position_sequence
FROM positions
WHERE ticker = :ticker
ORDER BY opened_at;
```

`retrospective_analyses` INSERT 시 이 값을 계산하여 저장한다 (비정규화, 조회 편의).

### 3.4 행 라이프사이클

```
                                 ┌──────────────────────────┐
                                 │    retrospective_analyses │
                                 └──────────────────────────┘

최초 분석 요청 ─→ INSERT
                   status = 'pending'
                   position_status = positions.status 에서 읽어서 세팅
                   analysis_count = 1
                        │
큐 처리 시작 ───→ UPDATE status = 'running'
                        │
                   ┌────┴────┐
                   │         │
              성공 ▼    실패 ▼
     status = 'completed'   status = 'failed'
     analysis_content = 결과 error_message = 에러
                   │         │
                   ▼         ▼
           ┌───── (closed면 불변) ─────┐
           │                           │
    재분석 요청 (open/failed):          
      UPDATE 덮어쓰기                   
        status = 'pending'              
        position_status = positions.status 재확인
        analysis_count += 1             
           │                           
    ※ positions.status가 'closed'로 바뀌어 있으면
      position_status도 'closed'로 갱신됨 (자동)
           │
           │                           │
           └───→ 큐 재진입

completed + position_status = 'closed' ─→ 불변 (더 이상 분석 불가)
```

---

## 4. 큐 아키텍처 변경

### 4.1 PriorityQueue 전환

| 항목 | 현재 | 변경 |
|------|------|------|
| 타입 | `asyncio.Queue` | `asyncio.PriorityQueue` |
| 아이템 | `Dict` (ticker, schedule_job_id) | `Tuple[int, int, Dict]` (priority, seq, payload) |

| 우선순위 | 작업 유형 |
|----------|----------|
| 0 (높음) | 스케줄 분석 (기존 정기 분석) |
| 1 (낮음) | 회고분석 (사용자 요청) |

### 4.2 영향 범위

| 파일 | 변경 내용 |
|------|----------|
| `scheduler/ticker_scheduler.py` | `Queue` → `PriorityQueue`, `_enqueue_item`에 priority 파라미터 추가 |
| `scheduler/ticker_scheduler.py` | `_is_ticker_queued`, `_queue_snapshot`에서 tuple 언팩 |
| `api/app.py` | `asyncio.Queue()` → `asyncio.PriorityQueue()` |
| `api/app.py` `_queue_worker` | dequeue 시 `priority, seq, item = await queue.get()` |
| `api/app.py` `_queue_snapshot` | tuple 언팩 후 ticker 추출 |

### 4.3 enqueue 패턴

```python
_enqueue_seq: int = 0

def _enqueue_item(self, item: Dict[str, Any], priority: int = 0) -> None:
    global _enqueue_seq
    _enqueue_seq += 1
    # PriorityQueue: (priority, sequence, payload) — sequence는 동일 priority 내 FIFO 보장
    asyncio.run_coroutine_threadsafe(
        self._analysis_queue.put((priority, _enqueue_seq, item)),
        self._queue_loop,
    )
```

### 4.4 동작 시나리오

| 시나리오 | 동작 |
|----------|------|
| 큐 비어있음 + 회고분석 요청 | 즉시 처리 |
| 스케줄 분석 큐잉 중 + 회고분석 요청 | 스케줄 먼저, 회고는 뒤로 밀림 |
| 회고분석 3건 큐잉 중 + 스케줄 분석 도착 | 스케줄이 3건 앞으로 점프 |
| 회고분석 running 중 + 스케줄 분석 도착 | 현재 작업 완료 대기 후 스케줄 처리 (최대 1건분 지연) |

---

## 5. UI 설계

### 5.1 네비게이션

기존 메뉴에 "회고분석" 탭 추가. Svelte SPA 라우트: `#/retrospective`

### 5.2 화면 구조

```
┌──────────────────────────────────────────────────┐
│  회고분석                                         │
├──────────────────────────────────────────────────┤
│                                                    │
│  필터: [티커] [날짜] [전체]                        │
│                                                    │
│  티커 선택:                                        │
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────┐         │
│  │#NVDA │ │#AAPL │ │#005930:  │ │#TSLA │         │
│  │      │ │      │ │삼성전자  │ │(disabled)│      │
│  └──────┘ └──────┘ └──────────┘ └──────┘         │
│                                                    │
│  ── 선택된 티커: NVDA ──                           │
│                                                    │
│  회차 │ 기간                     │ 결과 │ 상태                │
│  ─────┼──────────────────────────┼──────┼────────────────────│
│  1회차│ 2026-01-15 ~ 2026-02-03 │  승  │ closed 회고분석완료 │
│  2회차│ 2026-02-10 ~ (진행중)   │   -  │ open 회고분석완료   │
│  3회차│ 2026-02-20 ~ (진행중)   │   -  │ 분석미완료          │
│                                                    │
│         [선택된 포지션 회고분석 실행]               │
│                                                    │
└──────────────────────────────────────────────────┘
```

### 5.3 티커 선택

- `schedule_configs` 테이블에서 등록된 티커 조회
- `[ticker]:[display_name]` 형식의 해시태그 UI
- BUY 트레이드가 한 번도 없는 티커 → **disabled** (선택 불가)
- 복수 선택 가능

### 5.4 필터 모드

| 모드 | UI 흐름 |
|------|---------|
| 티커 | 해시태그로 티커 선택 → 선택된 티커의 포지션 리스트 표시 → 체크박스로 개별 포지션 선택 → 분석 실행 |
| 날짜 | date picker로 기간 선택 → 해당 기간 내 `opened_at`이 있는 분석 가능 티커 목록을 노티 형태로 표시 ("NVDA 2건, AAPL 1건 분석합니다") → 확인 시 일괄 분석 |
| 전체 | 분석 가능한 전체 티커 목록을 노티 형태로 표시 ("NVDA 2건, AAPL 1건, 005930 3건 분석합니다") → 확인 시 일괄 분석 |

공통 규칙: **`completed` + `position_status='closed'`** 상태는 분석 대상에서 제외.

### 5.5 포지션 리스트 데이터 소스

| 필드 | 소스 |
|------|------|
| 회차 (position_sequence) | `positions` 테이블에서 `ROW_NUMBER()` 도출 |
| 기간 (start ~ end) | `positions.opened_at` ~ `positions.closed_at` (open이면 "진행중") |
| 결과 (승/패) | `positions.return_pct` 기준 (> 0: 승, ≤ 0: 패, open: `-`) |
| 분석상태 | `retrospective_analyses` LEFT JOIN (아래 매핑 참조) |

> 손익(PnL)은 표시하지 않는다. 분석 대상 선정에 필요한 정보가 아니며, 실제 분석 시 yfinance에서 현재가를 조회한다.

### 5.6 분석상태 매핑

| DB 조건 | UI 표시 | 재분석 가능 |
|---------|---------|------------|
| LEFT JOIN 결과 없음 | 분석미완료 | ✅ |
| `status` IN ('pending', 'running') | 분석중 | ❌ |
| `status='completed'` + `position_status='open'` | open 회고분석완료 | ✅ |
| `status='completed'` + `position_status='closed'` | closed 회고분석완료 | ❌ (불변) |
| `status='failed'` | 분석실패 | ✅ |

분석 대상 = **분석미완료 + open 회고분석완료 + 분석실패**
분석 제외 = **closed 회고분석완료 + 분석중**

---

## 6. 분석 워크플로우

### 6.1 전체 흐름

```
┌─ 사용자 요청 ─────────────────────────────────────────────────────────┐
│                                                                        │
│  1. UI: 티커/날짜/전체 선택 → 포지션 체크박스 선택                    │
│  2. API: POST /api/retrospective/analyze                               │
│  3. 선택된 포지션별 retrospective_analyses UPSERT                      │
│     → status='pending' (신규 INSERT 또는 기존 행 UPDATE)              │
│  4. PriorityQueue에 priority=1로 포지션별 순차 enqueue                │
│                                                                        │
│  ── 큐 worker (기존 _queue_worker 확장) ──                             │
│                                                                        │
│  5. dequeue → item['type'] == 'retrospective' 분기                    │
│  6. UPDATE status='running'                                            │
│  7. 데이터 수집:                                                       │
│     ┌──────────────────────────────────────────────────────┐           │
│     │ positions : 포지션 메타 (avg_cost, shares, stop_loss)│           │
│     │ reports   : 포지션 기간 전체 리포트 (시간순)         │           │
│     │ trades    : 포지션 전체 매매 이력                     │           │
│     │ (open) 현재 시세 + 미실현 손익 (yfinance)            │           │
│     └──────────────────────────────────────────────────────┘           │
│  8. LLM 프롬프트 구성 (open/closed 분기)                              │
│  9. LLM 호출 → 분석 결과 수신                                        │
│ 10. UPDATE: status='completed', analysis_content=결과,                 │
│             updated_at=now()                                           │
│     (실패 시: status='failed', error_message=에러)                     │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.2 큐 worker 분기

기존 `_queue_worker`에 item type 분기 추가:

```python
priority, seq, item = await analysis_queue.get()

if item.get("type") == "retrospective":
    await _run_retrospective(item)
else:
    # 기존 스케줄 분석 로직
    await asyncio.to_thread(scheduler._run_analysis_cycle, ticker, job_id)
```

### 6.3 데이터 수집 쿼리

```sql
-- 포지션 정보
SELECT * FROM positions WHERE id = :position_id;

-- 포지션 기간 전체 리포트 (시간순)
SELECT r.*, r.rag_used, r.rag_docs
FROM reports r
WHERE r.position_id = :position_id
ORDER BY r.created_at;

-- 포지션 전체 매매 이력
SELECT * FROM trades
WHERE position_id = :position_id
ORDER BY executed_at;
```

### 6.4 프롬프트 분기

**공통 주입:**
- 자동청산 규칙: "이 시스템은 stop_loss 또는 target 도달 시 자동 청산하며, ±30% 도달 시에도 자동 청산된다."
- 전체 리포트 시계열 (사이클별 에이전트 판단 요약)
- 전체 매매 이력

**Open 포지션 전용:**
- 현재 시세 + 미실현 손익률
- 톤: "진행 중인 포지션에 대한 중간 점검. 지금까지의 의사결정 과정이 구조적으로 타당한지 평가하라."

**Closed 포지션 전용:**
- 최종 실현 손익률
- 톤: "완결된 포지션의 전체 라이프사이클을 검토하라. 의사결정 패턴에 편향이 있었는지 분석하라."
- 패턴 편향 분석 항목: 확증 편향, 손실 회피, 앵커링, 매몰비용 오류 등

---

## 7. API 엔드포인트

| Method | Path | 설명 | 응답 |
|--------|------|------|------|
| GET | `/api/retrospective/tickers` | 분석 가능 티커 목록 | ticker, display_name, has_trades, position_count |
| GET | `/api/retrospective/positions/{ticker}` | 티커별 포지션 목록 + 분석상태 | position_sequence, dates, result, pnl, analysis_status |
| POST | `/api/retrospective/analyze` | 분석 요청 | enqueued position_ids |
| GET | `/api/retrospective/{id}` | 개별 분석 결과 조회 | analysis_content, metadata |

### 7.1 POST /api/retrospective/analyze 요청 body

```json
{
  "mode": "ticker" | "date" | "all",
  "position_ids": [12, 15, 23],
  "tickers": ["NVDA", "AAPL"],
  "date_from": "2026-01-01",
  "date_to": "2026-02-24"
}
```

| 모드 | 필수 필드 | 동작 |
|------|----------|------|
| `ticker` | `position_ids` | 사용자가 선택한 포지션만 분석 |
| `date` | `date_from`, `date_to` | 기간 내 분석 가능한 모든 포지션 자동 선택 |
| `all` | (없음) | 전체 분석 가능 포지션 자동 선택 |

서버 처리:
1. mode에 따라 대상 포지션 결정 (`ticker` 모드는 `position_ids` 사용, `date`/`all` 모드는 서버가 필터링)
2. 분석 제외 대상 (closed 완료, 분석중) 제거
3. 대상 포지션별 `retrospective_analyses` UPSERT (status='pending', position_status는 `positions.status`에서 읽어서 세팅)
4. PriorityQueue enqueue (priority=1)
5. enqueue된 position_id 목록 응답

---

## 8. 데이터 관계

```
schedule_configs ←── (ticker 기준 UI 조회)

positions ──┬── 1:N  trades
            ├── 1:N  reports (via position_id)
            ├── 0..1 reflections (기존 반성 — 청산 시 자동)
            └── 0..1 retrospective_analyses (회고분석 — 사용자 요청)
                      ↑
                      UNIQUE(ticker, position_sequence)
```

---

## 9. 기존 코드 변경 요약

| 영역 | 파일 | 변경 |
|------|------|------|
| 스키마 | `storage/database.py` | `reports` 테이블 ALTER (rag_used, rag_docs), `retrospective_analyses` CREATE |
| 큐 | `scheduler/ticker_scheduler.py` | `Queue` → `PriorityQueue`, tuple wrapping |
| 큐 | `api/app.py` | `Queue()` → `PriorityQueue()`, worker 분기 |
| RAG 캡처 | `virtual_trade/portfolio_agent.py` | `memories` 구조체를 rag_docs로 함께 반환 |
| 리포지토리 | `storage/` (신규) | `RetrospectiveRepository` CRUD |
| 서비스 | (신규) | 회고분석 실행 로직 (데이터 수집 → 프롬프트 빌드 → LLM 호출 → 저장) |
| API | `api/routes.py` | 4개 엔드포인트 추가 |
| 프론트엔드 | `apps/web/src/routes/` (신규) | Retrospective.svelte 페이지 |
| 프론트엔드 | `apps/web/src/App.svelte` | 라우트 + 네비게이션 추가 |

---

## 10. 향후 고려사항

1. **회고분석·RAG**: 회고분석은 ChromaDB에 저장하지 않음. 용도는 RAG 효과 검증(v5 입력) 및 사용자 시각화로 한정.
2. **토큰 제한**: 장기 포지션(20+ 사이클)의 리포트를 LLM에 전부 주입 시 컨텍스트 윈도우 초과 가능 — 요약 압축 또는 최근 N개 사이클만 포함하는 전략 필요
3. **LLM 응답 구조화**: 분석 결과를 structured output (JSON schema)으로 받아 UI에서 섹션별 렌더링할지 — 현재는 TEXT로 시작, 필요 시 구조화
4. **프론트엔드 실시간 상태**: 분석중(pending/running) 상태를 WebSocket으로 실시간 반영할지, 폴링으로 할지

---

## 11. 버그픽스 — 스케줄 회차(current_cycle) 비정상 증가

### 증상
서버를 재시작할 때마다 `schedule_configs.current_cycle`이 증가하여, 실제 분석 횟수와 무관하게 회차가 폭증함. (예: 신규 DB에서 39회 재시작 → 19회차 표시)

### 원인
1. **서버 기동 시 복구 로직**: `app.py` lifespan에서 모든 티커에 대해 `enqueue_schedule`을 호출했으며, `has_done_today_for_ticker`가 `status='done'`만 확인하고 `'skipped'`를 확인하지 않아 매 재시작마다 새 job + cycle 증가
2. **`increment_cycle` 호출 시점**: `enqueue_schedule`(큐 삽입 시점)에서 cycle을 증가시켜, 이후 skip되더라도 이미 cycle이 올라간 상태

### 수정 내용

| 파일 | 변경 |
|------|------|
| `api/app.py` | 서버 기동 시 스케줄 복구 enqueue 로직 **제거**. 스케줄은 CronTrigger 지정 시간에만 실행 |
| `scheduler/ticker_scheduler.py` | `enqueue_schedule`에서 job 생성 + `increment_cycle` 제거. 순수하게 큐에 넣기만 함 |
| `scheduler/ticker_scheduler.py` | `_run_analysis_cycle`에서 skip 체크를 **job 생성 전**으로 이동. 새 시장 데이터가 없으면 job/cycle 없이 즉시 return. 실제 분석 실행 시에만 `increment_cycle` + job 생성 |

### 결과
- `current_cycle` = 실제 분석이 실행된 횟수만 반영
- 서버 재시작, 주말/공휴일(시장 데이터 없음) 시 cycle 증가 없음

---

## 12. UI/UX 개선사항

### 12.1 AI분석 탭 통합

기존 하단 네비게이션의 "회고" 탭을 제거하고, "AI분석" 탭 안에서 상단 서브탭으로 통합.

| 서브탭 | 라우트 | 설명 |
|--------|--------|------|
| 레포트 | `/reports` | 일정에 등록된 종목의 장 마감 후 분석 결과 |
| 매매검증 | `/reflections` | 거래 종료 시 자동 생성되는 회고 기록 (RAG 반영) |
| 회고분석 | `/retrospective` | 사용자 요청 기반 사후 평가 |

- `AnalysisTabs.svelte` 공유 컴포넌트: 탭 바 + 설명 텍스트 + `action` 슬롯
- 회고분석 탭에서만 "요청" 버튼이 탭 바 우측에 표시됨

### 12.2 용어 정리

| 이전 | 변경 | 이유 |
|------|------|------|
| 회고 | 매매검증 | "회고"가 모호함 |
| 회귀분석 | 회고분석 | "회귀분석"은 통계 용어와 혼동 |
| 청산 | 거래 종료 | "청산"은 부정적 뉘앙스 |

### 12.3 회고분석 페이지 — 리스트-디테일 패턴

기존 단일 페이지 트리거/결과 뷰를 레포트 탭과 동일한 패턴으로 변경:

1. **요약 리스트** (`/retrospective`): 티커별 완료 건수 + 최신 날짜
2. **상세 페이지** (`/retrospective/:ticker`): 셀렉트박스로 회차 선택 → 분석 결과 마크다운 렌더링
3. **분석 요청 모달**: "요청" 버튼 클릭 → 모달에서 티커/포지션 선택

### 12.4 분석 요청 모달

| 항목 | 설명 |
|------|------|
| 탭 | "티커" 단일 탭 (라벨용) |
| 티커 선택 | display_name 칩으로 표시, 클릭 시 포지션 자동 체크 |
| 포지션 | 분석 가능 항목 자동 체크, 커스텀 체크박스 |
| 버튼 | "선택티커" (체크된 포지션만) + "전체티커" (모든 분석 가능 포지션) |
| 레이아웃 | 헤더/푸터 고정, 바디 스크롤 |

### 12.5 홈 화면

- 최근활동 섹션 제거 (레포트 탭에서 확인 가능)
- 총손익 실현/미실현, 투자 승/패를 줄바꿈 + 그리드 정렬

### 12.6 하단 네비게이션

- 스크롤 시 숨김/표시 동작 제거 → 항상 고정
- full-width 솔리드 배경 (`rgb(11, 13, 17)`)으로 변경
- 라운드 코너, 블러, 그림자 제거
- 하단 safe area와 경계 없이 동일 색상

### 12.7 투자 상세 — 결정 뱃지 색상 수정

`getReportDecision`에서 `final_trade_decision` (전체 분석 텍스트) fallback을 제거.
이전에는 텍스트에 "BUY" 단어가 포함되면 모든 뱃지가 빨간색(매수)으로 표시되는 버그 존재.

---

## 13. 서버 기동 시 회고분석 복구

### 배경
서버 재시작 시 `status='pending'` 또는 `status='running'` 상태의 회고분석이 큐에서 유실됨.

### 구현

| 파일 | 변경 |
|------|------|
| `storage/retrospective_repo.py` | `get_incomplete()` 메서드 추가 — `status IN ('pending', 'running')` 조회 |
| `api/app.py` lifespan | startup 시 `get_incomplete()` 호출 → `PRIORITY_RETROSPECTIVE`로 큐 재삽입 |

### 동작
- 스케줄 분석 복구와 달리 cycle 증가나 job 생성 없음
- 기존 `retrospective_analyses` 행을 그대로 재처리
- 실패 시 `status='failed'`로 업데이트되어 사용자가 재요청 가능
