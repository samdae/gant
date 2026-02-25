# Proposal v5: RAG 검색 파이프라인 개편 + 효과 검증 에이전트

> **상태**: 미구현 — 회고분석 데이터가 충분히 축적된 후 착수  
> **선행 조건**: proposal_v4 (회고분석) 운영 및 데이터 축적

---

## 1. 목적

회고분석(v4)은 PA의 판단 품질을 **정성적**으로 평가한다.  
본 제안은 두 가지를 정의한다:

1. **RAG 검색 파이프라인 개편** — 맥락 인식(market/sector) 쿼리 enrichment, RRF → usefulness 순서 재설계, 주입 경험 수 제어
2. **RAG 효과 검증 에이전트** — 회고분석 결과를 집계하여 RAG가 PA 판단 품질에 실제로 기여하는가를 검증하고, usefulness_score로 피드백

### 대조군 확보 전략

RAG 미사용 사이클은 각 티커의 초기 구간(경험 없음 → RAG 불가)에서만 자연 발생한다.  
경험이 축적되면 거의 모든 사이클이 RAG 주입 상태가 되어 비사용 표본이 사라지므로, **초기에 티커를 충분히 확보**하여 미사용 표본을 최대화해야 한다.

시스템 자체(파이프라인, 프롬프트, 6:4 비중)는 불변이므로, 초기(RAG 없음) vs 후기(RAG 있음) 비교는 곧 **RAG 효과 비교 그 자체**이다.

---

## 2. RAG 검색 파이프라인 개편

### 2-1. 맥락 인식 쿼리 enrichment

#### 배경

현재 RAG는 크로스 티커 검색이다 — 모든 티커의 반성이 하나의 저장소에 통합되어 종목 간 패턴 인식이 가능하다. 그러나 **섹터/시장이 다른 경험은 오히려 노이즈**가 된다.

- 테크 기업은 펀더멘탈이 나빠도 주가가 오르는 경우가 흔함. 정유/금융과 투자 패턴이 근본적으로 다름.
- 한국 시장과 미국 시장은 규제, 투자자 행동, 매크로 환경이 다름.
- 같은 교훈이라도 맥락이 다르면 유효하지 않다.

#### 설계

분석 파이프라인 완료 후 PA 판단 직전에 RAG 검색이 실행된다. 이 시점에 `schedule_configs.market`과 yfinance `Ticker.info.sector`는 이미 확보된 상태이므로, **검색 쿼리에 market/sector를 텍스트로 부착**한다.

```python
def _build_rag_query(self, pipeline_state, ticker, market=None, sector=None):
    market_excerpt = pipeline_state.get("market_report", "")[:300]
    final_decision = pipeline_state.get("final_trade_decision", "")[:300]
    context_parts = [f"{ticker} analysis: {market_excerpt} Decision: {final_decision}"]
    if market:
        context_parts.append(f"Market: {market}")
    if sector:
        context_parts.append(f"Sector: {sector}")
    return " ".join(context_parts)
```

#### 설계 근거

| 방식 | 장점 | 단점 |
|------|------|------|
| **DB 하드 필터** (WHERE market = :market) | 정확한 분리 | 초기 데이터 부족 시 빈 결과, fallback 필요, 양쪽 인프라 수정 |
| **쿼리 enrichment** (텍스트 부착) | 인프라 변경 없음, graceful degradation | FTS 매칭이 불완전할 수 있음 |

쿼리 enrichment를 선택한다:
- **ChromaDB (시멘틱)**: 임베딩 모델(all-MiniLM-L6-v2)이 market/sector 컨텍스트를 벡터에 반영 → 같은 맥락 문서와 유사도 자연 상승. **핵심 역할**.
- **Postgres FTS**: `plainto_tsquery('simple')` 기반이라 sector/market이 반성문 텍스트에 직접 등장하지 않으면 매칭 안 됨. 그러나 FTS는 보조 역할이고, ChromaDB가 맥락을 잡으므로 RRF 합산 시 충분.
- **industry는 배제**: sector 수준이면 충분. industry까지 넣으면 쿼리가 과도하게 좁아짐.
- **fallback 불필요**: 같은 market/sector 문서가 부족하면 자연스럽게 cross-sector 문서가 낮은 유사도로 올라옴. 별도 로직 불필요.

### 2-2. 검색 파이프라인 재설계

#### 현재 파이프라인

```
FTS top-10 + ChromaDB top-10 → 중복제거 → RRF → top-K → PA 주입
```

#### 변경 파이프라인

```
1. 쿼리 enrichment
   기존 검색 쿼리 + "Market: {market} Sector: {sector}" 부착
       ↓
2. 후보 생성
   키워드(FTS) top-3 + 시멘틱(ChromaDB) top-3
       ↓
3. 중복 제거 + RRF 융합 → top-3
   (지금 상황과 관련 있는가?)
       ↓
4. usefulness_score < 40 하드 배제
   → 나머지 중 usefulness_score DESC 정렬 → top-K
   (과거에 도움이 됐는가?)
       ↓
5. PA에 주입
```

#### 변경 근거: RRF → usefulness 순서

이전 설계(v5 초안)는 usefulness → RRF 순서였으나, **초기에 usefulness_score가 전부 50(기본값)이므로 변별력이 없다.** 변별력 없는 축으로 먼저 자르면 연관성 높은 문서가 무작위로 탈락할 수 있다.

- **RRF 먼저**: 변별력이 항상 있는 축(검색 유사도)으로 먼저 커팅
- **usefulness 나중**: 시간이 지나면서 점수가 분화되면 두 번째 커팅의 의미가 점점 커짐
- **40점 하드 플로어**: 기본값 50에서 10번 연속 "쓸모없다" 평가를 받아야 도달. 충분히 보수적이면서 진짜 쓰레기만 배제

### 2-3. PA 주입 경험 수 (top-K)

| 시기 | K값 | 이유 |
|------|-----|------|
| 초기 ~ 6개월 | **1** | usefulness_score 미분화. 1개로 깨끗한 귀인 데이터 확보 → v5 검증 품질 향상 |
| 6개월 이후 | 2~3 | usefulness 분화 완료. 상위 문서만 살아남은 상태에서 다각도 경험 제공 |

**경험 1개 주입의 이점** (초기):
- v5 usefulness 평가 시 "이 문서가 영향을 줬는가" 귀인이 명확
- 3개 주입 시 어느 문서가 영향을 줬는지 LLM 개별 평가 정확도 저하
- 파이프라인 구조는 불변, K값만 조정하면 단계적 확장 가능

**환경변수**: `RAG_TOP_K` (기본값: 1). `.env`에서 설정 가능. 파이프라인 재배포 없이 주입 경험 수를 조정.

```python
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "1"))
```

### 2-4. 스키마 변경

`reflections` 테이블에 컬럼 추가:

```sql
ALTER TABLE reflections ADD COLUMN usefulness_score DOUBLE PRECISION NOT NULL DEFAULT 50;
```

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `usefulness_score` | DOUBLE PRECISION | 50 | RAG 효과 검증 에이전트가 ±1 조정. 40 미만 시 검색 결과에서 하드 배제 |

---

## 3. RAG 효과 검증 에이전트

### 역할
- 회고분석 결과(`retrospective_analyses.analysis_content`)를 입력으로 받아, RAG 주입 사이클의 PA 판단 품질을 정성 평가
- 각 RAG 문서(`rag_docs.memories[*]`)에 대해 PA가 실제로 해당 경험을 반영했는지 **문서 단위 개별 평가**
- RAG 문서는 **반성(매매검증) 출신으로 한정**. 회고분석은 RAG에 저장하지 않으며 검증·시각화 용도로만 사용.

### 입력 데이터
- `retrospective_analyses.analysis_content` (회고분석 결과 텍스트)
- `reports.rag_used` (boolean)
- `reports.rag_docs` (JSONB — `memories[*].reflection_id`로 문서 단위 추적 가능)

### 출력물
1. **RAG 효과 분석 리포트** — 사람이 읽고 판단하기 위한 보고서
2. **문서별 usefulness_score 조정값** — 자동 반영 (아래 4절 참조)

---

## 4. 피드백 루프

### 4-1. RAG 문서 usefulness_score (자동화)

| 항목 | 설계 |
|------|------|
| 기본값 | 50 |
| 조정 단위 | ±1 / 평가 회차 |
| 조정 주체 | RAG 효과 검증 에이전트 (LLM) |
| 하드 플로어 | 40 미만 → 검색 결과에서 배제 |
| 효과 | 진짜 쓸모없는 문서만 서서히 하락 → 보수적 쓰레기 필터 |

**설계 의도**: 빠르게 효과를 내는 것이 목적이 아니다. 회고와 반성에는 시장 펀더멘탈, 강세/약세 논리가 포함되어 있어 맥락마다 유용성이 달라진다. 빠르게 적용되면 오히려 위험하며, **느리게 적용되더라도 쓰레기를 거르는 것**이 본래 의도이다.

**시간 편향 완화**: 기본값 50에서 ±1씩 이동하므로, 초기 문서가 후기 문서 대비 가중치가 폭주하지 않음.  
**노이즈 허용**: LLM 판정 정확도가 60-70%라면 대부분 문서가 48~52 사이에 머물러 사실상 무가중과 동일. 신호가 강한 문서만 45↓ / 55↑로 이탈하여 변별됨.

**구현 시점**: 회고분석 데이터 충분히 축적 후.  
**선행 완료**: `rag_docs.memories[*].reflection_id` 저장 — **완료 (v4에서 반영됨)**

### 4-2. RAG 검색 기존 파라미터 (건드리지 않음)

similarity threshold 등 기존 검색 파라미터는 **고정**.  
자동 튜닝 시 되돌리기 어렵고, 현재 잘 작동하는 것을 불확실한 근거로 변경할 이유 없음.

### 4-3. RAG 경험 비중 6:4 (건드리지 않음)

현재 파이프라인 분석(60%) : RAG 경험(40%) 비중은 **고정**.  
동적 변경 시 PA 행동의 재현성이 깨지며, 회고분석 시 "이 시점에 비중이 몇이었는지"까지 추적해야 하는 복잡도가 발생.

### 4-4. PA 프롬프트 수정 (사람이 판단)

RAG 효과 분석 리포트를 사람이 읽고 필요 시 수동으로 PA 프롬프트를 조정.  
AI가 AI의 프롬프트를 자동으로 고치는 것은 피드백 루프가 불안정해질 위험이 있으므로 자동화하지 않음.

---

## 5. 전체 흐름도

```
[분석 시점 — 매 사이클]

12에이전트 파이프라인 완료
    ↓
RAG 검색 (맥락 인식 쿼리)
    쿼리: ticker + market_report + final_decision + "Market: {market} Sector: {sector}"
    FTS top-3 + ChromaDB top-3 → 중복제거 + RRF → top-3
    → usefulness < 40 배제 → usefulness DESC → top-K (env: RAG_TOP_K)
    ↓
PA 판단 (파이프라인 60% + RAG 경험 40%)
    ↓
reports에 rag_used, rag_docs 저장


[검증 시점 — 회고분석 축적 후]

회고분석 결과 축적 (retrospective_analyses)
    ↓
RAG 효과 검증 에이전트 실행
    ↓
출력물:
  ├─ [자동] RAG 문서별 usefulness_score ±1 업데이트
  │         → 다음 RAG 검색 시 파이프라인 4단계에서 배제/정렬에 사용
  └─ [리포트] RAG 효과 분석 보고서 → 사람이 읽고 판단
       ├─ 검색 파라미터 조정 여부 (원칙: 고정)
       └─ PA 프롬프트 수정 여부 (사람이 결정)
```

---

## 6. 결정 사항 요약

| 항목 | 결정 | 근거 |
|------|------|------|
| 쿼리 enrichment (market/sector) | O (텍스트 부착) | ChromaDB 시멘틱이 맥락 인식. DB 하드 필터 대비 인프라 변경 없음, graceful degradation |
| industry 포함 | X | sector 수준이면 충분. industry는 쿼리를 과도하게 좁힘 |
| 파이프라인 순서 | RRF → usefulness | 초기 usefulness 미분화(전부 50) 상태에서 연관성 축으로 먼저 커팅이 안전 |
| usefulness 하드 플로어 | 40 미만 배제 | 기본값 50에서 10회 연속 "쓸모없다" 평가 시 도달. 보수적 |
| PA 주입 경험 수 (K) | 초기 1, 추후 2~3 | 1개일 때 v5 귀인 평가가 깨끗함. `RAG_TOP_K` 환경변수로 제어 |
| usefulness_score 자동화 | O (±1 방식) | 느린 쓰레기 필터, 시간 편향 최소화 |
| 검색 파라미터 자동 튜닝 | X | 현재 정상 작동, 리스크 > 이득 |
| 6:4 비중 동적 조정 | X | 재현성 파괴, 추적 복잡도 증가 |
| PA 프롬프트 자동 수정 | X | 피드백 루프 불안정 위험 |
| reflection_id 저장 | O (이미 반영) | 문서 단위 추적 기반 확보 |
| RAG 소스 범위 | 반성(매매검증)만 | 회고분석은 RAG에 저장하지 않음. 검증·시각화 용도로만 사용 |
| 초기 티커 다수 확보 | 권장 | RAG 미사용 대조군 표본 확보 |

---

## 7. 매매검증 검색 기능

> **상태**: 미구현

### 배경
매매검증(Reflections) 탭에 현재 검색 기능이 없어, 데이터가 쌓이면 특정 회고 기록을 찾기 어려워짐.
반성 기록은 `reflections` 테이블(PostgreSQL)과 ChromaDB에 이중 저장되며, 두 저장소의 내용은 동일하지 않을 수 있음.

### 설계안

#### 검색 모드
| 모드 | 동작 | 데이터 소스 |
|------|------|------------|
| 키워드 검색 | 텍스트 LIKE/ILIKE 매칭 | `reflections` 테이블 (`reflection_text`) |
| 시멘틱 검색 | 의미 기반 유사도 검색 | ChromaDB (`reflection` 컬렉션) |

#### UI
- 매매검증 탭 상단에 검색창 + 모드 토글 (키워드 / 시멘틱)
- 검색 결과를 기존 리스트와 동일한 카드 형태로 표시

#### 추가 고려사항
- **reflections ↔ ChromaDB 동기화**: 하루 1회 스케줄러로 테이블 → ChromaDB sync 실행. 누락/불일치 건 보정
- **검색 API**: `GET /reflections/search?q=...&mode=keyword|semantic`
