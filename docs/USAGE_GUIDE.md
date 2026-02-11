# 🐜 G-ANT Trader 사용 가이드

G-ANT Trader(TradingAgents Mod)를 사용하여 주식 시장을 분석하고 매매 전략을 수립하는 방법을 안내합니다.

## 1. 개요
이 시스템은 여러 AI 에이전트(Analyst, Researcher, Trader, Risk Manager)가 협업하여 최적의 투자의사결정을 내리는 프레임워크입니다.
**Antigravity (Gemini 3 Pro)** 엔진을 사용하여 고성능 추론을 무료로 수행합니다.

## 2. 실행 환경 준비
터미널에서 가상환경을 활성화하고 프로젝트 루트로 이동하십시오.

```bash
cd ~/.openclaw/workspace/TradingAgents
# 가상환경 활성화 (필요시)
source venv/bin/activate 
```

## 3. 실행 방법 (CLI Mode)
TUI(Text User Interface)를 통해 대화형으로 설정을 입력하고 실행합니다.

```bash
python cli/main.py analyze
```

### 3.1. 단계별 입력 가이드

1.  **Ticker Symbol**: 분석할 종목 코드를 입력합니다. (예: `AAPL`, `TSLA`, `NVDA`)
2.  **Analysis Date**: 분석 기준일을 입력합니다. (예: `2026-02-10`)
    - *Tip*: 과거 날짜를 입력하면 그 시점의 데이터로 분석합니다.
3.  **Analysts Team**: 참여할 애널리스트를 선택합니다. (Space로 선택)
    - `Market Analyst`: 차트 및 기술적 분석 (필수)
    - `Social Analyst`: 소셜 미디어 여론 분석
    - `News Analyst`: 뉴스 기사 분석 (필수)
    - `Fundamentals Analyst`: 재무제표 분석 (가치투자 시 필수)
4.  **Research Depth**: 분석 및 토론의 깊이를 선택합니다.
    - `1 (Shallow)`: 빠른 분석.
    - `3 (Medium)`: 균형 잡힌 분석.
    - `5 (Deep)`: 심층 토론. (시간이 오래 걸림)
5.  **LLM Provider**: **`Google`**을 선택하십시오.
    - *Note*: 코드 내부에서 `Google` 선택 시 자동으로 `Antigravity` 엔진(Internal API)으로 라우팅되도록 설정되어 있습니다.
6.  **Thinking Mode**: `Enable Thinking (recommended)` 선택.
7.  **Models**:
    - **Deep-Thinker**: `gemini-3-pro` (또는 `gemini-2.5-pro`)
    - **Quick-Thinker**: `gemini-3-flash` (또는 `gemini-2.5-flash`)

## 4. 보조지표 (Technical Indicators) 설정
이 시스템은 `stockstats` 라이브러리를 사용하여 다양한 기술적 지표를 계산합니다.
에이전트는 기본적으로 다음 지표들을 활용하지만, 프롬프트 변경을 통해 추가할 수 있습니다.

### 주요 지원 지표
- **이동평균선 (MA)**:
    - `close_50_sma` (50일 단순이평): 중기 추세
    - `close_200_sma` (200일 단순이평): 장기 추세
    - `close_20_ema` (20일 지수이평): 단기 추세
- **모멘텀**:
    - `rsi` (Relative Strength Index): 과매수/과매도 판단 (14일 기준)
    - `macd`: 추세 전환 신호
- **변동성**:
    - `boll` (Bollinger Bands): 상단(`boll_ub`) / 하단(`boll_lb`) 밴드
    - `atr` (Average True Range): 변동성 크기
- **거래량**:
    - `vwma` (Volume Weighted Moving Average): 거래량 가중 이평선

*지표 추가 방법*: `tradingagents/agents/analysts/market_analyst.py`의 프롬프트에서 원하는 지표를 요청하도록 수정하십시오.

## 5. 결과 확인
분석이 완료되면 다음 경로에 리포트가 저장됩니다.
- 경로: `reports/{TICKER}_{TIMESTAMP}/complete_report.md`
- 내용:
    - **Analyst Reports**: 각 분야별 상세 분석.
    - **Debate Logs**: 에이전트 간의 매수/매도 토론 내역.
    - **Final Decision**: 최종 매매 의견 (BUY/HOLD/SELL), 비중, 진입가, 손절가.

---
*Created by Deuk-gu & Master DH*
