# Proposal v7: 매크로 지표 + 섹터 호황도 주입

> **상태**: 미구현 — v6 회고분석 배점 구현 후 착수 가능 (포트폴리오 모드보다 우선)  
> **선행 조건**: 현재 분석 파이프라인이 정상 운영 중이면 즉시 가능. v5/v6과 독립적.

---

## 1. 목적

현재 12에이전트는 **개별 종목만 보고** 판단한다. NVDA의 기술적 지표가 BUY를 가리켜도, 나스닥 전체가 고평가 구간이고 금리가 오르는 중이면 의미가 달라진다. 이 거시적 맥락이 빠져 있다.

본 제안은 분석 파이프라인 앞단에 **매크로 지표 + 섹터 호황도**를 수집하여 12에이전트와 PA 전부에게 주입한다.

### 핵심 원칙

- **LLM 호출 없음** — yfinance 데이터 fetch + 계산만. 비용 제로, 수초 소요
- **시장별 차등 주입** — 나스닥/코스피/코인 각각 핵심 지표만 (덜어내는 철학)
- **데이터 소스 단일화** — 전부 yfinance. 외부 API 의존성 제로
- **지표 해석 규칙 없음** — 수치만 주고 LLM이 해석. 유효성은 시스템이 운영되면서 반성/RAG로 자체 검증

### 객관성과의 관계

분석 객관성(FR-021)은 **포지션 정보를 모르게 하는 것**이지, 시장 상황을 모르게 하는 것이 아니다. 포지션을 알면 확증 편향이 생기지만, 시장이 상승장인지 하락장인지 아는 건 편향이 아니라 **분석의 기본 맥락**이다.

- PA만 아는 변수: **포지션** (확증 편향 방지)
- 전부 아는 변수: **시장 상황** (분석의 기본 맥락)

---

## 2. 시장별 매크로 지표

### 2-1. 나스닥 (US) — 4개

| 지표 | yfinance 소스 | 계산 | 의미 |
|------|-------------|------|------|
| VIX (공포지수) | `^VIX` | 종가 | 시장 불안 수준. 높으면 공포, 낮으면 탐욕 |
| Fed Funds Rate | `^IRX` (13주 T-Bill) | 종가 / 100 | 단기 금리 프록시. 통화 정책 방향 |
| 장단기 금리차 | `^TNX` - `^IRX` | 10Y - 3M 스프레드 | 양수=정상, 음수=역전(경기 침체 선행 신호) |
| 나스닥 추세 | `^IXIC` | 현재가 vs 50일/200일 이동평균 | 중기/장기 추세 방향 |

### 2-2. 코스피 (KR) — 4개

| 지표 | yfinance 소스 | 계산 | 의미 |
|------|-------------|------|------|
| VKOSPI (공포지수) | `^VKOSPI` | 종가 | 한국 시장 불안 수준 |
| USDKRW 환율 | `USDKRW=X` | 종가 | 원화 약세면 외국인 이탈, 강세면 유입. 코스피의 핵심 드라이버 |
| 코스피 추세 | `^KS11` | 현재가 vs 50일/200일 이동평균 | 중기/장기 추세 방향 |
| 섹터 ETF 상대 강도 | 아래 매핑 참조 | 섹터 ETF 20일 수익률 / 코스피 20일 수익률 | 해당 섹터가 시장 대비 강한지 약한지 |

> 한은 기준금리는 yfinance에 없고 FRED API 의존이 필요하므로 제외. USDKRW 환율이 금리 차이를 이미 반영하며, 한국 시장에서 금리보다 환율이 더 직접적인 드라이버.

### 2-3. 코인 (Crypto) — 3개

| 지표 | yfinance 소스 | 계산 | 의미 |
|------|-------------|------|------|
| BTC 20일 변동성 | `BTC-USD` | 20일 종가 표준편차 (연율화) | 공포/탐욕 프록시. 변동성 높으면 공포, 낮으면 탐욕. 외부 API 없이 동일 정보 |
| DXY (달러 인덱스) | `DX-Y.NYB` | 종가 | 달러 강세 = 크립토 약세 (역상관) |
| BTC 도미넌스 | `BTC-USD` 시가총액 / 전체 크립토 시총 | 계산 필요 (아래 참조) | 리스크 온/오프. 도미넌스 상승 = 알트 약세, 자금 BTC 집중 |

> BTC 도미넌스 계산: `yf.Ticker("BTC-USD").info["marketCap"]` / `yf.Ticker("^CMC200").info["marketCap"]` 또는 전체 크립토 시총 프록시. 정확한 소스가 없으면 BTC 시총 단독으로 추세만 제공.

---

## 3. 섹터 호황도

### 3-1. 자동 섹터 판별

`yf.Ticker(ticker).info["sector"]`로 자동 판별. 이미 반성 에이전트 메타데이터 태깅(FR-029)에서 사용 중.

### 3-2. 섹터 → ETF 매핑 (US)

S&P GICS 표준 11개 섹터. 전부 대응 ETF 존재.

| # | yfinance sector 값 | ETF | 대표 종목 |
|---|-------------------|-----|----------|
| 1 | Technology | XLK | NVDA, AAPL, MSFT |
| 2 | Communication Services | XLC | GOOGL, META |
| 3 | Consumer Cyclical | XLY | TSLA, AMZN |
| 4 | Consumer Defensive | XLP | PG, KO |
| 5 | Energy | XLE | OXY, XOM |
| 6 | Financial Services | XLF | JPM, BAC |
| 7 | Healthcare | XLV | JNJ, UNH |
| 8 | Industrials | XLI | CAT, GE |
| 9 | Basic Materials | XLB | LIN, APD |
| 10 | Real Estate | XLRE | DLR, AMT |
| 11 | Utilities | XLU | NEE, SO |

### 3-3. 섹터 → ETF 매핑 (KR)

8/11 섹터 대응. 없는 3개는 코스피 전체(`^KS11`)로 대체.

| # | yfinance sector 값 | ETF (yfinance 코드) | 비고 |
|---|-------------------|-------------------|------|
| 1 | Technology | `091160.KS` | KODEX 반도체 |
| 2 | Communication Services | — | 코스피(`^KS11`)로 대체 |
| 3 | Consumer Cyclical | `305720.KS` | KODEX 2차전지 |
| 4 | Consumer Defensive | `266390.KS` | KODEX 필수소비재 |
| 5 | Energy | `117460.KS` | KODEX 에너지화학 |
| 6 | Financial Services | `091170.KS` | KODEX 은행 |
| 7 | Healthcare | `266420.KS` | KODEX 헬스케어 |
| 8 | Industrials | `102780.KS` | KODEX 기계장비 |
| 9 | Basic Materials | `117680.KS` | KODEX 철강 |
| 10 | Real Estate | — | 코스피(`^KS11`)로 대체 |
| 11 | Utilities | — | 코스피(`^KS11`)로 대체 |

### 3-4. 호황도 계산

| 지표 | 계산 | 의미 |
|------|------|------|
| SPY/코스피 대비 상대 강도 | 섹터 ETF 20일 수익률 - SPY(또는 코스피) 20일 수익률 | 양수=강세, 음수=약세 |
| 50일선 추세 | 섹터 ETF 현재가 vs 50일 이동평균 | 위=상승 추세, 아래=하락 추세 |

### 3-5. 코인은 섹터 없음

코인 티커(BTC-USD 등)는 섹터 개념이 없으므로 섹터 호황도 주입을 스킵. 매크로 지표만 주입.

---

## 4. 주입 방식

### 4-1. 파이프라인 위치

```
[신규] 매크로 + 섹터 데이터 수집 (yfinance fetch + 계산)
  ↓ 결과를 AgentState에 주입
12에이전트 분석 (매크로/섹터 컨텍스트 참조)
  ↓
PA (매크로/섹터 컨텍스트 + 파이프라인 결론 + RAG + 포지션)
```

### 4-2. AgentState 주입 포맷

텍스트로 정리하여 각 에이전트 프롬프트에 주입:

```
[매크로 — 나스닥]
VIX: 15.3 (낮음)
Fed Rate (3M T-Bill): 4.25%
장단기 금리차 (10Y-3M): +0.82% (정상)
나스닥: 50일선 위 (+3.2%), 200일선 위 (+18.5%)

[섹터 — Technology (XLK)]
SPY 대비 상대 강도 (20일): +3.2% (강세)
XLK 50일선: 위 (+2.1%, 상승 추세)
```

코스피 티커 예시:

```
[매크로 — 코스피]
VKOSPI: 18.7
USDKRW: 1,342원 (20일 전 대비 -1.2%, 원화 강세)
코스피: 50일선 위 (+1.8%), 200일선 위 (+12.3%)

[섹터 — Technology (KODEX 반도체, 091160.KS)]
코스피 대비 상대 강도 (20일): +5.1% (강세)
091160.KS 50일선: 위 (+3.4%, 상승 추세)
```

### 4-3. 구현 위치

```python
# 신규 모듈: tradingagents/dataflows/macro_collector.py

class MacroCollector:
    """매크로 지표 + 섹터 호황도 수집기."""

    SECTOR_ETF_US = {
        "Technology": "XLK",
        "Communication Services": "XLC",
        "Consumer Cyclical": "XLY",
        "Consumer Defensive": "XLP",
        "Energy": "XLE",
        "Financial Services": "XLF",
        "Healthcare": "XLV",
        "Industrials": "XLI",
        "Basic Materials": "XLB",
        "Real Estate": "XLRE",
        "Utilities": "XLU",
    }

    SECTOR_ETF_KR = {
        "Technology": "091160.KS",
        "Consumer Cyclical": "305720.KS",
        "Consumer Defensive": "266390.KS",
        "Energy": "117460.KS",
        "Financial Services": "091170.KS",
        "Healthcare": "266420.KS",
        "Industrials": "102780.KS",
        "Basic Materials": "117680.KS",
    }

    def collect(self, ticker: str, market: str) -> str:
        """매크로 + 섹터 데이터를 텍스트로 반환."""
        macro = self._collect_macro(market)
        sector = self._collect_sector(ticker, market)
        return f"{macro}\n\n{sector}"
```

### 4-4. 스케줄러 연동

`_run_analysis_cycle_impl`에서 파이프라인 실행 전에 `MacroCollector.collect(ticker, market)` 호출. 결과를 `AgentState`에 `macro_context` 키로 주입. 12에이전트와 PA가 이 값을 프롬프트에서 참조.

---

## 5. 캐싱

같은 시장의 매크로 지표는 당일 모든 티커에 동일하다. 티커마다 다시 fetch하면 낭비.

| 데이터 | 캐시 범위 | TTL |
|--------|----------|-----|
| 매크로 지표 (VIX, 금리 등) | 시장별 1회 | 당일 |
| 섹터 ETF 데이터 | 섹터별 1회 | 당일 |

```python
_macro_cache: Dict[str, Tuple[str, str]] = {}  # {market: (date, text)}
_sector_cache: Dict[str, Tuple[str, str]] = {}  # {sector_etf: (date, text)}
```

21개 티커가 순차 실행되므로 첫 번째 US 티커에서 매크로를 fetch하면 나머지 US 티커는 캐시 히트. 같은 섹터 티커도 캐시 히트.

---

## 6. 에러 처리

| 상황 | 처리 |
|------|------|
| yfinance 매크로 fetch 실패 | 해당 지표 `"N/A"` 표시, 나머지 정상 진행 |
| 섹터 판별 실패 (`info["sector"]` 없음) | 섹터 호황도 스킵, 매크로만 주입 |
| 섹터 ETF 매핑 없음 (KR 3개 섹터) | 시장 전체 지수(`^KS11`)로 대체 |
| 전체 매크로 수집 실패 | 매크로 없이 기존 방식으로 분석 진행 (graceful degradation) |

분석이 매크로 수집 실패로 중단되면 안 된다. 매크로는 맥락 보강이지 필수 입력이 아니다.

---

## 7. 결정 사항 요약

| 항목 | 결정 |
|------|------|
| 주입 대상 | 12에이전트 + PA 전부 |
| 데이터 소스 | yfinance 단일 (외부 API 의존성 제로) |
| 나스닥 지표 | VIX, Fed Rate (3M T-Bill), 장단기 금리차, 나스닥 추세 (4개) |
| 코스피 지표 | VKOSPI, USDKRW 환율, 코스피 추세, 섹터 ETF 상대 강도 (4개) |
| 코인 지표 | BTC 20일 변동성, DXY, BTC 도미넌스 (3개) |
| 섹터 판별 | `yf.Ticker(ticker).info["sector"]` 자동 |
| 섹터 ETF | US 11/11 완비, KR 8/11 (없으면 코스피 대체) |
| 호황도 계산 | 시장 대비 상대 강도 (20일) + 50일선 추세 |
| 코인 섹터 | 없음 (매크로만) |
| 캐싱 | 시장별/섹터별 당일 1회 fetch |
| 에러 처리 | graceful degradation (실패해도 분석 진행) |
| 구현 위치 | `tradingagents/dataflows/macro_collector.py` 신규 모듈 |
| LLM 호출 | 없음 (데이터 fetch + 계산만) |
| 지표 해석 규칙 | 없음 (수치만 주고 LLM이 해석) |
| 우선순위 | v6 포트폴리오 모드보다 높음. 회고분석 배점과 동등 또는 선행 |
