# G-ANT

> **Live**: [https://daehun.app](https://daehun.app)

12개 AI 에이전트가 협업하여 주식을 분석하고, 가상 매매로 판단을 검증하며, 실패에서 스스로 학습하는 투자 분석 시스템.

시장 데이터 수집 → 강세/약세 토론 → 리스크 3자 토론 → 매매 판단 → 가상 매매 실행 → 청산 시 반성/학습. 이 사이클이 티커별로 자동 반복되며, 축적된 경험이 다음 판단에 반영된다.

---

## 어떻게 분석하는가

```
Market Analyst ──→ Social Analyst ──→ News Analyst ──→ Fundamentals Analyst
                                                              │
                              Bull Researcher ←→ Bear Researcher (N회 토론)
                                          │
                                   Research Manager (판결)
                                          │
                                       Trader (투자 계획)
                                          │
                    Aggressive ←→ Conservative ←→ Neutral (N회 리스크 토론)
                                          │
                                   Risk Judge (최종 판결 + strategy_json)
                                          │
                                   Portfolio Agent (실행 결정)
```

4명의 분석가가 각각 시장 데이터, 소셜 감성, 뉴스, 재무제표를 독립 분석한다. 이 보고서를 바탕으로 강세/약세 리서처가 토론하고, Research Manager가 판결을 내린다. Trader가 투자 계획을 수립하면, 공격적/보수적/중립 3명이 리스크를 토론하고 Risk Judge가 최종 BUY/SELL/HOLD를 결정한다.

여기까지가 12에이전트 파이프라인이며, **포지션 정보 없이 완전 객관적으로** 분석한다. 포지션을 아는 것은 마지막 Portfolio Agent뿐이다. PA는 파이프라인 결정과 과거 경험(RAG)을 종합하여 실제 매매 수량을 결정한다.

Risk Judge는 `strategy_json`으로 확신도(conviction)와 비중(allocation_pct)을 구조화 출력하며, PA가 이를 기반으로 가용 현금 대비 수량을 계산한다.

---

## 어떻게 학습하는가

가상 매매로 분석 결과를 추적하고, 포지션 청산 시 전체 사이클을 되돌아보며 교훈을 추출한다.

**가상 매매**: 티커당 $5,000 독립 자금. 매수/매도 모두 PA가 수량 결정 (소수점 매매 지원). 포지션 전량 청산 시 반성 에이전트가 가동된다.

**반성 에이전트**: 해당 포지션의 전체 분석 리포트 + 매매 이력을 LLM에 전달하여 반성문과 핵심 교훈을 생성한다. 결과는 성공/실패 레이블 + 섹터/산업/시장 메타데이터와 함께 저장된다.

**Hybrid RAG**: 다음 분석에서 PA가 유사 경험을 검색한다. Postgres FTS(키워드)와 ChromaDB(시맨틱)를 RRF Fusion으로 결합하여 가장 관련 높은 과거 교훈을 찾는다. 경험이 있으면 분석 60% + 경험 40% 가중치로 독립 판단하고, 경험이 없으면 파이프라인 결정을 그대로 따른다.

---

## 어떻게 동작하는가

티커별 APScheduler가 주기적으로 분석을 트리거한다. 분석 요청은 asyncio.Queue에 들어가고, 워커 1개가 순차 처리한다 (LLM rate limit 대응). 새 시장 데이터가 없으면 스킵하고, 파싱/에이전트 실패 시 자동으로 1회 재큐잉한다. 서버 재시작 시에는 미완료 스케줄을 자동 복구한다.

분석 중 각 에이전트의 진행 상태는 WebSocket으로 실시간 스트리밍되며, 동시에 DB에 영속화되어 이후 이력 조회가 가능하다.

웹 대시보드는 Svelte SPA로 구현되어 있다. 포지션 현황, 스케줄 관리, 리포트 열람, 실시간 모니터링을 지원하며, 모바일 최적화 다크 테마와 PWA 설치를 제공한다.

---

## 기술 구성

Python 3.10+, FastAPI, LangGraph, APScheduler로 백엔드를 구성하고, Svelte 4 + TypeScript + Vite로 프론트엔드를 구현했다. 데이터는 PostgreSQL 17에 저장하고 ChromaDB로 벡터 검색을 수행한다. LLM은 Google Gemini를 OAuth 인증으로 사용하며 API 키가 필요 없다. 429 시 동일 모델 재시도, 503 시 하위 모델로 자동 폴백한다.

시장 데이터는 yfinance를 기본으로 사용하고 Alpha Vantage로 자동 폴백한다.

---

## 문서

| 문서 | 설명 |
|------|------|
| [spec.md](docs/tradingagents/spec.md) | 요구사항 정의 (FR-001~037) |
| [arch-be.md](docs/tradingagents/arch-be.md) | 백엔드 설계 (DB 스키마, API 명세, 에러 처리) |
| [arch-fe.md](docs/tradingagents/arch-fe.md) | 프론트엔드 설계 (컴포넌트 구조, 상태 관리, 라우팅) |
| [ui.md](docs/tradingagents/ui.md) | UI 명세 (화면별 컴포넌트, 상태, 인터랙션) |

---

<details>
<summary><b>수집 데이터: 15개 기술 지표</b></summary>

LLM에게 15개 지표 목록이 주어지고 상호 보완적인 최대 8개를 자율 선택한다.

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

시가총액, P/E(TTM), Forward P/E, PEG, P/B, EPS(TTM), Forward EPS, 배당수익률, Beta, 52주 고가/저가, 50/200일 평균가, 매출(TTM), 매출총이익, EBITDA, 순이익, 이익률, 영업이익률, ROE, ROA, 부채비율, 유동비율, 장부가치, FCF

</details>

---

## License

[Apache License 2.0](LICENSE)
