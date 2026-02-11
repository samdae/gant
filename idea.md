# 💡 G-ANT Trader: Evolution Roadmap

이 문서는 G-ANT Trader의 고도화를 위한 아이디어와 기능 정의를 기록하는 공간입니다.
(Recorded by Deuk-gu, 2026-02-11)

> ~~Parameter Optimization~~ — 삭제: LLM이 15개 지표 중 최대 8개를 자율 선택 + lookback도 자율 결정. 이미 구현됨.
> ~~Advanced Analytics~~ — 삭제: 감정분석(Sentiment Analyst), 임직원동향(get_insider_transactions) 이미 구현됨.
> ~~Discord Bot~~ — 삭제: OpenClaw이 이미 디스코드 채널 연동됨. 득구 스킬로 동일 기능 가능.

---

## 구현 우선순위

| 순위 | 기능                       | 난이도          | 예상 공수 | 이유                                    |
| ---- | -------------------------- | --------------- | --------- | --------------------------------------- |
| 🥇 1 | Multi-Ticker Batch         | ⭐ 쉬움         | 반나절    | propagate() for loop. 즉시 활용 가능    |
| 🥈 2 | Paper Trading & Tracking   | ⭐⭐⭐ 보통     | 2~3일     | 매매 기록 → 수익률 추적 → Memory 시너지 |
| 🥉 3 | 득구(OpenClaw) Integration | ⭐ 쉬움         | 반나절    | 스킬 파일 1개. 디스코드 연동도 해결     |
| 4    | Web Dashboard              | ⭐⭐⭐⭐ 어려움 | 1주+      | 가장 공수 크지만 최종 목표              |

---

## 1. Multi-Ticker Batch Analysis (다중 분석)

**난이도:** ⭐ 쉬움
**현재:** 단일 티커만 분석 가능
**목표:** 관심 종목 리스트를 한 번에 분석

### Action

- `tickers = ["AAPL", "TSLA", "NVDA"]` 형태의 입력을 받아 순차 Loop
- 결과 리포트를 종목별로 폴더링하여 저장
- 병렬 실행은 API Rate Limit 고려 필요 (2차 목표)

### 핵심 키워드

`for loop`, `propagate()`, `results_dir/{ticker}/{date}/`, `argparse --tickers`

---

## 2. Paper Trading & Tracking (가상 매매 및 검증)

**난이도:** ⭐⭐⭐ 보통
**현재:** 보고서 저장 + Memory 반성 기능은 있으나, 실제 수익률 추적 없음
**목표:** AI 판단대로 샀다면 실제로 벌었는지 검증

### Action

- **Signal Logging**: 날짜, 주가, 판단(BUY/HOLD/SELL), 진입 비중을 DB/파일에 기록
- **Snapshot Archiving**: 매매 신호 시점의 차트 이미지(png) + 분석 리포트(md) 함께 저장
- **Tracking Simulation**: N일/N주 후, 기록된 판단이 유효했는지 수익률 계산
- **Feedback Loop**: Hit Rate 산출 → `reflect_and_remember(returns)` 자동 호출

### 핵심 키워드

`SQLite / JSON ledger`, `yfinance 후속 주가 조회`, `수익률 = (현재가 - 진입가) / 진입가`,
`reflect_and_remember()`, `cron / scheduler`, `matplotlib chart snapshot`

---

## 3. 득구(OpenClaw) Integration

**난이도:** ⭐ 쉬움
**현재:** 독립 실행 스크립트
**목표:** 득구(OpenClaw 에이전트)가 G-ANT를 sub-agent처럼 호출

> 득구 = 로컬 PC에서 상시 실행 중인 OpenClaw 에이전트 봇.
> 스크립트 실행 권한 보유 + 디스코드 채널 연동 완료.

### Action

- **Skill 파일 작성**: `.agent/workflows/analyze.md` — `python main.py AAPL -d 2024-12-01 -n 3` 실행
- **Sub-agent 호출**: 메인 에이전트가 스킬 통해 G-ANT 실행 → `complete_report.md` 수신
- **2차 코멘트**: 득구가 분석 결과를 읽고 사용자에게 추가 의견 제시
- **디스코드 접근**: OpenClaw 디스코드 연동으로 모바일에서도 분석 요청/결과 확인 가능

### 핵심 키워드

`OpenClaw Skill (.md)`, `run_command`, `argparse main.py`,
`complete_report.md 파싱`, `sub-agent pattern`

---

## 4. Web Dashboard

**난이도:** ⭐⭐⭐⭐ 어려움
**현재:** 터미널 출력만 가능
**목표:** 티커/지표/기간 선택 + 결과 시각화 + 실시간 에이전트 상태

### Action

- **Backend**: FastAPI + WebSocket (에이전트 진행 상태 실시간 스트리밍)
- **Frontend**: Next.js 또는 Streamlit
- **차트**: TradingView Lightweight Charts 또는 Plotly

### 핵심 키워드

`FastAPI`, `WebSocket`, `SSE (Server-Sent Events)`, `Next.js / Streamlit`,
`TradingView widget`, `Plotly`, `real-time agent status`, `docker-compose`
