# Proposal v6: 포트폴리오 모드 + 회고분석 배점

> **상태**: 미구현 — v5 안정화 및 데이터 축적 후 착수  
> **선행 조건**: v5 (RAG 검색 파이프라인 개편, RAG Validator) 운영 안정화

---

## 1. 목적

현재 시스템은 **분석검증모드** 단일 모드로 운영된다. 티커당 독립 자금($5,000 / ₩5,000,000)을 배정하고, PA는 파이프라인 결론의 실행자로서 분석 정확도를 순수 측정한다.

본 제안은 두 가지를 정의한다:

1. **포트폴리오 모드** — 공유 가상 자금 풀에서 종목 간 배분을 결정하는 실전 시뮬레이션 모드
2. **회고분석 배점** — 회고분석 에이전트가 분석 정확도와 RAG 기여도를 수치화하여 대시보드에 표시

---

## 2. 두 모드의 설계 철학

### 분석검증모드 (기존, 유지)

**목적**: 12에이전트 파이프라인의 분석이 맞는가?

통제된 실험이다. 변수를 최소화하여 분석 품질을 순수 측정한다.

```
12에이전트 분석 → 고정 결론 → PA(실행자) + 유일한 변수 RAG → 결과
```

- PA는 파이프라인 결론을 거의 그대로 실행
- 비중은 파이프라인이 결정 (allocation_pct 기반 25/50/75%)
- 티커당 독립 자금 → 종목 간 간섭 없음
- 결과가 좋으면 → 분석이 맞았거나 RAG가 도움됨
- 결과가 나쁘면 → 분석이 틀렸거나 RAG가 오염됨
- v5 RAG Validator가 RAG 효과를 분리 측정 → 최종적으로 "분석 정확도"와 "RAG 기여도"를 각각 평가 가능

### 포트폴리오 모드 (신규)

**목적**: 분석 + 자원 배분을 종합한 실전 시뮬레이션

PA에게 **자원 배분**이라는 차원을 추가한다. 같은 BUY 판정이라도 "포트폴리오의 60%가 이미 테크 섹터인데 또 테크를 살 것인가?"라는 맥락이 생긴다.

```
12에이전트 분석 → 고정 결론 → PA(펀드매니저) + RAG + 포트폴리오 상태 → 결과
```

- PA가 전체 포트폴리오를 보고 **자체 전략을 수립**
- 비중은 PA가 직접 계산 (섹터 분산, 현금 비율, 기회비용)
- 공유 자금 풀 → 종목 간 경쟁
- 반성의 질이 달라짐: "이 종목이 틀렸다"가 아니라 "이 종목에 너무 많이 태웠다"

### 두 모드 공존의 가치

두 모드의 성과 차이 자체가 인사이트다. 분석검증 승률은 높은데 포트폴리오 수익이 낮으면 → "AI가 종목 분석은 잘하는데 자원 배분은 못한다". 반대면 → "개별 분석은 부정확하지만 포트폴리오 레벨에서 분산이 리스크를 상쇄한다".

---

## 3. 포트폴리오 모드 상세

### 3-1. PA 역할 변경

| | 분석검증 PA (기존) | 포트폴리오 PA (신규) |
|--|-------------------|---------------------|
| 역할 | 실행자 | 펀드매니저 |
| 입력 | 해당 종목 포지션 + 독립 자금 | **전체 포트폴리오 상태** + 공유 자금 |
| 비중 결정 | 파이프라인이 줌 (allocation_pct) | PA가 직접 계산 |
| 판단 기준 | 이 종목의 확신도 | 확신도 + 섹터 분산 + 기회비용 + 현금 비율 |
| 매매 단위 | 뭉툭 (25/50/75%) | 세밀 (금액/비중 단위, 소수점) |
| 전략 | 파이프라인 결론 수용/거부 | **자체 포트폴리오 전략 수립** (리밸런싱, 헤지, 현금 확보) |

### 3-2. 포트폴리오 PA에 주입되는 컨텍스트

```
[포트폴리오 상태]
총 자금: $50,000
가용 현금: $23,500
투자 비중: 53%

[보유 포지션]
NVDA: $12,000 (24%) — 테크/반도체 — 수익률 +8.2%
GOOGL: $8,500 (17%) — 통신서비스 — 수익률 -1.3%
GLD: $6,000 (12%) — 원자재/금 — 수익률 +2.1%

[섹터 분포]
테크: 24% | 통신: 17% | 원자재: 12% | 현금: 47%

[이번 분석 대상]
티커: TSLA (테크/전기차)
파이프라인 결론: BUY, conviction=high
```

PA는 이 컨텍스트를 보고:
- "테크 비중이 이미 24%인데 TSLA까지 사면 테크 편중이 심해진다"
- "현금 47%는 여유가 있으니 일부 투입 가능하다"
- "GLD가 헤지 역할이니 유지하고, TSLA에 $5,000 (10%) 배분"

같은 판단을 내린다.

### 3-3. 스키마 변경

#### schedule_configs 변경

```sql
ALTER TABLE schedule_configs ADD COLUMN mode TEXT NOT NULL DEFAULT 'validation';
-- UNIQUE 제약 변경: (ticker) → (ticker, mode)
ALTER TABLE schedule_configs DROP CONSTRAINT schedule_configs_ticker_key;
ALTER TABLE schedule_configs ADD CONSTRAINT schedule_configs_ticker_mode_key UNIQUE (ticker, mode);
```

| 컬럼 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `mode` | TEXT NOT NULL | `'validation'` | `validation` / `portfolio` |

#### positions / trades 변경

```sql
ALTER TABLE positions ADD COLUMN mode TEXT NOT NULL DEFAULT 'validation';
ALTER TABLE trades ADD COLUMN mode TEXT NOT NULL DEFAULT 'validation';
```

#### 포트폴리오 자금 설정

환경변수로 관리:
```bash
PORTFOLIO_INITIAL_CAPITAL=50000        # USD 포트폴리오
PORTFOLIO_INITIAL_CAPITAL_KRW=50000000 # KRW 포트폴리오
```

또는 별도 설정 테이블 (향후 UI에서 조정 가능하도록):

```sql
CREATE TABLE IF NOT EXISTS portfolio_configs (
    id              BIGSERIAL PRIMARY KEY,
    currency        TEXT NOT NULL UNIQUE,     -- 'USD' / 'KRW'
    initial_capital DOUBLE PRECISION NOT NULL, -- 초기 자금
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3-4. 현금 계산

| | 분석검증 | 포트폴리오 |
|--|---------|-----------|
| 자금 | 티커당 독립 (`schedule_configs.initial_capital`) | 통화별 공유 풀 (`portfolio_configs.initial_capital`) |
| 현금 | `initial_capital - 해당 티커 active BUY + SELL` | `portfolio_capital - 전체 portfolio 모드 active BUY + SELL` |
| 쿼리 범위 | `WHERE p.ticker = :ticker AND p.mode = 'validation'` | `WHERE p.mode = 'portfolio' AND p.currency = :currency` |

### 3-5. PA 클래스 분리

프롬프트 분기가 아닌 **별도 클래스**로 분리를 권장한다. 입력 데이터, 판단 로직, 출력 포맷이 전부 다르기 때문.

| 클래스 | 파일 | 역할 |
|--------|------|------|
| `PortfolioAgent` (기존) | `virtual_trade/portfolio_agent.py` | 분석검증 PA — 실행자 |
| `PortfolioManagerAgent` (신규) | `virtual_trade/portfolio_manager_agent.py` | 포트폴리오 PA — 펀드매니저 |

스케줄러에서 `schedule_configs.mode`를 보고 어느 PA를 호출할지 분기.

### 3-6. 반성 차이

| | 분석검증 반성 | 포트폴리오 반성 |
|--|-------------|---------------|
| 초점 | "이 종목의 분석이 맞았는가?" | "이 종목에 대한 배분이 적절했는가?" |
| 맥락 | 해당 종목 리포트 + 매매 이력 | 해당 종목 + **당시 전체 포트폴리오 상태** |
| 교훈 | 분석 패턴, 진입/청산 타이밍 | 배분 비율, 섹터 편중, 현금 관리 |

반성 프롬프트도 모드별 분기 필요. 포트폴리오 반성에는 청산 시점의 전체 포트폴리오 스냅샷을 주입.

---

## 4. 회고분석 배점

### 4-1. 배경

현재 회고분석은 텍스트 분석 결과(`analysis_content`)만 저장한다. 분석 정확도와 RAG 기여도를 수치화하면 대시보드에서 시스템 전체의 성능을 한눈에 파악할 수 있다.

승률(wins/losses)은 "이겼나 졌나"만 보지만, 회고분석 배점은 **과정의 타당성**을 수치화한다:
- 분석이 맞았는데 운 나빠서 진 것 → 분석 정확도 높음, 수익률 마이너스
- 분석이 틀렸는데 운 좋게 이긴 것 → 분석 정확도 낮음, 수익률 플러스

### 4-2. 스키마 변경

`retrospective_analyses` 테이블에 컬럼 추가:

```sql
ALTER TABLE retrospective_analyses ADD COLUMN analysis_accuracy INTEGER;
ALTER TABLE retrospective_analyses ADD COLUMN rag_contribution INTEGER;
```

| 컬럼 | 타입 | 범위 | 설명 |
|------|------|------|------|
| `analysis_accuracy` | INTEGER | 0~100 | 12에이전트 분석의 실제 시장 움직임 대비 정확도 |
| `rag_contribution` | INTEGER | 0~100, NULL | RAG 경험의 PA 판단 기여도. RAG 미사용 시 NULL |

### 4-3. 배점 기준

회고분석 프롬프트에 추가할 지시:

#### analysis_accuracy (0~100)

12에이전트 파이프라인의 분석이 실제 시장 움직임과 얼마나 일치했는가를 평가.

| 점수 | 기준 |
|------|------|
| 90~100 | 방향, 타이밍, 근거 모두 정확. 분석 논리가 시장 결과와 완전히 일치 |
| 70~89 | 방향은 맞았으나 타이밍 또는 근거에 부분 오류. 핵심 판단은 유효 |
| 50~69 | 방향은 맞았으나 근거가 부실하거나 우연히 맞음. 재현 가능성 낮음 |
| 30~49 | 방향이 틀렸으나 일부 분석(섹터, 매크로 등)은 유효 |
| 0~29 | 전반적으로 부정확. 시장 상황을 오독 |

#### rag_contribution (0~100, RAG 미사용 시 null)

RAG로 주입된 과거 경험이 PA 판단에 얼마나 기여했는가를 평가.

| 점수 | 기준 |
|------|------|
| 90~100 | RAG 경험이 판단의 핵심 근거. 경험 없이는 다른 결정을 했을 것 |
| 70~89 | RAG 경험이 판단에 유의미하게 반영. 확신도나 비중에 영향 |
| 50~69 | RAG 경험이 언급됐으나 판단에 결정적이지 않음 |
| 30~49 | RAG 경험이 거의 무시됨. 파이프라인 결론에만 의존 |
| 0~29 | RAG 경험이 오히려 판단을 방해하거나 완전히 무관 |

### 4-4. 프롬프트 추가

기존 회고분석 프롬프트 출력 형식에 추가:

```
**Output Format**:
- Reflection: 포괄적 분석 (800-1200 토큰)
- Key Lessons: RAG 쿼리용 간결한 요약 (200-400 토큰)
- analysis_accuracy: 정수 (0~100)
- rag_contribution: 정수 (0~100) 또는 null (RAG 미사용 시)
```

### 4-5. 파싱

회고분석 LLM 응답에서 `analysis_accuracy: N`, `rag_contribution: N`을 추출.

```python
import re

def _parse_scores(text: str) -> tuple[int | None, int | None]:
    accuracy = None
    contribution = None

    m = re.search(r'analysis_accuracy\s*[:=]\s*(\d+)', text)
    if m:
        accuracy = max(0, min(100, int(m.group(1))))

    m = re.search(r'rag_contribution\s*[:=]\s*(\d+|null)', text, re.IGNORECASE)
    if m and m.group(1).lower() != 'null':
        contribution = max(0, min(100, int(m.group(1))))

    return accuracy, contribution
```

파싱 실패 시 NULL 저장. 회고분석 결과 자체는 정상 저장.

### 4-6. 대시보드 표시

```
분석 정확도: 72점 (23건 평균)
RAG 기여도: 58점 (RAG 사용 15건 평균)
```

#### API 변경

`GET /metrics` 응답에 추가:

```json
{
  "analysis_accuracy_avg": 72.3,
  "analysis_accuracy_count": 23,
  "rag_contribution_avg": 58.1,
  "rag_contribution_count": 15
}
```

쿼리:

```sql
SELECT
    AVG(analysis_accuracy) AS analysis_accuracy_avg,
    COUNT(analysis_accuracy) AS analysis_accuracy_count,
    AVG(rag_contribution) AS rag_contribution_avg,
    COUNT(rag_contribution) AS rag_contribution_count
FROM retrospective_analyses
WHERE status = 'completed'
  AND analysis_accuracy IS NOT NULL
```

포트폴리오 모드가 추가되면 `mode` 필터 적용:

```sql
WHERE ... AND mode = :mode
```

---

## 5. 전체 흐름도

```
[분석검증모드]
12에이전트 → PA(실행자) → 매매 → 청산 시 반성 → RAG
                                      ↓
                                 회고분석 → 분석정확도 + RAG기여도 채점
                                      ↓
                                 RAG Validator → usefulness_score ±1

[포트폴리오모드]
12에이전트 → PA(펀드매니저) + 포트폴리오 상태 → 매매 → 청산 시 반성 → RAG
                                                          ↓
                                                     회고분석 → 분석정확도 + RAG기여도 + 배분적정성 채점

[대시보드]
분석 정확도: 72점 (23건 평균)
RAG 기여도: 58점 (15건 평균)
포트폴리오 수익률: +12.3%
분석검증 승률: 65%
```

---

## 6. 결정 사항 요약

| 항목 | 결정 | 근거 |
|------|------|------|
| 분석검증 PA 변경 | X (유지) | 변수 최소화로 분석 정확도 순수 측정. PA에 전략 자유도를 주면 귀인이 불가능해짐 |
| 포트폴리오 PA 분리 | 별도 클래스 (`PortfolioManagerAgent`) | 입력/판단/출력 전부 다름. 프롬프트 분기로는 부족 |
| 스키마 mode 컬럼 | `schedule_configs`, `positions`, `trades` | 같은 티커를 양쪽 모드에서 동시 운영 가능 |
| 포트폴리오 자금 | 환경변수 또는 `portfolio_configs` 테이블 | 초기엔 환경변수, 향후 UI 설정 대비 테이블 |
| 회고분석 배점 | `analysis_accuracy` + `rag_contribution` | LLM이 과정 타당성을 수치화. 승률보다 정밀 |
| 배점 범위 | 0~100 정수 | 직관적, 평균 계산 용이 |
| 대시보드 표시 | metrics API에 평균값 추가 | 전체 시스템 성능 한눈에 파악 |
| 반성 프롬프트 분기 | 모드별 분리 | 포트폴리오 반성은 배분 적정성 + 전체 스냅샷 필요 |
| 12에이전트 파이프라인 | 양 모드 동일 | 분석은 객관적으로 동일하게 수행. 모드 차이는 PA 이후에만 발생 |

---

## 7. 구현 순서 (권장)

1. **회고분석 배점 먼저** — 스키마 ALTER 2개 + 프롬프트 추가 + 파싱. 기존 시스템에 영향 없음
2. **대시보드 표시** — metrics API 필드 추가 + FE 표시
3. **포트폴리오 모드 스키마** — mode 컬럼 + portfolio_configs 테이블
4. **PortfolioManagerAgent** — PA 신규 클래스 + 프롬프트 설계
5. **스케줄러 분기** — mode에 따라 PA 선택
6. **포트폴리오 반성 프롬프트** — 전체 스냅샷 주입 + 배분 적정성 평가
7. **FE** — 모드 전환 UI + 포트폴리오 대시보드
