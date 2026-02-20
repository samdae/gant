# UI Specification: TradingAgents (GANT)

> Created: 2026-02-13
> Updated: 2026-02-20 (code-based reverse sync)
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
| 1   | Dashboard       | `/`                  | `GET /health`, `GET /queue`, `GET /positions/market`, `GET /metrics`, `GET /activity`, `GET /schedules/summary` | No               | FR-025, FR-034         |
| 2   | Positions       | `/positions`         | `GET /positions/market`, `GET /metrics`                                                                        | No               | FR-013, FR-025, FR-034 |
| 3   | Schedules       | `/schedules`         | `GET /schedules`, `GET /queue`, `GET /schedules/{ticker}/cycles`, `GET /search/tickers`, `POST /schedules`, `DELETE /schedules/{ticker}` | POST/DELETE: Yes | FR-016, FR-025, FR-026 |
| 4   | Schedule Detail | `/schedules/:ticker` | `GET /schedules/{ticker}/cycles`, `GET /schedules/{ticker}/cycles/{id}/events`                                 | No               | FR-025, FR-037         |
| 5   | Trade Detail    | `/trade/:ticker`     | `GET /positions`, `GET /positions/{id}`, `GET /positions/market`, `GET /reports?ticker=`, `GET /position/{id}/graph` | No               | FR-013, FR-014, FR-020, FR-034 |
| 6   | Reports         | `/reports`           | `GET /reports/tickers`                                                                                         | No               | FR-025, FR-032         |
| 7   | Report Detail   | `/reports/:ticker`   | `GET /reports?ticker=`                                                                                         | No               | FR-025, FR-032         |
| 8   | Live Analysis   | `/live`              | `WS /ws/analyze/{ticker}`, `GET /queue`, `GET /live/{ticker}/events`                                           | No               | FR-025, FR-037         |
| 9   | Auth            | `/auth`              | —                                                                                                              | No               | FR-026                 |
| 10  | Not Found       | `*`                  | —                                                                                                              | No               | —                      |

---

## 2. Screen Specifications

### 2.1 Dashboard (`/`)

**Purpose**: 시스템 상태, 핵심 KPI, 오늘 실행 요약, 활성 포지션, 큐 상태, 최근 활동을 한 화면에 요약.

**Mobile**:

```
┌─────────────────────────────────┐
│ 홈                [● 온라인·대기]│
├─────────────────────────────────┤
│ ┌─ 오늘 실행 ──────────── 12 ─┐ │
│ │ 완료 8  건너뜀 2  실패 1  1 │ │
│ └─────────────────────────────┘ │
│ ┌─ 총손익 ────┬─ 투자 ────────┐ │
│ │ +$423.50    │ 4             │ │
│ │ 수익률+8.5% │ 승 3 · 패 1  │ │
│ └─────────────┴───────────────┘ │
│ ┌─ 내 투자 ──────── 전체 보기 ┐ │
│ │ NVDA 엔비디아    $1,250(+$50)│ │
│ │ AAPL 애플        $890 (-$12)│ │
│ └─────────────────────────────┘ │
│ ┌─ 대기열 ──── 실시간 보기 ───┐ │
│ │ ● TSLA         실행중       │ │
│ │ ○ MSFT         대기중       │ │
│ └─────────────────────────────┘ │
│ ┌─ 최근 활동 ─────────────────┐ │
│ │ ● NVDA 매수 10 @ $125.00   │ │
│ │ ◆ AAPL 결정: 관망          │ │
│ │ ● TSLA 매도 5 @ $245.00    │ │
│ └─────────────────────────────┘ │
├─────────────────────────────────┤
│ 예약  실시간  [홈]  투자  AI분석│
└─────────────────────────────────┘
```

**Desktop (> 1024px)**:

```
┌──────────────────────────────────────────────────────────────┐
│ GANT         예약  실시간  홈  투자  검색                     │
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
│ │                        │  ├────────────────────────────┤ │
│ │                        │  │ 최근 활동                  │ │
│ │                        │  │ ● NVDA 매수 10 @ $125     │ │
│ │                        │  │ ◆ AAPL 결정: 관망         │ │
│ └────────────────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**States**: loading / error (오프라인 배지) / loaded

**API Calls**: `fetchMetrics`, `fetchPositionsMarket`, `fetchQueue`, `fetchActivity`, `fetchHealth`, `fetchScheduleSummary`

---

### 2.2 Positions (`/positions`)

**Purpose**: 활성 포지션의 현재가·미실현 수익률 표시. 클릭 시 Trade Detail로 이동.

**Mobile (카드 리스트)**:

```
┌─────────────────────────────────┐
│ 투자                 손익 +$423 │
├─────────────────────────────────┤
│ ┌───────────────────────────┐   │
│ │ NVDA 엔비디아     +4.12%  │   │
│ │ 보유 10 · 1주 평균 $125   │   │
│ │ 총 금액 $1,250 (+$50.00) │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ AAPL 애플         -1.33%  │   │
│ │ 보유 5 · 1주 평균 $180    │   │
│ │ 총 금액 $890 (-$12.00)   │   │
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

**States**: loading / error / empty ("투자가 없습니다.") / loaded

**API Calls**: `fetchPositionsMarket`, `fetchMetrics`

**Interactions**: 행/카드 클릭 → `/#/trade/{ticker}`

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
│ │ 매일 · 12회차             │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ AAPL 애플        [활성]   │   │
│ │ 매일 · 8회차              │   │
│ │         ← 스와이프로 삭제 │   │
│ └───────────────────────────┘   │
│ ┌───────────────────────────┐   │
│ │ TSLA             [대기중] │   │
│ │ 2일마다 · 3회차           │   │
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

### 2.8 Live Analysis (`/live`)

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

### 2.9 Auth (`/auth`)

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

### 2.10 Not Found (`*`)

**Purpose**: 미등록 라우트 접근 시 대시보드로 자동 리다이렉트.

---

## 3. Shared Components

| Component       | Props / State                       | File                              | Usage                                         |
| --------------- | ----------------------------------- | --------------------------------- | --------------------------------------------- |
| AppHeader       | navItems, $location                 | `components/AppHeader.svelte`     | 모든 페이지 상단 (로고 + 데스크톱 네비게이션) |
| BottomNav       | navItems, $location                 | `components/BottomNav.svelte`     | 모바일 하단 5탭 (예약/실시간/홈/투자/AI분석)  |
| SelectMenu      | value, options, placeholder, disabled | `components/SelectMenu.svelte`  | ScheduleDetail, ReportDetail (사이클 선택)     |

### Utility Functions (`lib/utils/format.ts`)

| Function           | Description                                    |
| ------------------ | ---------------------------------------------- |
| `formatMoney`      | 부호 포함 통화 포맷 (+$1,234.56)              |
| `formatMoneyPlain` | 부호 없는 통화 포맷 ($1,234.56)               |
| `formatPercent`    | 퍼센트 포맷 (+12.34%)                         |
| `formatDateTime`   | ISO → 로컬 날짜시간                            |
| `formatAgo`        | ISO → 상대 시간 (방금 전, N분 전, N시간 전)   |
| `formatErrorMessage` | Error → 사용자 친화적 메시지                 |

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
AppHeader: 예약(/schedules) ─ 실시간(/live) ─ [홈](/) ─ 투자(/positions) ─ 검색(/search ⚠️ 라우트 미등록)

Dashboard (/) ──→ Positions (/positions) ──→ TradeDetail (/trade/:ticker)
              ──→ Schedules (/schedules) ──→ ScheduleDetail (/schedules/:ticker)
              ──→ Live (/live)
              ──→ Reports (/reports) ──→ ReportDetail (/reports/:ticker)
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
| Last synced    | 2026-02-20 (reverse — code-based full sync)  |
| Analysis scope | `apps/web/src/` (Svelte + TypeScript)        |
