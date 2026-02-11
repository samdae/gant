# 🐜 G-ANT Trader

**"개미는 뚠뚠, 오늘도 뚠뚠... 하지만 스마트하게!"**

[TradingAgents](https://github.com/virattt/TradingAgents) 프레임워크를 기반으로, Google Antigravity 엔진(Gemini 3 Pro / Gemini 2.5 Pro)을 탑재한 무료 AI 주식 분석 시스템입니다. 여러 전문 에이전트가 토론과 리스크 분석을 거쳐 매수/매도/관망 판단을 내립니다.

---

## 아키텍처

### 멀티 에이전트 시스템

이 시스템은 하나의 AI가 아닌 **역할이 다른 여러 에이전트**의 협업으로 의사결정을 내립니다.

| 역할             | 에이전트                              | 설명                                                   |
| ---------------- | ------------------------------------- | ------------------------------------------------------ |
| **Analyst**      | Market / Social / News / Fundamentals | 각각 시장 데이터, 소셜 센티먼트, 뉴스, 재무제표를 분석 |
| **Researcher**   | Bull / Bear                           | 낙관/비관 시나리오를 각각 옹호하며 토론                |
| **Risk Manager** | Risk Analyst                          | 포지션 리스크, 변동성, 최대 손실을 평가                |
| **Trader**       | Portfolio Trader                      | 최종 매수/매도/관망 판단과 비중 결정                   |

### 분석 흐름

```
[데이터 수집] → [4종 Analyst 보고서] → [Bull vs Bear 토론]
      → [Risk Manager 평가] → [Trader 최종 판단] → [결과 리포트]
```

토론 라운드 수는 `max_debate_rounds`와 `max_risk_discuss_rounds`로 조절됩니다 (기본: 1라운드).

### 데이터 소스

시장 데이터는 **yfinance**를 기본 데이터 벤더로 사용합니다. Alpha Vantage로 전환하려면 `ALPHA_VANTAGE_API_KEY` 환경변수 설정 후 config의 `data_vendors`를 수정하면 됩니다.

수집 데이터:

- 주가/거래량/기술 지표 (SMA, RSI, MACD 등)
- 재무제표 (손익계산서, 대차대조표, 현금흐름표)
- 내부자 거래 내역
- 뉴스 헤드라인 및 글로벌 뉴스

---

## LLM Provider

API 키 없이 **Google OAuth 인증만으로** Gemini 모델을 사용합니다. 두 가지 provider를 지원합니다.

| Provider            | 모델                       | 인증 파일                    | 특징                     |
| ------------------- | -------------------------- | ---------------------------- | ------------------------ |
| `gemini-cli` (기본) | gemini-2.5-pro, 2.5-flash  | `~/.gemini/oauth_creds.json` | Gemini CLI의 토큰 재사용 |
| `antigravity`       | gemini-3-pro-high, 3-flash | `~/.antigravity_tokens.json` | 자체 OAuth 플로우        |

### 모델 매핑

`gemini-cli` provider 사용 시, config의 모델명은 자동으로 매핑됩니다:

| Config 모델명       | 실제 호출 모델     |
| ------------------- | ------------------ |
| `gemini-3-flash`    | `gemini-2.5-flash` |
| `gemini-3-pro`      | `gemini-2.5-pro`   |
| `gemini-3-pro-high` | `gemini-2.5-pro`   |

### 인증 방식

1. **Refresh Token** (env 변수): `GEMINI_CLI_REFRESH_TOKEN` 또는 `ANTIGRAVITY_REFRESH_TOKEN` 설정 시 자동 토큰 갱신. CI/headless 환경에 적합.
2. **캐시 파일**: 이전 인증에서 저장된 토큰 파일을 자동 로드. 토큰 만료 시 refresh token으로 갱신.
3. **브라우저 OAuth**: 위 두 방법이 모두 실패하면 브라우저가 열려 Google 로그인을 요청합니다.

우선순위: **env 변수 → 캐시 파일 → 브라우저 인증**

### Resilience

API 호출 실패 시 자동 복구:

- **429 (Rate Limit)**: 30초 대기 후 동일 모델로 재시도 (최대 5회)
- **503 (Capacity)**: 폴백 모델로 자동 전환 (`2.5-pro → 2.5-flash`, `3-pro-high → 3-pro-low → 3-flash`)

---

## 설치 및 실행

### Prerequisites

- Python 3.10+
- (선택) `gemini-cli` 설치 및 인증:
  ```bash
  npm install -g @google/gemini-cli
  gemini   # 최초 실행 시 브라우저 인증
  ```

### Install

```bash
git clone https://github.com/samdae/g-ant-trader.git
cd g-ant-trader
pip install -r requirements.txt
```

### Run

```bash
python main.py
```

`main.py`에서 종목, 날짜, 모델 등을 직접 설정합니다. 기본 설정은 `default_config.py`에서 읽고, `.env`로 override할 수 있습니다.

CLI wizard를 사용하려면 `python -m cli.main` 또는 `tradingagents` 명령을 실행하세요. wizard는 6단계로 분석을 설정합니다:

1. **종목 선택** — 티커 심볼 입력 (예: AAPL, TSLA)
2. **분석 날짜** — 분석 기준일 선택
3. **애널리스트 팀** — market, social, news, fundamentals 중 선택
4. **리서치 깊이** — 토론 라운드 수 결정
5. **LLM Provider** — gemini-cli 또는 antigravity 선택
6. **모델 선택** — shallow/deep thinking 모델 지정

### 환경변수 설정

`.env` 파일로 기본값을 설정할 수 있습니다 (`.env.example` 참고):

```env
# Provider 기본값 (CLI wizard에서도 변경 가능)
LLM_PROVIDER=gemini-cli

# Headless 인증용 Refresh Token (선택)
GEMINI_CLI_REFRESH_TOKEN=<your-token>
ANTIGRAVITY_REFRESH_TOKEN=<your-token>

# Alpha Vantage (yfinance 대신 사용 시)
ALPHA_VANTAGE_API_KEY=<your-key>
```

---

## 주요 설정 (default_config.py)

| 키                        | 기본값                             | 설명                          |
| ------------------------- | ---------------------------------- | ----------------------------- |
| `llm_provider`            | `gemini-cli` (env: `LLM_PROVIDER`) | LLM provider 선택             |
| `deep_think_llm`          | `gemini-3-pro-high`                | 심층 분석용 모델              |
| `quick_think_llm`         | `gemini-3-flash`                   | 빠른 판단용 모델              |
| `max_debate_rounds`       | 1                                  | Bull vs Bear 토론 라운드 수   |
| `max_risk_discuss_rounds` | 1                                  | 리스크 논의 라운드 수         |
| `data_vendors`            | 모두 `yfinance`                    | 데이터 소스 벤더 (카테고리별) |

---

## ⚠️ Disclaimer

이 소프트웨어는 교육 및 연구 목적으로만 제공됩니다. 실제 투자에 대한 책임은 전적으로 사용자에게 있습니다.
**Antigravity API 사용은 Google의 정책에 따라 제한될 수 있습니다.**

---

_Maintained by DH & Deuk-gu_
