# 💡 G-ANT Trader: Evolution Roadmap (Idea Note)

이 문서는 G-ANT Trader의 고도화를 위한 아이디어와 기능 정의를 기록하는 공간입니다.
(Recorded by Deuk-gu, 2026-02-11)

## 1. Parameter Optimization (최적화)
현재 시스템은 티커, 보조지표(MA, Bollinger 등), Lookback Period(회귀 범위)가 고정되어 있거나 하드코딩되어 있음.
- **Goal**: 각 종목(Ticker)별로 가장 잘 맞는 "승리하는 조합(Winning Combination)"을 찾는다.
- **Action**:
    - 지표 종류 및 기간(N일)을 파라미터화.
    - Grid Search 또는 Bayesian Optimization을 통해 최적값 도출 기능 추가.

## 2. Multi-Ticker Batch Analysis (다중 분석)
현재는 단일 티커(Target)만 분석 가능함.
- **Goal**: 관심 종목 리스트(Watchlist)를 한 번에 분석한다.
- **Action**:
    - `tickers = ["AAPL", "TSLA", "NVDA"]` 형태의 입력을 받아 순차적으로(또는 병렬로) Loop.
    - 결과 리포트를 종목별로 폴더링하여 저장.

## 3. Paper Trading & Tracking (가상 매매 및 검증)
이 시스템은 "현재 시점"의 판단이 중요함. 백테스팅보다 "Forward Testing(전진 분석)"이 핵심.
- **Goal**: AI의 조언대로 샀다면 진짜 돈을 벌었을까? 검증한다.
- **Action**:
    - **Signal Logging**: 분석 시점의 날짜, 주가, AI의 판단(BUY/HOLD/SELL), 진입 비중(25%, 50% 등)을 DB(또는 파일)에 기록.
    - **Snapshot Archiving (New)**: 매매 신호 발생 시점의 **차트 이미지(png)**와 **분석 리포트(md)**를 함께 저장. (오답 노트 및 사후 분석용)
    - **Tracking Simulation**: N일/N주 후, 기록된 시점의 판단이 유효했는지 수익률 계산.
    - **Feedback Loop**: 예측 성공률(Hit Rate)을 산출하여 모델 신뢰도 평가.

## 4. User Interface & Accessibility (접근성 강화)
CLI는 불편하고 확장성이 낮음.
- **Goal**: 누구나 쉽고 직관적으로 시스템을 제어하고 결과를 본다.
- **Action**:
    - **Web Dashboard**: 티커/지표/기간 선택 및 결과 시각화 (Streamlit/Next.js).
    - **Discord Bot Interface (New)**:
        - `/analyze AAPL`: 즉시 분석 실행 및 리포트 요약 전송.
        - `/track NVDA`: 관심 종목 등록 및 매일 아침 알림.
        - 모바일 접근성 극대화 및 빠른 개발 속도.

## 5. Deuk-gu Integration (Skill & Sub-agent)
이 시스템은 Python + Gemini CLI 기반이라 득구의 메인 세션과 독립적임.
- **Goal**: 득구가 이 시스템을 "내 손발처럼" 부린다.
- **Action**:
    - **Skill Packaging**: `run_antigravity.py`를 실행하는 득구 전용 스킬(Skill) 생성.
    - **Sub-agent Execution**: 득구가 `sessions_spawn`으로 서브 에이전트를 소환하여 분석을 시키고, 결과만 쏙 빼먹는 구조.
    - **Reasoning**: 득구가 분석 결과를 읽고 "주인님, G-ANT가 사라고 하네요. 근데 뉴스 보니까 좀 불안한데요?"라고 2차 의견 제시.

## 6. Advanced Analytics (심화 분석) - New Ideas
단순 텍스트/차트 분석을 넘어선 고차원 데이터 분석.
- **Sentiment Heatmap (뉴스 감성 히트맵)**:
    - 최근 뉴스 100개를 수집하여 긍정/부정/중립 점수(-1 ~ +1) 산출.
    - 섹터별/종목별 감성 상태를 색상(Heatmap)으로 시각화하여 직관적 판단 보조.
- **Whale Watcher (고래/수급 감시)**:
    - 내부자 거래(Insider Trading) 및 기관 수급 데이터(OpenInsider 등) 연동.
    - 기술적 지표와 수급이 엇갈릴 때(예: 차트는 좋은데 CEO가 매도) 경고 신호 발생.
