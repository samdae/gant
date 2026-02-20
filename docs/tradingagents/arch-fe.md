# Frontend Design Doc: TradingAgents UI (GANT)

> Created: 2026-02-15
> Updated: 2026-02-20 (code-based reverse sync)
> Service: tradingagents
> Type: Frontend
> Requirements: docs/tradingagents/spec.md
> UI Specification: docs/tradingagents/ui.md

## 0. Summary

### Goal
Svelte 기반 SPA로 AI 트레이딩 분석 대시보드 구현. REST API + WebSocket 연동, PWA 설치 지원.

### Non-goals
- SSR / SvelteKit
- 멀티유저 인증 / OAuth
- 실제 매매 실행 UI

### Success metrics
- 모든 화면이 API 라이브 데이터로 렌더링
- WS 라이브 피드 1초 이내 업데이트
- 스케줄 CRUD가 admin token 흐름과 동작
- PWA 설치 가능 (standalone)

---

## 1. Scope

### In scope
- Dashboard, Positions, Schedules, ScheduleDetail, TradeDetail, Reports, ReportDetail, Live, Auth (9 페이지)
- SPA 라우팅 + Bearer token gating
- PWA (manifest + service worker + autoUpdate)
- 모바일 최적화 다크 테마 UI

### Out of scope
- SvelteKit / SSR
- 백엔드 코드 변경
- 멀티유저 / RBAC
- 테스트 코드 (Vitest / Playwright)

---

## 1.5. Tech Stack

```yaml
tech_stack:
  framework: "Svelte 4 + Vite 5"
  language: "TypeScript 5.x"
  state_management: "Svelte writable stores"
  styling: "Custom CSS (Toss Securities-inspired dark UI, Pretendard Variable font)"
  routing: "svelte-spa-router (hash-based)"
  api_client: "Fetch wrapper (src/lib/api/client.ts)"
  form_handling: "Native inputs + custom validation"
  build_tool: "Vite"
  markdown: "marked + dompurify"
  third_party:
    - "vite-plugin-pwa (PWA manifest + service worker)"
    - "svelte-spa-router (hash routing)"
    - "marked (markdown → HTML)"
    - "dompurify (HTML sanitization)"
```

---

## 1.6. Dependencies

```yaml
package_manager: "npm"
project_type: "existing"

dependencies:
  - name: "svelte-spa-router"
    version: "^3.3.0"
    purpose: "Hash-based SPA routing"
    status: "approved"

  - name: "marked"
    version: "^17.0.2"
    purpose: "Markdown → HTML 변환 (리포트 렌더링)"
    status: "approved"

  - name: "dompurify"
    version: "^3.3.1"
    purpose: "HTML 살균 (XSS 방지)"
    status: "approved"

  - name: "@types/dompurify"
    version: "^3.0.5"
    purpose: "DOMPurify TypeScript 타입"
    status: "approved"

devDependencies:
  - name: "svelte"
    version: "^4.2.0"
    purpose: "UI 프레임워크"
    status: "approved"

  - name: "vite"
    version: "^5.0.0"
    purpose: "빌드 도구"
    status: "approved"

  - name: "@sveltejs/vite-plugin-svelte"
    version: "^3.0.0"
    purpose: "Svelte + Vite 통합"
    status: "approved"

  - name: "vite-plugin-pwa"
    version: "^0.20.0"
    purpose: "PWA manifest + SW 자동 생성"
    status: "approved"

  - name: "typescript"
    version: "^5.2.2"
    purpose: "TypeScript 컴파일러"
    status: "approved"

  - name: "svelte-check"
    version: "^3.6.0"
    purpose: "Svelte 타입 체크"
    status: "approved"
```

---

## 2. Architecture Impact

### Component Structure

```yaml
component_structure:
  pages:
    - path: "/"
      component: "Dashboard"
      file: "src/routes/Dashboard.svelte"
      description: "시스템 상태, KPI, 포지션, 큐, 활동 요약"
    - path: "/positions"
      component: "Positions"
      file: "src/routes/Positions.svelte"
      description: "활성 포지션 테이블/카드"
    - path: "/schedules"
      component: "Schedules"
      file: "src/routes/Schedules.svelte"
      description: "스케줄 목록 + CRUD 모달 + 티커 자동완성"
    - path: "/schedules/:ticker"
      component: "ScheduleDetail"
      file: "src/routes/ScheduleDetail.svelte"
      description: "사이클별 에이전트 이벤트 타임라인"
    - path: "/trade/:ticker"
      component: "TradeDetail"
      file: "src/routes/TradeDetail.svelte"
      description: "포지션 상세 + OHLC 차트 + 리포트 + 매매 이력"
    - path: "/reports"
      component: "Reports"
      file: "src/routes/Reports.svelte"
      description: "티커별 리포트 요약 목록"
    - path: "/reports/:ticker"
      component: "ReportDetail"
      file: "src/routes/ReportDetail.svelte"
      description: "13개 섹션별 리포트 상세 (마크다운)"
    - path: "/live"
      component: "Live"
      file: "src/routes/Live.svelte"
      description: "큐 + WS 라이브 피드"
    - path: "/auth"
      component: "Auth"
      file: "src/routes/Auth.svelte"
      description: "Admin 토큰 입력 (localStorage)"
    - path: "*"
      component: "NotFoundRedirect"
      file: "src/routes/NotFoundRedirect.svelte"
      description: "대시보드로 리다이렉트"

  shared:
    - name: "AppHeader"
      path: "src/components/AppHeader.svelte"
      description: "상단 로고 + 데스크톱 네비게이션"
    - name: "BottomNav"
      path: "src/components/BottomNav.svelte"
      description: "모바일 하단 5탭 네비게이션"
    - name: "SelectMenu"
      path: "src/components/SelectMenu.svelte"
      props: "value, options, placeholder, disabled"
      description: "커스텀 드롭다운 (사이클 선택 등)"

  lib:
    - name: "api/client.ts"
      description: "Fetch wrapper (BASE_URL, auth header, localStorage 캐싱, 401 리다이렉트)"
    - name: "api/endpoints.ts"
      description: "API 호출 함수 (fetchMetrics, fetchSchedules, createSchedule 등 20개)"
    - name: "ws/liveStream.ts"
      description: "WebSocket 연결 (http→ws URL 변환, onMessage/onError)"
    - name: "utils/format.ts"
      description: "포맷 유틸 (formatMoney, formatPercent, formatAgo, formatErrorMessage)"

  stores:
    - name: "auth.ts"
      description: "tokenStore (writable), setToken, clearToken → localStorage 동기화"
    - name: "tickerNames.ts"
      description: "tickerNames (writable<Record>), loadTickerNames, setTickerName → API /tickers/names"
    - name: "ui.ts"
      description: "liveTickerStore (writable<string|null>)"
```

### File Structure (실제 코드 기준)

```
apps/web/
├── src/
│   ├── routes/
│   │   ├── Dashboard.svelte
│   │   ├── Positions.svelte
│   │   ├── Schedules.svelte
│   │   ├── ScheduleDetail.svelte
│   │   ├── TradeDetail.svelte
│   │   ├── Reports.svelte
│   │   ├── ReportDetail.svelte
│   │   ├── Live.svelte
│   │   ├── Auth.svelte
│   │   └── NotFoundRedirect.svelte
│   ├── components/
│   │   ├── AppHeader.svelte
│   │   ├── BottomNav.svelte
│   │   └── SelectMenu.svelte
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   └── endpoints.ts
│   │   ├── ws/
│   │   │   └── liveStream.ts
│   │   └── utils/
│   │       └── format.ts
│   ├── stores/
│   │   ├── auth.ts
│   │   ├── tickerNames.ts
│   │   └── ui.ts
│   ├── styles/
│   │   ├── base.css          (→ imports prototype.css)
│   │   ├── prototype.css     (전체 스타일, ~3000줄)
│   │   └── tokens.css        (CSS 변수 오버라이드)
│   ├── App.svelte
│   └── main.ts
├── public/
│   ├── favicon.svg
│   └── icon.svg
├── index.html
├── vite.config.ts            (PWA 설정 포함)
├── package.json
├── tsconfig.json
└── svelte.config.js
```

---

## 3. State Management

```yaml
state_management:
  global_state:
    - name: "tokenStore"
      file: "src/stores/auth.ts"
      type: "writable<string | null>"
      initial: "localStorage.getItem('gant_admin_token')"
      sync: "subscribe → localStorage 자동 동기화"
      actions:
        - "setToken(value) → store.set(value)"
        - "clearToken() → store.set(null)"

    - name: "tickerNames"
      file: "src/stores/tickerNames.ts"
      type: "writable<Record<string, string>>"
      initial: "{}"
      actions:
        - "loadTickerNames() → GET /tickers/names (앱 시작 시 1회)"
        - "setTickerName(ticker, name) → 로컬 store 업데이트"
        - "getTickerName(ticker) → display_name || ticker"

    - name: "liveTickerStore"
      file: "src/stores/ui.ts"
      type: "writable<string | null>"
      initial: "null"

  server_state:
    description: "fetch 기반 (SWR/React Query 없음). localStorage 캐시 5분 TTL."
    cache:
      prefix: "gant_api_cache:"
      ttl: "300000ms (5분)"
      strategy: "GET 요청 + 인증 헤더 없는 경우만 캐시"
      offline: "캐시 있으면 stale 데이터 반환"

  local_state:
    - component: "Schedules.svelte"
      states: "formTicker, formInterval, formDisplayName, formError, submitting, showAdd, showDelete, deleteTarget, suggestions, showSuggestions"
    - component: "ScheduleDetail.svelte"
      states: "cycles, selectedCycleId, events, stepStates"
    - component: "TradeDetail.svelte"
      states: "summary, trades, reports, positionId, avgCost, tab(report|history), rawPoints, chartMode(candle|line), chartStats, pointWidth, crosshair, tradeMarkers, selectedHistoryId"
    - component: "ReportDetail.svelte"
      states: "report, reports, selectedReportId, reportOptions, decisionKey, decisionLabel, openSections"
    - component: "Live.svelte"
      states: "queue, messages, ws, connectedTicker, stepStates"
    - component: "Auth.svelte"
      states: "tokenInput, error"
```

---

## 4. Route Definition

```yaml
routes:
  - path: "/"
    component: "Dashboard"
    auth_required: false

  - path: "/positions"
    component: "Positions"
    auth_required: false

  - path: "/schedules"
    component: "Schedules"
    auth_required: false
    note: "POST/DELETE 작업 시 Bearer token 필요"

  - path: "/schedules/:ticker"
    component: "ScheduleDetail"
    params:
      - name: "ticker"
        type: "string"
    auth_required: false

  - path: "/trade/:ticker"
    component: "TradeDetail"
    params:
      - name: "ticker"
        type: "string"
    auth_required: false

  - path: "/reports"
    component: "Reports"
    auth_required: false

  - path: "/reports/:ticker"
    component: "ReportDetail"
    params:
      - name: "ticker"
        type: "string"
    auth_required: false

  - path: "/live"
    component: "Live"
    auth_required: false

  - path: "/auth"
    component: "Auth"
    auth_required: false

  - path: "*"
    component: "NotFoundRedirect"
    auth_required: false
```

---

## 5. API Integration

### API Client Configuration

```yaml
api_client:
  file: "src/lib/api/client.ts"
  base_url: "${VITE_API_BASE_URL || http://localhost:8000}"
  cache:
    enabled: true
    storage: "localStorage"
    prefix: "gant_api_cache:"
    ttl: "300000ms (5분)"
    condition: "GET + no Authorization header"
    offline_fallback: true
  interceptors:
    request:
      - "addAuthToken (if tokenStore has value → Authorization: Bearer)"
      - "addContentType (if body → application/json)"
    response:
      - "handleUnauthorized (401/403 → clearToken + redirect /auth)"
      - "cacheResponse (조건 충족 시 localStorage 저장)"
    error:
      - "readCache (네트워크 실패 시 캐시 반환)"
```

### API Endpoints (src/lib/api/endpoints.ts)

```yaml
api_integration:
  - endpoint: "GET /metrics"
    function: "fetchMetrics"
    used_by: ["Dashboard", "Positions"]

  - endpoint: "GET /health"
    function: "fetchHealth"
    used_by: ["Dashboard"]

  - endpoint: "GET /positions/market"
    function: "fetchPositionsMarket"
    used_by: ["Dashboard", "Positions", "TradeDetail"]

  - endpoint: "GET /positions?status="
    function: "fetchPositions"
    used_by: ["TradeDetail"]

  - endpoint: "GET /queue"
    function: "fetchQueue"
    used_by: ["Dashboard", "Schedules", "Live"]

  - endpoint: "GET /schedules/summary"
    function: "fetchScheduleSummary"
    used_by: ["Dashboard"]

  - endpoint: "GET /activity"
    function: "fetchActivity"
    used_by: ["Dashboard"]

  - endpoint: "GET /schedules"
    function: "fetchSchedules"
    used_by: ["Schedules"]

  - endpoint: "GET /schedules/{ticker}/cycles"
    function: "fetchScheduleCycles"
    used_by: ["Schedules", "ScheduleDetail"]

  - endpoint: "GET /schedules/{ticker}/cycles/{id}/events"
    function: "fetchScheduleCycleEvents"
    used_by: ["ScheduleDetail"]

  - endpoint: "POST /schedules"
    function: "createSchedule"
    used_by: ["Schedules"]
    auth: true

  - endpoint: "DELETE /schedules/{ticker}"
    function: "deleteSchedule"
    used_by: ["Schedules"]
    auth: true

  - endpoint: "GET /reports?ticker="
    function: "fetchReportsByTicker"
    used_by: ["TradeDetail", "ReportDetail"]

  - endpoint: "GET /reports/tickers"
    function: "fetchReportTickers"
    used_by: ["Reports"]

  - endpoint: "GET /positions/{id}"
    function: "fetchPositionDetail"
    used_by: ["TradeDetail"]

  - endpoint: "GET /position/{id}/graph"
    function: "fetchPositionGraph"
    used_by: ["TradeDetail"]

  - endpoint: "GET /search/tickers"
    function: "searchTickers"
    used_by: ["Schedules (autocomplete)"]

  - endpoint: "GET /live/{ticker}/events"
    function: "fetchLiveEvents"
    used_by: ["Live"]

  - endpoint: "GET /tickers/names"
    function: "(via stores/tickerNames.ts)"
    used_by: ["전체 (앱 시작 시 로드)"]

  - endpoint: "WS /ws/analyze/{ticker}"
    function: "connectLiveStream"
    file: "src/lib/ws/liveStream.ts"
    used_by: ["Live"]
```

---

## 6. Code Mapping

| # | Spec Ref | Feature | File | Component/Function | Action | Impl |
|---|----------|---------|------|----------------|--------|------|
| 1 | FR-035 | SPA 라우팅 | src/App.svelte | Router | 10개 라우트 매핑 | [x] |
| 2 | FR-034 | 대시보드 메트릭 | src/routes/Dashboard.svelte | fetchMetrics, fetchScheduleSummary | KPI + 오늘 실행 렌더링 | [x] |
| 3 | FR-025 | 큐 상태 | src/routes/Dashboard.svelte | fetchQueue | 실행중/대기중 표시 | [x] |
| 4 | FR-034 | 포지션 현재가 | src/routes/Positions.svelte | fetchPositionsMarket | 테이블/카드 + PnL 렌더링 | [x] |
| 5 | FR-016 | 스케줄 목록 | src/routes/Schedules.svelte | fetchSchedules, fetchQueue | 카드 + 상태 배지 | [x] |
| 6 | FR-026 | 스케줄 CRUD 인증 | src/routes/Schedules.svelte | createSchedule, deleteSchedule | Bearer token 주입 | [x] |
| 7 | FR-025 | 티커 자동완성 | src/routes/Schedules.svelte | searchTickers | Yahoo Finance 검색 + 250ms debounce | [x] |
| 8 | FR-037 | 스케줄 상세 이벤트 | src/routes/ScheduleDetail.svelte | fetchScheduleCycleEvents | 에이전트 타임라인 렌더링 | [x] |
| 9 | FR-013 | 매매 상세 | src/routes/TradeDetail.svelte | fetchPositionDetail | 포지션 + 매매 + 리포트 | [x] |
| 10 | FR-034 | OHLC 차트 | src/routes/TradeDetail.svelte | fetchPositionGraph | SVG 기반 캔들/라인 차트 + 핀치 줌 + 크로스헤어 | [x] |
| 11 | FR-032 | 리포트 목록 | src/routes/Reports.svelte | fetchReportTickers | 티커별 요약 카드 | [x] |
| 12 | FR-032 | 리포트 상세 | src/routes/ReportDetail.svelte | fetchReportsByTicker | 13개 섹션 마크다운 렌더링 | [x] |
| 13 | FR-025 | 실시간 분석 | src/routes/Live.svelte | connectLiveStream, fetchLiveEvents | WS + DB 이벤트 병합 | [x] |
| 14 | FR-026 | 관리자 인증 | src/routes/Auth.svelte | setToken | localStorage 저장 + 리다이렉트 | [x] |
| 15 | FR-035 | PWA | vite.config.ts | VitePWA | manifest + SW (autoUpdate) | [x] |
| 16 | FR-025 | API 클라이언트 | src/lib/api/client.ts | request, getJson, postJson, deleteJson | localStorage 캐싱 + 401 처리 | [x] |
| 17 | FR-025 | WS 클라이언트 | src/lib/ws/liveStream.ts | connectLiveStream | http→ws 변환 + JSON 파싱 | [x] |
| 18 | FR-035 | 하단 네비게이션 | src/components/BottomNav.svelte | BottomNav | 5탭 (예약/실시간/홈/투자/AI분석) | [x] |
| 19 | FR-035 | 상단 헤더 | src/components/AppHeader.svelte | AppHeader | 로고 + 데스크톱 네비 | [x] |
| 20 | FR-035 | 셀렉트 메뉴 | src/components/SelectMenu.svelte | SelectMenu | 커스텀 드롭다운 | [x] |
| 21 | FR-035 | 글로벌 스토어 | src/stores/auth.ts, tickerNames.ts, ui.ts | tokenStore, tickerNames, liveTickerStore | localStorage 동기화 + API 로드 | [x] |
| 22 | FR-035 | 포맷 유틸 | src/lib/utils/format.ts | formatMoney, formatPercent 등 | 통화/퍼센트/시간 포맷 | [x] |

---

## 7. Implementation Plan

### Required Reference Files

| File | Reference Purpose |
|------|------------------|
| src/styles/prototype.css | 전체 스타일 토큰 + 컴포넌트 스타일 (~3000줄) |
| src/lib/api/client.ts | API 클라이언트 패턴 (캐싱, 인증, 에러 처리) |
| src/lib/api/endpoints.ts | API 호출 함수 목록 |
| src/stores/auth.ts | 인증 스토어 패턴 |
| docs/tradingagents/arch-be.md | 백엔드 API 엔드포인트 명세 |
| docs/tradingagents/ui.md | 화면 명세 + 컴포넌트 계층 |

### Step-by-Step (구현 완료)

1. **Scaffold**: Vite + Svelte + TypeScript + vite-plugin-pwa
2. **Styles**: prototype.css 이식 (다크 테마, Pretendard)
3. **API Client + Stores**: client.ts (캐싱/인증) + auth/tickerNames/ui stores
4. **Routes + Pages**: 10개 라우트 + svelte-spa-router
5. **Dashboard**: 6개 API 병렬 호출 + KPI + 큐 + 활동
6. **Schedules CRUD**: 자동완성 + 모달 + 스와이프 삭제
7. **TradeDetail**: Canvas OHLC 차트 + 마크다운 리포트
8. **Live**: WS 연결 + DB 이벤트 병합
9. **PWA**: manifest + SW (CacheFirst/StaleWhileRevalidate)

---

## 8. User Flow Diagram

### 스케줄 추가 플로우

```
Schedules 화면 → "+ 추가" 클릭
  → AddScheduleModal 표시
    → 티커 입력 → GET /search/tickers (250ms debounce)
      → 자동완성 드롭다운 표시
        → 선택 → display_name 자동 채움
    → 주기 입력 (1~365)
    → "생성" 클릭
      → 유효성 검사 (ticker A-Z0-9.-{1,15}, interval 1~365)
        → POST /schedules (Bearer token)
          → 성공: 목록 갱신 + loadTickerNames()
          → 401: /auth 리다이렉트
          → 409: "이미 등록됨" 에러
```

### 실시간 모니터링 플로우

```
Live 화면 → GET /queue
  → running ticker 있으면:
    → GET /live/{ticker}/events (기존 이벤트 로드)
    → WS /ws/analyze/{ticker} 연결
      → 메시지 수신 → stepStates 업데이트 → 타임라인 렌더링
      → status=completed/error → WS 종료
  → running ticker 없으면:
    → "대기 중" 표시
    → 5초 간격 큐 폴링
```

---

## 9. Style Guide

### Design Tokens

```yaml
design_tokens:
  colors:
    bg: "#0d0f13"
    surface: "#1f2023"
    surface-hover: "#26282d"
    border: "#23262d"
    text: "#e8edf5"
    text-dim: "#8b96a8"
    primary: "#5b8bff"
    primary-hover: "#4b7dff"
    gain: "#ff5d5d"
    loss: "#4c7dff"
    info: "#6aa4ff"
    warn: "#f4b24d"

  typography:
    font_family: "Pretendard Variable, Pretendard, SUIT, Noto Sans KR, sans-serif"
    sizes:
      xs: "0.6875rem (11px)"
      sm: "0.75rem (12px)"
      base: "0.8125rem (13px)"
      lg: "0.875rem (14px)"
      xl: "1.125rem (18px)"

  breakpoints:
    sm: "640px"
    md: "768px"
    lg: "1024px"
```

### Styling Convention

```yaml
styling_convention:
  approach: "Custom CSS (prototype.css, ~3000줄)"
  naming: "BEM-like (page-header, card-body, ticker-badge)"
  responsive: "Mobile First (table → card 전환 @ 640px)"
  dark_mode: "기본 (dark only)"
  css_import: "base.css → prototype.css (단일 체인)"
```

---

## 10. Risks & Tradeoffs

### Chosen Option
- Svelte 4 + Vite SPA (해시 라우팅) + 커스텀 다크 CSS

### Rejected Alternatives
- SvelteKit/SSR: 단일 사용자 대시보드에 불필요한 복잡도
- Tailwind CSS: 기존 prototype.css를 이식하는 것이 더 빠름
- Chart.js/D3: OHLC 차트가 단순하여 Canvas 직접 구현으로 충분

### Reasoning
- 단일 사용자 개인 대시보드 → SSR 불필요
- 기존 프로토타입 CSS 활용으로 개발 속도 극대화
- marked + DOMPurify로 마크다운 리포트 안전 렌더링

### Known Issues
- AppHeader 네비게이션의 "검색" 링크(`/search`)가 라우트 미등록 → NotFound → `/` 리다이렉트
- Dashboard ScheduleSummaryBanner 클릭(`/archive`)도 라우트 미등록 → NotFound → `/` 리다이렉트

### Assumptions
- **Confirmed**: 백엔드 API가 안정적이고 arch-be.md와 일치
- **Confirmed**: 인증 토큰은 localStorage에 영구 저장
- **Confirmed**: PWA autoUpdate로 새 버전 자동 반영

---

## 11. UX/Performance/A11y Checklist

### UX States

| State | Component | Handling | User Feedback |
|-------|-----------|----------|---------------|
| Loading | Dashboard | Inline "불러오는 중..." | 각 섹션 독립 로딩 |
| Empty | Positions | Empty row | "투자가 없습니다." |
| Error | Schedules | Inline error text | formatErrorMessage() 사용 |
| Offline | API client | localStorage 캐시 반환 | Status badge "오프라인" |

### Performance

| Item | Target | Optimization |
|------|--------|--------------|
| Bundle size | < 200KB | Svelte 컴파일 (no virtual DOM) |
| API 캐싱 | 5분 TTL | localStorage + 오프라인 폴백 |
| SW 캐싱 | reports: CacheFirst 10min, API: StaleWhileRevalidate 5min | Workbox 설정 |
| OHLC 차트 | SVG 직접 렌더링 (캔들/라인 모드, 핀치 줌) | 외부 차트 라이브러리 없음 |
| 자동 새로고침 | TradeDetail 30초 | setInterval |

### Accessibility

| Item | Implementation |
|------|----------------|
| Keyboard nav | SelectMenu: aria-expanded + keyboard navigation |
| Touch target | 모바일 카드/버튼 최소 44px |
| Focus visible | CSS focus-visible 스타일 |
| 스크린 리더 | SVG aria-hidden, 시멘틱 table/section |

---

## Reverse Extraction Info

| Item           | Content                                      |
| -------------- | -------------------------------------------- |
| Generated      | 2026-02-15                                   |
| Last synced    | 2026-02-20 (reverse — code-based full sync)  |
| Analysis scope | `apps/web/src/` (10 routes, 3 components, 6 lib/store files) |
