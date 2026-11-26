# GANT v4 Windows 배포

[공개 리포트](https://v3.daehun.app/v4/#/reports)는 현재 발행된 연구와 모의매매 기록을 읽는 Liquid Glass UI다. 이 브랜치의 화면·설치·배포 방식을 바꾸면 이 문서와 [화면 설계](../../DESIGN.md)를 같은 변경에 갱신한다.

| 구성 | 위치 및 책임 |
|---|---|
| 소스 | Windows의 `C:\Users\samda\dev\TradingAgents-V4`, 브랜치 `codex/gant-v4` |
| 화면 서버 | Node.js 기본 HTTP, `127.0.0.1:8035/v4/`, 정적 파일 GET·HEAD |
| 게시 디렉터리 | `%LOCALAPPDATA%\TradingAgentsV4\web`, 현재 릴리스는 `current` 한 줄 |
| 자동 기동 | Windows 작업 스케줄러의 `TradingAgents V4 Preview`, 현재 사용자 로그인 시 실행 |
| 공개 입구 | 기존 Cloudflare Tunnel의 `v3.daehun.app`에서 `/v4` 경로만 8035로 전달 |
| 연구·매매 원본 | 같은 호스트의 `/api/`, `/workspace-api/`, `/public-api/` 조회는 기존 공개 서버 8025. 내부 8024가 v2 발행 기록과 v3 출처 보관소를 조회한다. v2의 8014가 예약·가상매매를 실행한다. |

## 빌드와 게시

Windows PowerShell에서 v4 체크아웃으로 이동한다. Git, Node.js 22 이상과 npm을 사용한다. 이 화면 배포에 Python 환경, DB 초기화 및 운영 계정 인증 정보는 필요하지 않다.

~~~powershell
Set-Location C:/Users/samda/dev/TradingAgents-V4
npm --prefix apps/web ci
npm --prefix apps/web run check
node --test apps/web/tests/v4-preview.test.mjs
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

## 터널 라우팅

기존 Windows 터널 구성은 `%LOCALAPPDATA%\TradingAgentsDeploy\tunnel.yml`에 있다. 아래 경로 규칙은 같은 호스트의 기본 8025 규칙보다 앞에 있어야 한다. 호스트와 기존 DNS 레코드를 공유한다. 터널 커넥터의 설정 검증·교체 순서는 [v2 운영 문서](../forecast-lab/OPERATIONS.md)를 따른다.

~~~yaml
  - hostname: v3.daehun.app
    path: ^/v4(/.*)?$
    service: http://127.0.0.1:8035
  - hostname: v3.daehun.app
    service: http://127.0.0.1:8025
~~~

원본 데이터·계좌·개인용 콘솔의 기동과 백업은 [v3 운영 문서](../v3/OPERATIONS.md)에 연결된 절차를 사용한다. v4 화면 업데이트는 이 서비스들을 재기동하지 않는다.

## 화면과 설치 확인

1. 로컬 정적 서버의 `/v4/`와 `/v4/gant.webmanifest`가 200인지 확인한다. 공개 주소에서는 리포트 목록과 회사별 회차·뉴스 출처를 열고, 개발자 도구에서 조회 요청이 같은 출처의 루트 API로 가는지 확인한다. 8035만 단독 열면 원본 API는 제공되지 않는다.
2. 공개 v4의 매니페스트 `id`, `scope`는 `/v4/`, 시작 URL은 `/v4/#/reports`다. 네 가지 일반·마스크형 아이콘과 Apple touch 아이콘을 열 수 있어야 한다. `/v4/gant-sw.js`의 `Service-Worker-Allowed`는 `/v4/`이며 루트에서 설치한 v3와 별도의 앱이다.
3. 같은 호스트의 루트에서 v3를 열고 기존 번들과 데이터를 확인한다. 원본 준비 상태는 `http://127.0.0.1:8025/ready`를 조회한다. 로컬에서 통합 화면을 개발할 때는 `npm --prefix apps/web run dev:v4 -- --host 127.0.0.1`로 Vite를 열고 표시된 주소의 `/v4/`에 들어간다. 로컬 개발 서버의 API 요청은 8025로 전달된다.

## 이전 화면 복구

게시 전 기록해 둔 이전 릴리스 ID 또는 `%LOCALAPPDATA%\TradingAgentsV4\web\releases`의 보관된 ID를 사용한다.

~~~powershell
node scripts/v4-preview.mjs activate <이전-64자리-릴리스-ID>
~~~

복구 명령은 해당 릴리스가 참조하는 JS·CSS를 확인한 뒤 활성 포인터를 교체한다. 공개 주소에서 기존 회차·탭과 설치 앱의 시작 화면을 다시 확인한다.

## 최초 배포 검증

2026년 11월 27일 배포한 버전은 `gant-v4-preview.1`이다. 빌드의 정적 릴리스 ID는 `ff3b1176488dabe391e7cd1dd7892ec35e0c572740814e7bb347113dc3fbac69`다. 공개 주소에서 JS·CSS와 설치 파일 8개의 바이트를 로컬 배포본과 대조했고, v2 메인과 v3 루트의 기존 JS·CSS도 확인했다.

Chromium에서 320·393·768·1440px로 실제 공개 데이터가 있는 화면 16개를 검사했다. 외부 URL에서는 393·1440px에서 같은 16개 화면을 다시 열었고, WebKit에서도 393px로 리포트·상세·연구·대시보드·포트폴리오의 표시를 확인했다. 월마트 검색 및 회차 열람, 출처 펼침, 엔비디아 차트 전환과 가격 표, 사례 선택, 설치 범위, 키보드와 메뉴 터치도 확인했다. Python 회귀 167개와 Node 테스트 10개가 통과했고 Svelte 진단의 오류·경고는 0개였다.
