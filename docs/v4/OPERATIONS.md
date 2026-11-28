# GANT v4 Windows 배포

[공개 리포트](https://daehun.app/v4/#/reports)는 현재 발행된 연구와 모의매매 기록을 읽는 Liquid Glass UI다. 이 브랜치의 화면·설치·배포 방식을 바꾸면 이 문서와 [화면 설계](../../DESIGN.md)를 같은 변경에 갱신한다.

| 구성 | 위치 및 책임 |
|---|---|
| 소스 | Windows의 `C:\Users\samda\dev\TradingAgents-V4`, 브랜치 `codex/gant-v4` |
| 화면 서버 | Node.js 기본 HTTP, `127.0.0.1:8035/v4/`, 정적 화면·설치 파일 및 최근 판단 비교 조회 |
| 게시 디렉터리 | `%LOCALAPPDATA%\TradingAgentsV4\web`, 현재 릴리스는 `current` 한 줄 |
| 자동 기동 | Windows 작업 스케줄러의 `TradingAgents V4 Preview`, 현재 사용자 로그인 시 실행 |
| 공개 입구 | `daehun.app`, `research.daehun.app`, `v3.daehun.app`에서 UI를 8035로 전달한다. 각 호스트의 루트에서 `/v4/`로 이동한다. |
| 연구·매매 원본 | 같은 호스트의 `/api/`, `/workspace-api/`, `/public-api/` 조회는 기존 공개 서버 8025. 내부 8024가 v2 발행 기록과 v3 출처 보관소를 조회한다. v2의 8014가 예약·가상매매를 실행한다. |

## 빌드와 게시

Windows PowerShell에서 v4 체크아웃으로 이동한다. Git, Node.js 22 이상과 npm을 사용한다. 이 화면 배포에 Python 환경, DB 초기화 및 운영 계정 인증 정보는 필요하지 않다.

~~~powershell
Set-Location C:/Users/samda/dev/TradingAgents-V4
npm --prefix apps/web ci
npm --prefix apps/web run check
Push-Location apps/web
try {
    $specs = (Get-ChildItem tests -Filter '*.test.mjs').FullName
    node --test $specs
    if ($LASTEXITCODE -ne 0) { throw 'v4 tests failed' }
} finally { Pop-Location }
npm --prefix apps/web run build:v4
if ($LASTEXITCODE -ne 0) { throw 'v4 build failed' }

$current = Join-Path $env:LOCALAPPDATA 'TradingAgentsV4/web/current'
if (Test-Path -LiteralPath $current) { Get-Content -LiteralPath $current }
node scripts/v4-preview.mjs publish apps/web/dist
if ($LASTEXITCODE -ne 0) { throw 'v4 publish failed' }
.\scripts\start-v4-preview.ps1 -RegisterAtLogon
~~~

`build:v4`는 공개 전용 메타태그와 `/v4/` 경로를 넣고 API는 같은 도메인의 루트로 연결한다. 배포 명령은 정적 파일, 설치 앱 설정, 실제 번들의 존재를 확인한 뒤 릴리스 ID를 출력한다. 모든 파일을 준비한 후 현재 릴리스를 원자적으로 교체한다. 이미 열린 탭이 사용하는 이전 해시 자산도 유지한다. 다음 화면 배포부터는 게시만 해도 실행 중인 서버에 바로 반영된다.

최초 기동 시 현재 Windows 사용자에게 로그인 작업을 만든다. 충돌하는 8035 포트의 프로그램이나 다른 명령이 연결된 같은 이름의 작업은 중단하지 않는다. 정상 종료 뒤 수동 기동에는 `.\scripts\start-v4-preview.ps1`을 사용한다. 정적 서버 코드 자체가 바뀌면 등록된 작업의 실행 명령을 확인한 뒤 해당 작업만 재시작한다.

~~~powershell
(Get-ScheduledTask -TaskName 'TradingAgents V4 Preview').Actions | Select-Object Execute,Arguments
Stop-ScheduledTask -TaskName 'TradingAgents V4 Preview'
Get-NetTCPConnection -State Listen -LocalPort 8035 -ErrorAction SilentlyContinue
.\scripts\start-v4-preview.ps1
~~~

## 판단 변화 조회

리포트 첫 화면의 `GET /v4/data/report-pulse`는 8035에서 처리한다. 같은 종목의 이번 회차와 바로 앞 회차를 읽고 발행 시각, 회차 ID, 저장된 판단과 이번 최종 판단의 짧은 발췌문을 제공한다. 가상 체결 내역과 확률 예측은 각자의 상세 화면에서 조회한다.

Windows 뷰어는 고정된 주소 `127.0.0.1:8025`의 공개 리포트 목록과 종목별 최근 두 회차만 조회한다. 일반 상태에서는 5분간 한 번 만든 응답을 재사용하고, 변경이 없는 종목의 비교 결과도 재사용한다. 회차 자료가 일치하지 않거나 일부 읽기에 실패하면 해당 종목을 다시 조회할 수 있도록 비교 불가 상태로 반환한다. 시간이나 결정값이 비어 있는 자료는 방향이 바뀐 것으로 계산하지 않는다.

릴리스에서 `scripts/v4-preview.mjs` 또는 `scripts/v4-report-pulse.mjs`가 바뀌면 8035의 실행 파일·작업 소유자를 먼저 확인하고 위 절차로 v4 작업을 다시 기동한다. 연동 확인은 새 자료를 먼저 제공한 뒤 번들을 게시하는 순서로 진행한다. `/v4/data/report-pulse`의 티커·두 리포트 ID를 `/workspace-api/reports?ticker=WMT&limit=2` 등으로 대조하고, 화면에서 최신 회차의 링크를 눌러 같은 ID인지 확인한다. 8025는 조회에 사용하며 예약 실행과 DB 권한은 v2의 기존 설정을 따른다.

## 터널 라우팅

Windows 터널 구성은 `%LOCALAPPDATA%\TradingAgentsDeploy\tunnel.yml`에 있다. 세 공개 호스트 각각에 아래 두 규칙을 같은 순서로 둔다. 관리자 호스트 `lab.daehun.app`은 기존 8014와 Cloudflare Access의 `originRequest.access` 검증을 사용한다. 마지막에는 기존 `http_status:404` 규칙을 둔다.

~~~yaml
  - hostname: daehun.app
    path: '^/((api|public-api|workspace-api)/.*|(healthz|ready)/?)$'
    service: http://127.0.0.1:8025
  - hostname: daehun.app
    service: http://127.0.0.1:8035
~~~

원본 데이터·계좌·개인용 콘솔의 기동과 백업은 [v3 운영 문서](../v3/OPERATIONS.md)에 연결된 절차를 사용한다. v4 화면 업데이트는 이 서비스들을 재기동하지 않는다.

재부팅 후 Windows 사용자 로그인으로 `TradingAgents Forecast Lab`, `TradingAgents V3 Preview`, `TradingAgents V4 Preview`, `TradingAgents Public Tunnel`이 자동 기동한다. 복구할 때는 8014와 8025의 `/ready`, 8035의 `/v4/`를 먼저 확인하고 응답이 없는 서비스의 등록 작업부터 실행한다. 외부에서는 메인 주소의 307 응답과 최종 리포트·연구 사례 상세 조회를 확인한다.

터널 규칙을 바꿀 때는 같은 디렉터리에 설정 사본을 만들고 `cloudflared tunnel --config <후보파일> ingress validate`와 `ingress rule <URL>`로 공개·관리자 경로를 대조한다. 적용은 이 설정 파일로 실행 중인 커넥터만 교체하고 등록 작업 `TradingAgents Public Tunnel`을 실행한다. 2026-11-28 전환 직전 설정은 같은 디렉터리의 `tunnel-before-v4-only-20261128-234039.yml`이다. 라우팅을 복구할 때는 이 사본을 `tunnel.yml`로 복원한 뒤 같은 커넥터를 재기동한다.

## 화면과 설치 확인

1. 로컬 정적 서버의 `/v4/`와 `/v4/gant.webmanifest`가 200인지 확인한다. 공개 주소에서는 리포트 목록과 회사별 회차·뉴스 출처를 열고, 개발자 도구에서 조회 요청이 같은 출처의 루트 API로 가는지 확인한다. 8035만 단독 열면 원본 API는 제공되지 않는다.
2. 공개 v4의 매니페스트 `id`, `scope`는 `/v4/`, 시작 URL은 `/v4/#/reports`다. 네 가지 일반·마스크형 아이콘과 Apple touch 아이콘을 열 수 있어야 한다. `/v4/gant-sw.js`의 `Service-Worker-Allowed`는 `/v4/`이며 루트에서 설치한 v3와 별도의 앱이다.
   HTML의 `theme-color`, 매니페스트의 `theme_color`와 `background_color`는 모두 `#000000`이다. 스크롤한 리포트에서 전체 메뉴를 열고, 연구 사례의 시장 목록과 날짜 달력도 열어 글래스 표면을 확인한다. 투명도 줄이기 환경에서는 같은 창들이 불투명한 검정 표면으로 표시된다.
3. 세 공개 호스트의 루트가 모두 v4로 연결되는지, 기존 `/#/research`와 `/research/?case=<사례 ID>`가 해당 화면으로 이동하는지 확인한다. 원본 준비 상태는 `http://127.0.0.1:8025/ready`를 조회한다. 로컬 개발 서버는 `npm --prefix apps/web run dev:v4 -- --host 127.0.0.1`로 열고 표시된 주소의 `/v4/`에 접속한다.

## 이전 화면 복구

게시 전 기록해 둔 이전 릴리스 ID 또는 `%LOCALAPPDATA%\TradingAgentsV4\web\releases`의 보관된 ID를 사용한다.

~~~powershell
node scripts/v4-preview.mjs activate <이전-64자리-릴리스-ID>
~~~

복구 명령은 해당 릴리스가 참조하는 JS·CSS를 확인한 뒤 활성 포인터를 교체한다. 공개 주소에서 기존 회차·탭과 설치 앱의 시작 화면을 다시 확인한다.

## 최초 배포 검증

2026년 11월 27일 배포한 버전은 `gant-v4-preview.1`이다. 빌드의 정적 릴리스 ID는 `ff3b1176488dabe391e7cd1dd7892ec35e0c572740814e7bb347113dc3fbac69`다. 공개 주소에서 JS·CSS와 설치 파일 8개의 바이트를 로컬 배포본과 대조했고, v2 메인과 v3 루트의 기존 JS·CSS도 확인했다.

Chromium에서 320·393·768·1440px로 실제 공개 데이터가 있는 화면 16개를 검사했다. 외부 URL에서는 393·1440px에서 같은 16개 화면을 다시 열었고, WebKit에서도 393px로 리포트·상세·연구·대시보드·포트폴리오의 표시를 확인했다. 월마트 검색 및 회차 열람, 출처 펼침, 엔비디아 차트 전환과 가격 표, 사례 선택, 설치 범위, 키보드와 메뉴 터치도 확인했다. Python 회귀 167개와 Node 테스트 10개가 통과했고 Svelte 진단의 오류·경고는 0개였다.

## 두 번째 배포 검증

2026년 11월 27일 `gant-v4-preview.2`의 정적 릴리스 `cd775e4c0d4efb78ad37431eb942dd831a6eb07cffe0b6659e32aaaf3d9358df`를 게시했다. 8035의 v4 작업을 다시 기동해 새 읽기 경로를 확인한 뒤 정적 릴리스를 전환했다. 공개 JS·CSS·설치 파일을 로컬 빌드와 바이트 단위로 대조했다. v2 메인과 v3 루트의 JS·CSS 참조도 이전 배포와 일치했다.

공개 비교 결과 24종목의 회차 ID와 판단을 각각 원본에서 확인했다. 직전 대비 변경은 8종목, 유지는 16종목이었다. 월마트의 직전 1276번과 최신 1300번, SK이노베이션의 직전 1284번과 최신 1308번을 확인했다. 이 수치는 배포 시점 기록이며 이후 회차 발행에 따라 달라진다.

공개 주소의 16개 화면을 393·1440px에서 열었고, 리포트는 Chromium 320·393·768·1440px 및 WebKit 393px에서 두 회차 조회를 점검했다. 종목 검색, 회차 변경, 출처, 예측·가격 차트, 기간 선택, 탐색, PWA 설치 범위를 확인했다. 비교 조회 장애는 별도 후보 환경에서 재현해 기존 디렉터리와 재시도 동작을 검증했다. Python 회귀 167개와 Node 테스트 16개가 통과했으며 Svelte 진단은 오류·경고 0개였다.

## 검정·비취 테마 배포

2026년 11월 27일 승인된 08번 검정·비취 테마를 `gant-v4-preview.3`으로 게시했다. 정적 릴리스 ID는 `e1db3a39e6d59b17f3557fb0470f5a197412ed5391fb0efd357790a2211decb2`다. 8035에서 실행 중인 뷰어의 정적 릴리스 포인터를 교체했다.

후보에서 320·393·768·1440px로 16개 화면을 확인했다. 공개 주소에서는 393·1440px의 같은 화면을 다시 열고 종목 검색, 발행 회차 전환, 출처 펼침, 차트·달력·설치 범위를 점검했다. Chromium과 WebKit에서 실제 메뉴와 선택창의 배경 흐림을 확인했고, Chromium에서 투명도 줄이기와 강제 색상도 확인했다. 공개 JS·CSS·설치 파일 8개가 후보 빌드와 일치했고, v2 메인과 v3 루트의 기존 번들 참조도 대조했다.

## 선택 영역 정렬

2026년 11월 27일 `gant-v4-preview.4`의 정적 릴리스 `b669aacbd4c94c5bce10f1614b11b1d7594237b0feb993b917b09fa925a05423`를 게시했다. 공개 v4의 18개 경로를 320·393·768·1440px에서 열어 화면 폭을 벗어나는 요소를 확인했다. 리포트의 양쪽 탭 전환, 포지션 상태 선택과 연구 상세 탭·차트는 Chromium 및 모바일 크기의 WebKit에서 확인했다.

다음 배포에서도 Chrome이 설치된 PC에서 아래 검사를 실행한다. 리포트와 포지션 화면에서 선택을 양 끝으로 바꿔 실제 칠해지는 면의 반경, 상하좌우 여백, 키보드 포커스를 측정한다. 마지막 인수에 후보 또는 공개 뷰어 주소를 넣는다.

~~~powershell
uv run --no-project --with playwright scripts/check-v4-segment-layout.py https://v3.daehun.app/v4/
~~~

## 공개 진입점 통합

2026년 11월 28일 서버 버전 `gant-v4-preview.5`로 세 공개 호스트의 진입점을 통합했다. 정적 화면은 직전 배포본을 사용한다. 로그인 후 터널과 단일 운영 스케줄러가 자동 기동한 것을 확인했고, 공개 브라우저에서 월마트 리포트 1334번과 연구 사례 92번을 열어 검증했다.
