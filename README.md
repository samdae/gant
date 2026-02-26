# G-ANT

**Live** — [https://daehun.app](https://daehun.app)

12개 AI 에이전트가 협업하여 주식을 분석하고,
가상 매매로 판단을 검증하며,
실패에서 스스로 학습하는 투자 분석 시스템.

```
[분석검증 모드] 티커별 독립 분석 + 가상 매매
데이터 수집 → 투자 토론 → 리스크 토론 → 매매 판단 → 가상 매매 → 청산 시 반성
                         ↑                                              │
                         └──────── 경험이 다음 판단에 반영 ─────────────┘

[포트폴리오 모드] 전체 티커 분석 완료 후 자동 실행
전체 분석 결과 → 비서 브리핑 → 포트폴리오 PA 리밸런싱 → 매매 실행 → 주간 회고
                  ↑                                                       │
                  └───────── 포트폴리오 경험이 다음 배분에 반영 ──────────┘
```

---

## 어떻게 분석하는가

### 파이프라인

```
                    ┌─ Market Analyst
  데이터 수집       ├─ Social Analyst
  (4명 독립 분석)   ├─ News Analyst
                    └─ Fundamentals Analyst
                              ↓
  투자 토론         Bull Researcher ←→ Bear Researcher (N회)
                              ↓
                       Research Manager (판결)
                              ↓
  매매 판단                Trader
                              ↓
  리스크 토론       Aggressive ←→ Conservative ←→ Neutral (N회)
                              ↓
                        Risk Judge (최종 BUY/SELL/HOLD)
                              ↓
  실행              Portfolio Agent (매매 수량 결정)
```

### 분석 흐름

**데이터 수집** — 4명의 분석가가 각각 시장 데이터, 소셜 감성, 뉴스, 재무제표를 독립 분석한다.

**투자 토론** — 분석 보고서를 바탕으로 강세/약세 리서처가 N라운드 토론.
Research Manager가 양측 논거를 종합하여 판결.

**리스크 토론** — Trader의 투자 계획에 대해 공격적/보수적/중립 3명이 N라운드 토론.
Risk Judge가 최종 BUY/SELL/HOLD + `strategy_json`(확신도, 비중)을 구조화 출력.

**실행** — Portfolio Agent가 파이프라인 결정과 과거 경험(RAG)을 종합하여 매매 수량 결정.
가용 현금 대비 `allocation_pct` 기반으로 계산한다.

> 12에이전트 파이프라인은 **포지션 정보 없이 완전 객관적으로** 분석한다.
> 포지션을 아는 것은 마지막 Portfolio Agent뿐이다.

---

## 어떻게 학습하는가

가상 매매로 분석 결과를 추적하고,
포지션 청산 시 전체 사이클을 되돌아보며 교훈을 추출한다.

### 분석검증 모드 (가상 매매)

- 티커당 $5,000 독립 자금 — 포지션 간 간섭 없음
- 매수/매도 모두 PA가 수량 결정 (소수점 매매 지원)
- 포지션 전량 청산 시 반성 에이전트 가동

### 포트폴리오 모드 (v6)

- 공유 자금 풀 1억원 (KRW) — 분석검증 자금과 완전 분리
- 전체 티커 분석 완료 → 비서 에이전트가 브리핑 → PortfolioManagerAgent가 리밸런싱 결정
- 혼합 통화 지원 (USD+KRW), yfinance 실시간 환율 적용
- 시장별 거래 수수료: US 0.1%, KR 0.015%+세금, Crypto 0.04%
- 주간 회고로 배분 품질 자체 평가 → 경험이 다음 배분에 반영

### 반성 에이전트

- 해당 포지션의 **전체 분석 리포트 + 매매 이력**을 LLM에 전달
- 반성문 + 핵심 교훈 생성
- 성공/실패 레이블 + 섹터/산업/시장 메타데이터와 함께 저장

### Hybrid RAG

- 다음 분석에서 PA가 유사 경험을 검색
- **Postgres FTS**(키워드) + **ChromaDB**(시맨틱) → **RRF Fusion**
- 경험이 있으면 → 분석 60% + 경험 40% 가중치로 **독립 판단**
- 경험이 없으면 → 파이프라인 결정을 **그대로 따름**
- 검색 쿼리에 market/sector 맥락 부착 → 같은 시장/섹터 경험 우선 매칭
- `usefulness_score` 기반 쓰레기 문서 점진적 필터링 (RAG Validator)

### RAG Validator

- 회고분석 결과를 기반으로 RAG 문서별 유용성 평가
- PA가 해당 경험을 실제로 반영했는지 문서 단위 판정
- `usefulness_score` ±1 자동 조정 → 40 미만 시 검색에서 배제
- 효과 분석 리포트 생성 → 사람이 읽고 판단

### 회고분석 배점 (v6)

- 12에이전트 분석의 시장 움직임 대비 정확도 (0~100)
- RAG 경험이 PA 판단에 실제 기여한 정도 (0~100)
- 회고분석 프롬프트에서 자동 추출 → 대시보드 표시

---

## 어떻게 동작하는가

### 자동 스케줄

- 티커별 APScheduler가 주기적으로 분석 트리거
- `asyncio.Queue` → 워커 1개가 순차 처리 (LLM rate limit 대응)
- 새 시장 데이터가 없으면 스킵
- 파싱/에이전트 실패 시 자동 1회 재큐잉
- 서버 재시작 시 미완료 스케줄 자동 복구

### 실시간 모니터링

- 분석 중 에이전트 진행 상태를 **WebSocket으로 실시간 스트리밍**
- 동시에 DB에 영속화 → 이후 이력 조회 가능

### 웹 대시보드

- Svelte SPA — 포지션, 스케줄, 리포트, 실시간 모니터링
- 모바일 최적화 다크 테마, PWA 설치 지원

---

## 기술 구성

| 영역 | 스택 |
|------|------|
| 백엔드 | Python 3.10+, FastAPI, LangGraph, APScheduler |
| 프론트엔드 | Svelte 4, TypeScript, Vite |
| 데이터베이스 | PostgreSQL 17, ChromaDB |
| LLM | Google Gemini — OAuth 인증, API 키 불필요 |
| 데이터 | yfinance (기본) → Alpha Vantage (자동 폴백) |

> LLM Resilience: 429 → 동일 모델 재시도 (최대 5회) / 503 → 하위 모델 자동 폴백

---

## 문서

| 문서 | 설명 |
|------|------|
| [spec.md](docs/tradingagents/spec.md) | 요구사항 정의 (FR-001~061) |
| [arch-be.md](docs/tradingagents/arch-be.md) | 백엔드 설계 — DB 스키마, API 명세, 에러 처리 |
| [arch-fe.md](docs/tradingagents/arch-fe.md) | 프론트엔드 설계 — 컴포넌트, 상태 관리, 라우팅 |
| [ui.md](docs/tradingagents/ui.md) | UI 명세 — 화면별 컴포넌트, 상태, 인터랙션 |
| [USAGE_GUIDE.md](docs/USAGE_GUIDE.md) | 설치·실행·API 사용 가이드 |

---

<details>
<summary><b>수집 데이터: 15개 기술 지표</b></summary>

<br>

LLM에게 15개 지표 목록이 주어지고, 상호 보완적인 최대 8개를 자율 선택한다.

| 카테고리 | 지표            | 설명                                            |
| -------- | --------------- | ----------------------------------------------- |
| 이동평균 | `close_50_sma`  | 50일 단순이동평균 — 중기 추세                   |
|          | `close_200_sma` | 200일 단순이동평균 — 장기 추세, 골든/데드크로스 |
|          | `close_10_ema`  | 10일 지수이동평균 — 단기 모멘텀                 |
| MACD     | `macd`          | EMA 차이 기반 모멘텀                            |
|          | `macds`         | MACD 시그널 라인                                |
|          | `macdh`         | MACD 히스토그램 — 모멘텀 강도                   |
| 모멘텀   | `rsi`           | RSI — 과매수(70↑)/과매도(30↓)                   |
| 변동성   | `boll`          | 볼린저 밴드 중간선 (20 SMA)                     |
|          | `boll_ub`       | 볼린저 상단밴드 (+2σ)                           |
|          | `boll_lb`       | 볼린저 하단밴드 (-2σ)                           |
|          | `atr`           | ATR — 평균 진폭                                 |
| 거래량   | `vwma`          | 거래량 가중 이동평균                            |
|          | `mfi`           | MFI — 매수/매도 압력                            |

</details>

<details>
<summary><b>수집 데이터: 28개 펀더멘탈 지표</b></summary>

<br>

시가총액, P/E(TTM), Forward P/E, PEG, P/B, EPS(TTM), Forward EPS, 배당수익률, Beta, 52주 고가/저가, 50/200일 평균가, 매출(TTM), 매출총이익, EBITDA, 순이익, 이익률, 영업이익률, ROE, ROA, 부채비율, 유동비율, 장부가치, FCF

</details>

---

## License

[Apache License 2.0](LICENSE)
