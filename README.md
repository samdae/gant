# 🐜 G-ANT Trader (TradingAgents Mod)

**"개미는 뚠뚠, 오늘도 뚠뚠... 하지만 스마트하게!"**

이 프로젝트는 [TradingAgents](https://github.com/virattt/TradingAgents)를 기반으로, **Google Antigravity (Gemini 3 Pro)** 엔진을 탑재하여 무제한/고성능 추론이 가능하도록 개조한 버전입니다.

## 🚀 Key Features

- **Antigravity Engine**: Google Cloud Code 내부 API를 활용한 `gemini-3-pro` / `gemini-2.5-pro` 모델 사용. (무료, 고성능)
- **Hybrid Auth**: `gemini-cli` 인증과 Python Native Request를 결합한 하이브리드 인증 방식.
- **Probe Mode**: API 엔드포인트와 Payload 형식을 자동으로 탐색하여 최적의 경로로 통신.
- **Strategic Debate**: Analyst, Risk Manager, Trader 에이전트 간의 치열한 토론을 통한 의사결정.

## 🛠 Usage

### 1. Prerequisites
- Python 3.10+
- `gemini-cli` installed & authenticated (for token generation)
  ```bash
  npm install -g @google/gemini-cli
  gemini login
  ```

### 2. Install
```bash
pip install -r requirements.txt
```

### 3. Run
```bash
python run_antigravity.py
```

## ⚠️ Disclaimer
이 소프트웨어는 교육 및 연구 목적으로만 제공됩니다. 실제 투자에 대한 책임은 전적으로 사용자에게 있습니다.
**Antigravity API 사용은 Google의 정책에 따라 제한될 수 있습니다.**

---
*Maintained by DH & Deuk-gu*
