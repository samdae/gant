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

**Component Hierarchy**:

```yaml
DashboardPage:
  - PageHeader:
      - Title: "홈"
      - StatusBadge: 온라인/오프라인/실행중 (queue.running 기반)
  - ScheduleSummaryBanner (card, 클릭 → /archive — 현재 라우트 미등록으로 / 리다이렉트):
      - 오늘 실행 총 합계
      - 완료/건너뜀/실패/실행중 4항목
  - MetricStrip (card, 2 segments):
      - TotalPnlSegment (총손익 + 수익률)
      - InvestmentSegment (투자 수 + 승/패)
  - DashboardGrid:
      - ActivePositionsCard (table):
          - ticker + display_name + 총금액 + PnL
          - 클릭 → /trade/{ticker}
      - QueueCard:
          - running (실행중) + pending (대기중) 표시
          - 링크 → /live
      - RecentActivityCard:
          - activity 이벤트 목록 (trade/analysis 유형)
          - activity dot 색상: buy=파랑, sell=빨강, hold=회색, analysis=보라
```

**States**: loading / error (오프라인 배지) / loaded

**API Calls**: `fetchMetrics`, `fetchPositionsMarket`, `fetchQueue`, `fetchActivity`, `fetchHealth`, `fetchScheduleSummary`

---

### 2.2 Positions (`/positions`)

**Purpose**: 활성 포지션의 현재가·미실현 수익률 표시. 클릭 시 Trade Detail로 이동.

**Component Hierarchy**:

```yaml
PositionsPage:
  - PageHeader:
      - Title: "투자"
      - PnlBanner (총 손익)
  - Table (desktop): ticker, 보유, 1주 평균, 총 금액(+PnL), 수익률
  - CardList (mobile): ticker + display_name + return badge + 보유 상세
```

**States**: loading / error / empty ("투자가 없습니다.") / loaded

**API Calls**: `fetchPositionsMarket`, `fetchMetrics`

**Interactions**: 행 클릭 → `/#/trade/{ticker}`

---

### 2.3 Schedules (`/schedules`)

**Purpose**: 분석 스케줄 CRUD. 티커 추가/삭제 + 상태(실행중/대기중/활성) 표시.

**Component Hierarchy**:

```yaml
SchedulesPage:
  - PageHeader:
      - Title: "예약"
      - AddButton: "+ 추가"
  - ScheduleList (card grid):
      - ScheduleCard (repeat):
          - ticker + display_name + status badge
          - 주기 (매일/N일마다) + 회차
          - 좌 스와이프 → 삭제 확인 (모바일 제스처)
          - 클릭 → /schedules/{ticker}
  - AddScheduleModal:
      - TickerInput (자동완성, GET /search/tickers)
      - DisplayNameInput
      - IntervalDaysInput (1~365)
      - 유효성 검사: ticker A-Z0-9.-{1,15}
  - DeleteConfirmModal
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

**Component Hierarchy**:

```yaml
ScheduleDetailPage:
  - PageHeader:
      - BackButton → /schedules
      - Title: ticker + display_name
  - CycleSelector (SelectMenu dropdown):
      - 사이클 목록 (최신 순)
  - EventTimeline:
      - PhaseGroup (Data Collection / Investment Debate / Trade Decision / Risk Assessment / Execution)
      - AgentStep (repeat):
          - agent name + status icon (running/completed/error/skipped)
          - message + timestamp
```

**States**: loading / error / empty / loaded / loadingEvents

**API Calls**: `fetchScheduleCycles(ticker, 10)`, `fetchScheduleCycleEvents(ticker, scheduleId)`

---

### 2.5 Trade Detail (`/trade/:ticker`)

**Purpose**: 특정 티커의 포지션 상태, OHLC 차트, 최신 리포트, 매매 이력 표시.

**Component Hierarchy**:

```yaml
TradeDetailPage:
  - PageHeader:
      - BackButton → /positions
      - Title: ticker + display_name
      - PnL badge
  - PositionSummaryCard:
      - 보유 주식수 / 평균가 / 현재가 / 총 금액 / 수익률
  - OHLCChart (SVG):
      - 캔들/라인 모드 토글 (chartMode: candle | line)
      - 일봉 차트 (GET /position/{id}/graph)
      - 볼륨 바 (하단)
      - 매매 마커 (BUY=gain 삼각형, SELL=loss 삼각형)
      - 평균가 수평선
      - 크로스헤어 (터치/마우스)
      - 핀치 줌 (pointWidth 8~40px)
  - TabBar: [리포트 / 매매 이력]
  - TabContent:
      - Report: 최신 리포트 요약 + 전체 리포트 드롭다운 (SelectMenu)
      - History: 매매 이력 테이블
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

**Component Hierarchy**:

```yaml
ReportsPage:
  - PageHeader: "AI분석"
  - TickerList (card grid):
      - TickerCard (repeat):
          - ticker + display_name
          - report_count + latest_cycle + latest_at
          - 최신 결정 (BUY/SELL/HOLD badge)
          - portfolio_action + trade_action
          - 클릭 → /reports/{ticker}
```

**States**: loading / error / empty / loaded

**API Calls**: `fetchReportTickers`

**특이사항**: 결정 추출 로직 (BUY/SELL/HOLD, 한국어 매수/매도/관망 인식)

---

### 2.7 Report Detail (`/reports/:ticker`)

**Purpose**: 특정 티커의 분석 리포트 상세 (13개 섹션별 내용 표시).

**Component Hierarchy**:

```yaml
ReportDetailPage:
  - PageHeader:
      - BackButton → /reports
      - Title: ticker + display_name
  - CycleSelector (SelectMenu):
      - 사이클 목록 (최신 순)
  - ReportSections (accordion, 7그룹):
      - 분석: 시장 분석, 펀더멘털 분석
      - 투자 토론: 심판 결론(판정) + 하위(강세 분석, 약세 분석)
      - 투자 계획: 투자 계획
      - 매매 결정: 트레이더 결정
      - 리스크 토론: 리스크 결론(판정) + 하위(공격적/보수적/중립 분석)
      - 최종 결정: 최종 매매 결정
      - 트레이더 의견: PA 의견
```

**States**: loading / error / empty / loaded

**API Calls**: `fetchReportsByTicker(ticker, limit)`

**특이사항**: 마크다운 렌더링 (marked + DOMPurify), 각 섹션 접기/펼치기

---

### 2.8 Live Analysis (`/live`)

**Purpose**: WebSocket으로 에이전트 실행 상태를 실시간 스트리밍.

**Component Hierarchy**:

```yaml
LiveAnalysisPage:
  - PageHeader: "실시간"
  - QueueSection:
      - RunningTicker (실행중)
      - PendingList (대기중)
  - AgentPipeline:
      - PhaseGroup (분석/투자토론/매매결정/리스크평가/실행):
          - AgentStep (repeat):
              - step number + agent name + status icon
              - message text
  - EventLog:
      - 최근 이벤트 역순 목록
```

**States**: loading / idle ("대기 중") / connected (WS live) / disconnected

**API Calls**: `fetchQueue`, `fetchLiveEvents(ticker)`, `WS /ws/analyze/{ticker}`

**특이사항**:
- onMount 시 `fetchQueue` 1회 호출, running ticker 있으면 자동 WS 연결
- `fetchLiveEvents(ticker)` → DB 기존 이벤트 로드 → `seedEvents`로 stepStates 초기화
- WS 실시간 이벤트와 병합 (messages 최대 20개 유지)
- 5단계 phase 그룹 한국어 라벨: 분석 / 투자 토론 / 매매 결정 / 리스크 토론 / 실행
- 13개 에이전트별 한국어 라벨 매핑 (시장 분석 에이전트, 강세 분석 에이전트 등)

---

### 2.9 Auth (`/auth`)

**Purpose**: WRITE 작업을 위한 Admin 토큰 입력. 성공 시 localStorage에 저장 + 원래 화면 복귀.

**Component Hierarchy**:

```yaml
AuthPage:
  - Card:
      - Title: "관리자 접근"
      - TokenInput (password type)
      - Error message (inline)
      - SaveButton + CancelButton
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
