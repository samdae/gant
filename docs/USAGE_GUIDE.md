# 🐜 G-ANT Trader 사용 가이드

G-ANT Trader(TradingAgents Mod)를 사용하여 주식 시장을 분석하고 매매 전략을 수립하는 방법을 안내합니다.

## 1. 개요
이 시스템은 여러 AI 에이전트(Analyst, Researcher, Trader, Risk Manager)가 협업하여 최적의 투자의사결정을 내리는 프레임워크입니다.
**Antigravity (Gemini 3 Pro)** 엔진을 사용하여 고성능 추론을 무료로 수행합니다.

## 2. 실행 환경 준비
터미널에서 가상환경을 활성화하고 프로젝트 루트(모노레포)로 이동하십시오.

```bash
cd ~/.openclaw/workspace/TradingAgents/monorepo
# 가상환경 활성화 (필요시)
source venv/bin/activate
```

## 3. 실행 방법

### 3.1. 로컬 분석 실행

```bash
python main.py
```

### 3.2. API 서버 실행

```bash
scripts/run_api.sh
```

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

*지표 추가 방법*: `packages/tradingagents/agents/analysts/market_analyst.py`의 프롬프트에서 원하는 지표를 요청하도록 수정하십시오.

## 5. 결과 확인
분석이 완료되면 다음 경로에 리포트가 저장됩니다.
- 경로: `reports/{TICKER}_{TIMESTAMP}/complete_report.md`
- 내용:
    - **Analyst Reports**: 각 분야별 상세 분석.
    - **Debate Logs**: 에이전트 간의 매수/매도 토론 내역.
    - **Final Decision**: 최종 매매 의견 (BUY/HOLD/SELL), 비중, 진입가, 손절가.

---
*Created by Deuk-gu & Master DH*
