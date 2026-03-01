# UI Specification: TradingAgents (GANT)

> Created: 2026-02-13
> Updated: 2026-03-01 (코드 동기화 — About 화면, 회고분석 라우트/요청 플로우, 하단 5탭 네비)
> Service: tradingagents
> Platform: responsive
> Requirements: docs/tradingagents/spec.md
> Backend API: docs/tradingagents/arch-be.md

## 0. Responsive Strategy

```yaml
platform: "responsive"
breakpoints:
  mobile: "< 640px"
  tablet: "640-1024px"
  desktop: "> 1024px"
approach: "Mobile First"
```

---

## 1. Screen List

| #   | Screen          | Route                | Related Endpoints                                                                                              | Auth Required    | Spec Reference         |
| --- | --------------- | -------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------- | ---------------------- |
| 1   | Dashboard       | `/`                  | `GET /health`, `GET /queue`, `GET /positions/market`, `GET /metrics`, `GET /schedules/summary`              | No               | FR-025, FR-034, FR-040, FR-045 |
| 2   | Positions       | `/positions`         | `GET /positions/market`, `GET /positions/closed`, `GET /metrics`                                              | No               | FR-013, FR-025, FR-034, FR-046 |
| 3   | Schedules       | `/schedules`         | `GET /schedules`, `GET /queue`, `GET /schedules/{ticker}/cycles`, `GET /search/tickers`, `POST /schedules`, `DELETE /schedules/{ticker}` | POST/DELETE: Yes | FR-016, FR-025, FR-026 |
| 4   | Schedule Detail | `/schedules/:ticker` | `GET /schedules/{ticker}/cycles`, `GET /schedules/{ticker}/cycles/{id}/events`                               | No               | FR-025, FR-037         |
| 5   | Trade Detail    | `/trade/:ticker`     | `GET /positions?status=`, `GET /positions/{id}`, `GET /positions/market`, `GET /reports?ticker=`, `GET /position/{id}/graph` | No | FR-013, FR-014, FR-020, FR-034, FR-048 |
| 6   | Reports         | `/reports`           | `GET /reports/tickers`                                                                                         | No               | FR-025, FR-032         |
| 7   | Report Detail   | `/reports/:ticker`   | `GET /reports?ticker=`                                                                                         | No               | FR-025, FR-032         |
| 8   | Reflections     | `/reflections`       | `GET /reflections`                                                                                             | No               | FR-049                 |
| 9   | Retrospective   | `/retrospective`     | `GET /retrospective/summary`, `GET /retrospective/tickers`, `GET /retrospective/positions/{ticker}`, `POST /retrospective/analyze` | No | FR-055 |
| 10  | Retro Detail    | `/retrospective/:ticker` | `GET /retrospective/detail/{ticker}`                                                                      | No               | FR-055                 |
| 11  | Live Analysis   | `/live`              | `WS /ws/analyze/{ticker}`, `GET /queue`, `GET /live/{ticker}/events`                                          | No               | FR-025, FR-037         |
| 12  | About           | `/about`             | —                                                                                                              | No               | FR-035                 |
| 13  | Auth            | `/auth`              | —                                                                                                              | No               | FR-026                 |
| 14  | Not Found       | `*`                  | —                                                                                                              | No               | —                      |

---

## 2. Screen Specifications

### 2.1 Dashboard (`/`)

**Purpose**: 시스템 상태, 핵심 KPI, 오늘 실행 요약, 활성 포지션, 큐 상태를 한 화면에 요약.

**Mobile**:

```
┌─────────────────────────────────┐
│ 홈   [ALL▾KRW|USD] [● 온라인·대기]│
├─────────────────────────────────┤
│ ┌─ 오늘 실행 ──────────── 12 ─┐ │
│ │ 완료 8  건너뜀 2  실패 1  1 │ │
│ └─────────────────────────────┘ │
│ ┌─ 총손익 ────┬─ 투자 ────────┐ │
│ │ 실현 +$200  │ 4             │ │
│ │ 미실현+$223 │ 승 3 · 패 1  │ │
│ │ 합계 +$423  │               │ │
│ │ 수익률+8.5% │               │ │
│ └─────────────┴───────────────┘ │
│ ※ ALL 선택 시 퍼센트만 표시     │
│ ┌─ 내 투자 ──────── 전체 보기 ┐ │
│ │ NVDA 엔비디아    $1,250(+$50)│ │
│ │ AAPL 애플        $890 (-$12)│ │
│ └─────────────────────────────┘ │
│ ┌─ 대기열 ──── 실시간 보기 ───┐ │
│ │ ● TSLA         실행중       │ │
│ │ ○ MSFT         대기중       │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 예약 실시간 [홈] 투자 AI분석     │
└─────────────────────────────────┘
```

**Desktop (> 1024px)**:

```
┌──────────────────────────────────────────────────────────────┐
│ [ALL▾KRW|USD]                                  about           │
├──────────────────────────────────────────────────────────────┤
│ 홈                                        [● 온라인·대기]    │
│                                                              │
│ ┌─ 오늘 실행 ───────────────────────────────────────── 12 ─┐ │
│ │   완료 8       건너뜀 2       실패 1       실행중 1      │ │
│ └──────────────────────────────────────────────────────────┘ │
│ ┌─ 총손익 ──────────────┬─ 투자 ──────────────────────────┐ │
│ │ +$423.50  수익률+8.5% │ 4 투자  ·  승 3 · 패 1         │ │
│ └───────────────────────┴─────────────────────────────────┘ │
│                                                              │
│ ┌─ 내 투자 ─── 전체보기 ─┐  ┌─ 대기열 ─── 실시간보기 ────┐ │
│ │ NVDA  $1,250 (+$50)    │  │ ● TSLA        실행중       │ │
│ │ AAPL  $890   (-$12)    │  │ ○ MSFT        대기중       │ │
│ │                        │  │                            │ │
│ │                        │  │                            │ │
│ │                        │  │                            │ │
│ └────────────────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**States**: loading / error (오프라인 배지) / loaded

**API Calls**: `fetchMetrics`, `fetchPositionsMarket`, `fetchQueue`, `fetchHealth`, `fetchScheduleSummary`

---

### 2.2 Positions (`/positions`) — FR-046

**Purpose**: 활성/종료 포지션 표시. active/closed 탭 분리. 클릭 시 Trade Detail로 이동.

**Mobile (카드 리스트)**:

```
┌─────────────────────────────────┐
│ 투자                 손익 +$423 │
│ [활성 포지션]  [이전 투자]       │
├─────────────────────────────────┤
│ === 활성 포지션 탭 ===          │
│ ┌───────────────────────────┐   │
│ │ NVDA 엔비디아     +4.12%  │   │
│ │ 보유 10 · 1주 평균 $125   │   │
│ │ 총 금액 $1,250 (+$50.00) │   │
│ └───────────────────────────┘   │
│                                 │
│ === 이전 투자 탭 ===            │
│ ┌───────────────────────────┐   │
│ │ GOOGL 구글   ✅ 승 +2.34% │   │
│ │ 보유기간 15일 · 수익 $117  │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ TSLA 테슬라  ❌ 패 -5.12% │   │
│ │ 보유기간 8일 · 손실 -$256  │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
```

**Desktop (테이블)**:

```
┌──────────────────────────────────────────────────────────────┐
│ 투자                                          손익 +$423.50  │
├──────────┬──────┬──────────┬───────────────┬─────────────────┤
│ 티커     │ 보유 │ 1주 평균 │ 총 금액       │ 수익률          │
├──────────┼──────┼──────────┼───────────────┼─────────────────┤
│ NVDA     │ 10   │ $125.00  │ $1,250(+$50)  │ +4.12%          │
│ AAPL     │ 5    │ $180.00  │ $890 (-$12)   │ -1.33%          │
└──────────┴──────┴──────────┴───────────────┴─────────────────┘
```

**States**: loading / error / empty ("투자가 없습니다." / "이전 투자가 없습니다.") / loaded

**API Calls**: `fetchPositionsMarket`, `fetchPositionsClosed` (`GET /positions/closed`), `fetchMetrics`

**Interactions**: 행/카드 클릭 → `/#/trade/{ticker}`. 탭 전환으로 active/closed 목록 전환

**Closed 포지션 표시 항목**: 티커, 승패(win/loss), 수익률(return_pct), 보유기간(opened_at~closed_at), 실현 손익 금액

---

### 2.3 Schedules (`/schedules`)

**Purpose**: 분석 스케줄 CRUD. 티커 추가/삭제 + 상태(실행중/대기중/활성) 표시.

**Mobile**:

```
┌─────────────────────────────────┐
│ 예약                    [+ 추가]│
├─────────────────────────────────┤
│ ┌───────────────────────────┐   │
│ │ NVDA 엔비디아    [실행중] │   │
│ │ 매일 · 2/26 07:00 예정    │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ AAPL 애플        [활성]   │   │
│ │ 매일 · 2/26 07:00 예정    │   │
│ │         ← 스와이프로 삭제 │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ TSLA             [대기중] │   │
│ │ 매일 · 2/26 07:00 예정    │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘

┌─ 예약 추가 모달 ───────────────┐
│                            [×] │
│ 티커                           │
│ ┌─────────────────────────────┐│
│ │ NVDA                        ││
│ ├─────────────────────────────┤│
│ │ NVDA  NVIDIA Corp    NASDAQ ││
│ │ NVD   Invesco QQQ    ARCA  ││
│ └─────────────────────────────┘│
│ 표시 이름                      │
│ [NVIDIA                      ] │
│ 주기 (일)                      │
│ [1                           ] │
│                                │
│              [취소]   [생성]    │
└────────────────────────────────┘
```

**States**: loading / error / empty / loaded / submitting (버튼 disabled)

**API Calls**: `fetchSchedules`, `fetchQueue`, `fetchScheduleCycles`, `searchTickers`, `createSchedule`, `deleteSchedule`

**특이사항**:
- 티커 입력 시 Yahoo Finance 자동완성 (`GET /search/tickers`, 250ms debounce)
- 선택 시 display_name 자동 채움
- 스와이프 삭제 (touchstart/touchmove/touchend, threshold -80px)

---

### 2.4 Schedule Detail (`/schedules/:ticker`)

**Purpose**: 특정 티커의 분석 사이클 이력과 에이전트별 이벤트 타임라인 표시.

```
┌─────────────────────────────────┐
│ ← NVDA 엔비디아                 │
├─────────────────────────────────┤
│ [▼ 12회차 · 2026-02-20       ] │
├─────────────────────────────────┤
│ 분석                            │
│  09:31 시장 분석 에이전트    ✓  │
│  09:32 소셜분석 에이전트     ✓  │
│  09:33 뉴스 분석 에이전트    ✓  │
│  09:35 펀더멘털 분석 에이전트 ✓ │
│ 투자 토론                       │
│  09:36 강세 분석 에이전트    ✓  │
│  09:37 약세 분석 에이전트    ✓  │
│  09:38 심판 결론 에이전트    ✓  │
│ 매매 결정                       │
│  09:39 트레이더 결정 에이전트 ✓ │
│ 리스크 토론                     │
│  09:40 공격적 분석 에이전트  ●  │  ← running
│  —    중립적 분석 에이전트   ○  │  ← pending
│  —    보수적 분석 에이전트   ○  │
│  —    리스크 결론 에이전트   ○  │
│ 실행                            │
│  —    포트폴리오 에이전트    ○  │
└─────────────────────────────────┘
```

**States**: loading / error / empty / loaded / loadingEvents

**API Calls**: `fetchScheduleCycles(ticker, 10)`, `fetchScheduleCycleEvents(ticker, scheduleId)`

---

### 2.5 Trade Detail (`/trade/:ticker`)

**Purpose**: 특정 티커의 포지션 상태, OHLC 차트, 최신 리포트, 매매 이력 표시.

```
┌─────────────────────────────────┐
│ ← NVDA 엔비디아        [+4.12%]│
├─────────────────────────────────┤
│ ┌─ 포지션 요약 ───────────────┐ │
│ │ 보유 10주  평균가 $125.00   │ │
│ │ 현재가 $130.12              │ │
│ │ 총 금액 $1,301 (+$51.20)   │ │
│ └─────────────────────────────┘ │
│ ┌─ OHLC 차트 (SVG) ──────────┐ │
│ │    ╻                        │ │
│ │   ┃╻  ╻                    │ │
│ │  ╻┃┃ ┃╻  ╻                 │ │
│ │  ┃┃┃ ┃┃ ┃┃╻  ▲BUY         │ │
│ │ ─┃┃──┃┃─┃┃┃──── avg $125  │ │
│ │  ┃   ┃  ┃┃┃               │ │
│ │  ╹   ╹  ╹╹╹               │ │
│ │ ▁▂▃▁▂▅▂▁▃▂  (volume)      │ │
│ │ 2/10        2/20   [🔍±]  │ │
│ └─────────────────────────────┘ │
│ [리포트]  [매매 이력]           │
├─────────────────────────────────┤
│ ┌─ 리포트 ────────────────────┐ │
│ │ [▼ 12회차 · 2026-02-20   ] │ │
│ │                             │ │
│ │ 결정: 매수  PA: BUY 5주    │ │
│ │                             │ │
│ │ ## 최종 매매 결정           │ │
│ │ 시장 모멘텀이 강하고...    │ │
│ │                             │ │
│ │ ## 투자 계획               │ │
│ │ 현재 가격대에서 추가...    │ │
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

**States**: loading / error / notFound / loaded

**API Calls**: `fetchPositions`, `fetchPositionsMarket`, `fetchPositionDetail(id)`, `fetchReportsByTicker(ticker)`, `fetchPositionGraph(id, days)`

**특이사항**:
- `marked` + `DOMPurify`로 마크다운 → 안전한 HTML 변환
- SVG 기반 OHLC 차트 직접 구현 (외부 차팅 라이브러리 없음). 캔들/라인 모드 전환, 핀치 줌, 크로스헤어 지원
- 30초 간격 자동 새로고침 (setInterval)

---

### 2.6 Reports (`/reports`)

**Purpose**: 티커별 AI 분석 리포트 요약 목록. 클릭 시 상세 리포트로 이동.

```
┌─────────────────────────────────┐
│ AI분석                          │
├─────────────────────────────────┤
│ ┌───────────────────────────┐   │
│ │ NVDA 엔비디아     [매수]  │   │
│ │ 12회 분석 · 최근 2/20     │   │
│ │ PA: BUY 5주               │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ AAPL 애플         [관망]  │   │
│ │ 8회 분석 · 최근 2/19      │   │
│ │ PA: HOLD                  │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ TSLA              [매도]  │   │
│ │ 3회 분석 · 최근 2/18      │   │
│ │ PA: SELL 전량             │   │
│ └───────────────────────────┘   │
└─────────────────────────────────┘
```

**States**: loading / error / empty / loaded

**API Calls**: `fetchReportTickers`

**특이사항**: 결정 추출 로직 (BUY/SELL/HOLD, 한국어 매수/매도/관망 인식)

---

### 2.7 Report Detail (`/reports/:ticker`)

**Purpose**: 특정 티커의 분석 리포트 상세 (7그룹 아코디언).

```
┌─────────────────────────────────┐
│ ← NVDA 엔비디아                 │
├─────────────────────────────────┤
│ [▼ 12회차 · 2026-02-20       ] │
│                                 │
│ 결정: [매수]  PA: BUY 5주      │
├─────────────────────────────────┤
│ ▼ 분석                          │
│ ├─ 시장 분석                    │
│ │  RSI 65로 과매수 구간에      │
│ │  근접하나 상승 추세 유지...  │
│ ├─ 펀더멘털 분석                │
│ │  매출 YoY +25%, 영업이익...  │
│                                 │
│ ▶ 투자 토론                     │
│   (심판 결론 + 강세/약세 분석)  │
│                                 │
│ ▶ 투자 계획                     │
│                                 │
│ ▶ 매매 결정                     │
│                                 │
│ ▶ 리스크 토론                   │
│   (리스크 결론 + 공격/보수/중립)│
│                                 │
│ ▶ 최종 결정                     │
│                                 │
│ ▶ 트레이더 의견                 │
└─────────────────────────────────┘
```

> ▶ = 접힌 상태 (클릭하면 펼침), ▼ = 펼친 상태

**States**: loading / error / empty / loaded

**API Calls**: `fetchReportsByTicker(ticker, limit)`

**특이사항**: 마크다운 렌더링 (marked + DOMPurify), 각 섹션 접기/펼치기

---

### 2.8 Reflections (`/reflections`) — FR-049

**Purpose**: AI 에이전트의 회고/반성 목록. 포지션 종료 후 생성된 반성문과 핵심 교훈 확인.

**Mobile**:

```
┌─────────────────────────────────┐
│ 회고                             │
│ [전체]  [✅ 성공]  [❌ 실패]     │
├─────────────────────────────────┤
│ ┌───────────────────────────┐   │
│ │ NVDA 엔비디아  ✅ +12.34% │   │
│ │ 2026-02-18 · 보유 15일    │   │
│ │                           │   │
│ │ ## 핵심 교훈              │   │
│ │ AI 반도체 수요 증가 추세  │   │
│ │ 에서 모멘텀 진입이 효과적 │   │
│ │ 이었으나, 과매수 구간에서 │   │
│ │ 부분 익절이 필요했다...   │   │
│ │                    [더보기]│   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ TSLA 테슬라   ❌ -5.12%   │   │
│ │ 2026-02-15 · 보유 8일     │   │
│ │                           │   │
│ │ ## 핵심 교훈              │   │
│ │ 실적 발표 직전 진입은     │   │
│ │ 리스크가 높았다. 이벤트   │   │
│ │ 전 보수적 접근 필요...    │   │
│ │                    [더보기]│   │
│ └───────────────────────────┘   │
│          [더 불러오기]           │
└─────────────────────────────────┘
```

**States**: loading / error / empty ("회고가 없습니다.") / loaded

**API Calls**: `fetchReflections(?outcome=win|loss, ?cursor, ?limit)`

**표시 항목**: ticker, outcome(win/loss), return_pct, market/sector/industry, key_lessons (요약), reflection (전체, 마크다운), created_at

**특이사항**:
- win/loss 필터 (백엔드 `outcome` 파라미터 활용) — 전환 시 목록+cursor 초기화
- cursor 기반 페이지네이션 (백엔드 이미 지원)
- 마크다운 렌더링 (marked + DOMPurify)
- 카드 클릭 시 전체 반성문 펼치기/접기

---

### 2.9 Retrospective (`/retrospective`) — FR-055

**Purpose**: 티커별 회고분석 완료 현황 확인 + 회고분석 요청(선택 티커/전체 티커).

**States**: loading / error / empty / loaded / modal(open) / analyzing

**API Calls**:
- `fetchRetroSummary()`
- `fetchRetroTickers()`
- `fetchRetroPositions(ticker)`
- `requestRetroAnalysis({ mode: "ticker" | "all", position_ids? })`

**특이사항**:
- 상단 `AnalysisTabs` 우측 action 슬롯에 "요청" 버튼 배치
- 모달에서 티커 선택 시 포지션별 분석 상태(`분석미완료`, `분석중`, `완료(open|closed)`, `실패`) 표시
- `completed + closed`는 재요청 비활성화, `completed + open`/`failed`는 재요청 허용

---

### 2.10 Retro Detail (`/retrospective/:ticker`) — FR-055

**Purpose**: 특정 티커의 완료된 회고분석 결과 상세(회차 선택 + 마크다운 본문).

**States**: loading / error / empty / loaded

**API Calls**: `fetchRetroByTicker(ticker)`

**특이사항**:
- 결과 목록에서 `status === "completed"`만 표시
- `SelectMenu`로 회차 선택 시 해당 분석 본문 즉시 교체
- 상단 뒤로가기 링크 `#/retrospective`

---

### 2.11 Live Analysis (`/live`)

**Purpose**: WebSocket으로 에이전트 실행 상태를 실시간 스트리밍.

```
┌─────────────────────────────────────────────────────────┐
│ 실시간                                                   │
├──────────────────┬──────────────────────────────────────┤
│ 대기열           │ 에이전트 파이프라인    ● NVDA · 실시간│
│                  │                                      │
│ ● NVDA  실행중   │ 최근: 공격적 분석 에이전트 · running │
│ ○ MSFT  대기중   │                                      │
│                  │ 분석                                  │
│                  │  09:31 시장 분석 에이전트          ✓  │
│                  │  09:32 소셜분석 에이전트           ✓  │
│                  │  09:33 뉴스 분석 에이전트          ✓  │
│                  │  09:35 펀더멘털 분석 에이전트      ✓  │
│                  │ 투자 토론                             │
│                  │  09:36 강세 분석 에이전트          ✓  │
│                  │  09:37 약세 분석 에이전트          ✓  │
│                  │  09:38 심판 결론 에이전트          ✓  │
│                  │ 매매 결정                             │
│                  │  09:39 트레이더 결정 에이전트      ✓  │
│                  │ 리스크 토론                           │
│                  │  09:40 공격적 분석 에이전트        ●  │
│                  │  —    중립적 분석 에이전트         ○  │
│                  │  —    보수적 분석 에이전트         ○  │
│                  │  —    리스크 결론 에이전트         ○  │
│                  │ 실행                                  │
│                  │  —    포트폴리오 에이전트          ○  │
└──────────────────┴──────────────────────────────────────┘

(모바일에서는 대기열이 상단, 파이프라인이 하단으로 세로 배치)
```

**States**: loading / idle ("대기 중") / connected (WS live) / disconnected

**API Calls**: `fetchQueue`, `fetchLiveEvents(ticker)`, `WS /ws/analyze/{ticker}`

**특이사항**:
- onMount 시 `fetchQueue` 1회 호출, running ticker 있으면 자동 WS 연결
- `fetchLiveEvents(ticker)` → DB 기존 이벤트 로드 → `seedEvents`로 stepStates 초기화
- WS 실시간 이벤트와 병합 (messages 최대 20개 유지)
- 5단계 phase 그룹: 분석 / 투자 토론 / 매매 결정 / 리스크 토론 / 실행
- 13개 에이전트별 한국어 라벨 (시장 분석 에이전트, 강세 분석 에이전트 등)

---

### 2.12 About (`/about`)

**Purpose**: 서비스 목적/모드 구분/학습 사이클/RAG 개념을 설명하는 정적 안내 페이지.

**States**: loaded (정적 콘텐츠)

**API Calls**: 없음

**특이사항**:
- AppHeader 우측 `about` 링크로 접근
- 분석검증 모드 vs 포트폴리오 모드 차이 및 용어 설명 제공

---

### 2.13 Auth (`/auth`)

**Purpose**: WRITE 작업을 위한 Admin 토큰 입력. 성공 시 localStorage에 저장 + 원래 화면 복귀.

```
┌─────────────────────────────────┐
│                                 │
│  ┌─ 관리자 접근 ──────────────┐ │
│  │                            │ │
│  │ 관리자 토큰                │ │
│  │ [••••••••••••••••••••••]   │ │
│  │                            │ │
│  │           [취소]   [저장]  │ │
│  └────────────────────────────┘ │
│                                 │
└─────────────────────────────────┘
```

**States**: initial / error ("토큰을 입력해 주세요.")

**특이사항**: `?return=` 쿼리 파라미터로 원래 화면 경로 복원

---

### 2.14 Not Found (`*`)

**Purpose**: 미등록 라우트 접근 시 대시보드로 자동 리다이렉트.

---

## 3. Shared Components

| Component       | Props / State                       | File                              | Usage                                         |
| --------------- | ----------------------------------- | --------------------------------- | --------------------------------------------- |
| AppHeader       | `$currencyFilter`                   | `components/AppHeader.svelte`     | 모든 페이지 상단 (통화 셀렉터 ALL/KRW/USD + `about` 링크) (FR-040) |
| BottomNav       | navItems, `$location`               | `components/BottomNav.svelte`     | 모바일 하단 5탭 (예약/실시간/홈/투자/AI분석). `/reports` 탭이 `/reflections`, `/retrospective`도 활성 처리 |
| AnalysisTabs    | `$location`, `slot="action"`        | `components/AnalysisTabs.svelte`  | Reports/Reflections/Retrospective 상단 서브탭 (레포트/매매검증/회고분석) |
| SelectMenu      | value, options, placeholder, disabled | `components/SelectMenu.svelte`  | ScheduleDetail, ReportDetail, RetroDetail (회차 선택) |

### Utility Functions (`lib/utils/format.ts`)

| Function             | Description                                    |
| -------------------- | ---------------------------------------------- |
| `formatMoney`        | 부호 포함 통화 포맷 (+$1,234.56)              |
| `formatMoneyPlain`   | 부호 없는 통화 포맷 ($1,234.56)               |
| `formatPercent`      | 퍼센트 포맷 (+12.34%)                         |
| `formatDateTime`     | ISO → 로컬 날짜시간                            |
| `formatAgo`          | ISO → 상대 시간 (방금 전, N분 전, N시간 전)   |
| `formatErrorMessage` | Error → 사용자 친화적 메시지                   |
| `formatAmount`       | ticker 기반 통화 포맷 (KRW: ₩1,234 / USD: $1,234.56). ticker 접미사(.KS/.KQ)로 자동 판단 |
| `formatSignedAmount` | `formatAmount` + 부호 (+₩1,234 / -$1,234.56)  |

---

## 4. Design System Reference

```yaml
ui_library: "Custom CSS (Toss Securities-inspired dark UI)"
font: "Pretendard Variable"
color_scheme: "Dark"
layout:
  container: "page-container (max-width 내부 정의)"
  grid: "list-grid + dashboard-grid"
colors:
  bg: "#0d0f13"
  surface: "#1f2023"
  border: "#23262d"
  text: "#e8edf5"
  text-dim: "#8b96a8"
  primary: "#5b8bff"
  gain: "#ff5d5d"
  loss: "#4c7dff"
  info: "#6aa4ff"
  warn: "#f4b24d"
```

---

## 5. Navigation Flow

```
BottomNav: 예약(/schedules) ─ 실시간(/live) ─ [홈](/) ─ 투자(/positions) ─ AI분석(/reports)
  └ AI분석 탭 활성 그룹: /reports, /reflections, /retrospective

AppHeader: [ALL|KRW|USD] 통화 셀렉터 + about(/about) 링크

Dashboard (/) ──→ Positions (/positions) ──→ TradeDetail (/trade/:ticker)
              ──→ Schedules (/schedules) ──→ ScheduleDetail (/schedules/:ticker)
              ──→ Live (/live)
              ──→ Reports (/reports) ──→ ReportDetail (/reports/:ticker)
              ──→ Reflections (/reflections) [FR-049]
              ──→ Retrospective (/retrospective) ──→ RetroDetail (/retrospective/:ticker) [FR-055]
              ──→ About (/about)
              ──→ Auth (/auth) [401/403 시 자동 리다이렉트]
```

---

## 6. Auth Flow

```yaml
auth_model: "Bearer token (single user)"
read_endpoints: "public"
write_endpoints: "Authorization: Bearer {ADMIN_TOKEN}"
token_entry: "/auth page (with ?return= query param)"
token_storage: "localStorage (gant_admin_token)"
on_401_403: "clearToken() + redirect to /auth?return={current_hash}"
```

---

## 7. PWA Configuration

```yaml
pwa:
  register_type: "autoUpdate"
  manifest:
    name: "GANT Trading Console"
    short_name: "GANT"
    theme_color: "#0d0f13"
    background_color: "#0d0f13"
    display: "standalone"
    icons: ["/icon.svg (any maskable)"]
  workbox:
    api_reports: "CacheFirst (10min, max 100 entries)"
    api_other: "StaleWhileRevalidate (5min, max 100 entries)"
```

---

## Reverse Extraction Info

| Item           | Content                                      |
| -------------- | -------------------------------------------- |
| Generated      | 2026-02-13                                   |
| Last synced    | 2026-03-01 (코드 동기화 — About 화면, 회고분석 요청 플로우, BottomNav 5탭/분석 그룹 활성화) |
| Analysis scope | `apps/web/src/` (14 screens, 4 shared components: AppHeader, BottomNav, AnalysisTabs, SelectMenu) |
