# GANT v3 Windows 개발 운영

| 구성 | v3 위치 |
|---|---|
| 소스 | C:\Users\samda\dev\TradingAgents-V3 · codex/gant-v3 |
| 런타임 | %LOCALAPPDATA%\TradingAgentsV3 |
| PostgreSQL | 127.0.0.1:55436, 독립 pgdata, SCRAM 인증 |
| 연구·콘솔·검증 | forecast_lab_research, forecast_lab_console, forecast_lab_acceptance · 각 DB의 별도 로그인 |
| 운영자·조회용 로컬 화면 | http://127.0.0.1:8024/ · http://127.0.0.1:8025/ |
| 외부 운영 | [v3 읽기 전용 프리뷰](https://v3.daehun.app/) · [v2 메인](https://daehun.app/) · [v2 기존 공개 주소](https://research.daehun.app/) · [v2 관리자](https://lab.daehun.app/) |

v3 개발 DB는 빈 상태에서 시작한다. 포트와 클러스터 디렉터리를 함께 확인한다. 보호된 런타임 안의 lab.env, console.env, acceptance.env가 각 자격증명을 담고 있다. 초기 연구 스케줄은 꺼 두고, 등록된 가상매매 예약도 빈 상태에서 시작한다. 같은 DB명이 있는 v2 클러스터는 55434에서 운영된다.

## 개발 도구

현재 Windows 사용자에 설치한 Impeccable은 화면 설계와 실제 렌더링 점검에, last30days는 출처를 수동으로 조사할 때 사용한다. Codex 사용자 스킬은 %USERPROFILE%\.codex\skills 아래에 있다. last30days 4.6.0은 Python 3.12 이상으로 실행한다.

개발 회고는 gant-dev-memory 스킬에서 claude-mem 16.1.3에 저장한다. 워커와 데이터는 %LOCALAPPDATA%\GantDevHarness에 있고 전용 주소는 127.0.0.1:37779다. 스킬은 v3 개발 체크아웃에서만 작동한다. 자동 대화 수집 대신 명시적으로 저장한 설계 결정과 검증 내역을 검색한다. 운영 모델이 사용하는 입력·시장 RAG와 별도로 운영한다.

## 재현용 기준

| 도구 | 확인한 upstream 버전 |
|---|---|
| Impeccable | 4.10.0 · b49177d32788 |
| last30days | 4.6.0 · 7c2e1c2b099b |
| claude-mem | npm 16.1.3 |
| claude-trading-skills | 4080042a7863 · trade-hypothesis-ideator |

[제품·설계](README.md) · [v2 기준 설계](../forecast-lab/DESIGN.md)

## 설치와 기동

Windows에서 이 브랜치를 체크아웃하고 PowerShell로 저장소 루트에 들어간다. PostgreSQL 17의 Windows 실행 파일은 %LOCALAPPDATA%\TradingAgentsDeploy\pgsql\bin에 둔다. 비어 있는 PC에는 uv, Node.js/npm, Git 및 모델 호출용 Codex 로그인이 필요하다.

~~~powershell
uv sync --frozen
Push-Location apps/web
try {
    npm ci
    $env:VITE_FORECAST_LAB = '1'
    $env:VITE_API_BASE_URL = '/workspace-api'
    npm run build
} finally { Pop-Location }
~~~

처음 설치하는 PC에서만 아래 명령으로 클러스터와 세 DB를 만든다. 런타임 디렉터리나 포트가 이미 사용 중이면 명령이 중단된다. 중간 실패는 보호된 logs에서 원인을 확인한 뒤 복구한다.

~~~powershell
.\.venv\Scripts\python.exe scripts/initialize-v3-runtime.py
~~~

기존 Windows 설치에서는 다음 명령부터 시작한다. loopback 읽기 전용 서버가 v3 운영자 서버만 조회하며 공유 Cloudflare 터널의 v3 호스트는 8025를 향한다. TradingAgents V3 Preview 예약 작업은 Windows 사용자 로그온 시와 15분 간격으로 웹 서비스를 기동한다. 공유 커넥터는 v2 체크아웃의 TradingAgents Public Tunnel 작업이 기동한다. 예측 자동 실행은 별도 lab.env 설정을 따른다.

~~~powershell
.\scripts\start-forecast-lab-services.ps1
Invoke-RestMethod 'http://127.0.0.1:8024/ready'
Invoke-RestMethod 'http://127.0.0.1:8025/healthz'
~~~

연구 목록은 seed 명령으로 등록한다. 현재 인스턴스에는 v2 관찰 목록 23개(한국 10, 미국 13)를 가져왔다. 예측, 가상거래, 기억은 v3에서 새로 생성한다.

~~~powershell
$labEnv = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env'
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app --env-file $labEnv seed --us NVDA WMT KO --kr 316140.KS
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.issue_collector --env-file $labEnv
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app --env-file $labEnv run-once --limit 1
~~~

run-once는 적격 종목에서 실제 모델을 사용해 예측을 발행한다. 채점에는 실제 다섯 번째 거래일의 관측이 필요하다. 자동 발행을 시작하려면 v3 lab.env의 FORECAST_LAB_SCHEDULER_ENABLED를 1로 설정하고 v3 운영자 서버를 재시작한다. 이슈 수집을 예약하는 방법은 [수집 운영 문서](ISSUES.md)에 있다. 재시작은 v3 포트를 소유하고 v3 체크아웃 또는 런타임을 참조하는 프로세스만 대상으로 한다. DB 백업은 v3 체크아웃의 scripts/backup-forecast-lab.py를 프로젝트 가상환경에서 실행한다.

## 검증

~~~powershell
$env:PG_TEST_BINDIR = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin'
$env:FORECAST_PUBLIC_UI_DIST = (Resolve-Path apps/web/dist).Path
$line = Get-Content (Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/acceptance.env') | Where-Object { $_ -like 'FORECAST_LAB_DSN=*' }
$env:FORECAST_LAB_ACCEPTANCE_DSN = $line.Substring('FORECAST_LAB_DSN='.Length)
try { .\.venv\Scripts\python.exe -m unittest discover -s tests -v }
finally { Remove-Item Env:FORECAST_LAB_ACCEPTANCE_DSN -ErrorAction SilentlyContinue }
~~~

브라우저 검증에는 Windows Chrome 설치가 필요하다. 별도 경로를 사용하면 CHROME_BIN에 실행 파일을 지정한다. 프런트엔드 검사와 단위 테스트는 apps/web에서 `npm run check`와 `node --test tests/api-cache.test.mjs tests/research-markdown.test.mjs`를 실행한다. 수집·채점 회귀는 검증 DB 또는 별도 임시 PostgreSQL에서 수행한다.

## 첫 Windows 프리뷰 검증 · 2026-11-25 KST

새 DB에서 관찰 종목 23개를 대상으로 RSS 수집을 실행해 모든 종목에서 적격 기사를 받았다. 개발용 last30days는 Hacker News 검색으로 실제 결과 3건을 내보냈고 수집 명령에서 별도로 가져왔다. 수집 결과는 저장 당시의 검색 범위에 의존한다.

첫 실제 사례는 NVDA #1이다. 11월 24일 미국 거래일 자료로 기준선·단일 모델·토론 확률을 발행했다. 첫 토론 시도는 시간 제한으로 실패했다. 같은 사례의 동결된 근거로 재시도해 토론 결과를 저장했고 기존 단일 모델 결과를 유지했다. 만기 전에는 두 가격 조건이 대기이고, 사용할 수 있는 성숙 기억이 없어 기억 실험 두 가지는 건너뛰었다. 최신순 이슈 40건을 보관했다. 만기 예정은 12월 3일 06:00 KST다.

[외부 조회용 사례](https://v3.daehun.app/#/research/1) · [로컬 조회용 사례](http://127.0.0.1:8025/#/research/1) · [로컬 운영자 사례](http://127.0.0.1:8024/#/research/1)

이 프리뷰는 gant-v3-preview.1 태그로 재현한다. Windows PostgreSQL과 Chrome을 사용한 전체 테스트 142건, 프런트엔드 단위 테스트 2건이 통과했고 Svelte 검사에서 오류·경고가 0건이었다. 아래 두 가지 동작도 실행 중인 인스턴스에서 확인했다. 8024·8025에서 같은 NVDA 사례의 기준선·단일 모델·토론 결과를 읽을 수 있고, 8025의 쓰기 요청은 HTTP 405로 차단된다.

## 통합 콘솔의 배포와 검증

연구 사례와 분석 리포트는 같은 Svelte 앱에서 읽는다. 예측은 `/#/research/{id}`, 매매 분석은 `/#/reports/{ticker}`에서 열며, 리포트 목록은 `/#/reports`다. 기존 `/research/?case=1`, `/research/#results`, `/research/#observe` 북마크도 각각 해당 화면으로 연결된다.

운영 중에 업데이트할 때는 위와 같은 두 Vite 환경 변수로 배포 후보를 별도 폴더에 빌드하고, 전체 테스트의 `FORECAST_PUBLIC_UI_DIST`를 그 폴더로 지정한다. 서버 변경이 있으면 v3의 `/api/status`가 유휴 상태이고 `/workspace-api/queue`가 비었는지 확인한다. 8024 리스너의 명령줄에서 v3의 lab.env와 `serve --console`을, 8025에서는 v3 packages와 `public_app:app`을 대조한다. 해당 리스너만 하나씩 재시작하고 각 포트에서 연구 사례가 조회되는지 확인한다. 8024는 `scripts/start-forecast-lab.ps1`, 8025는 `scripts/start-forecast-lab-public.ps1`로 기동한다.

기존 v3 dist의 index.html을 보관하고, 후보의 해시가 붙은 JS와 CSS를 먼저 복사한 뒤 index.html을 원자적으로 교체한다. 직전 정적 파일을 남겨 두면 보관한 index.html로 화면을 복구할 수 있다. 서버 코드까지 복구해야 하면 직전 릴리스 태그와 호환되는 번들을 함께 기동한다. 이 배포에는 PostgreSQL 초기화·재시작이나 Cloudflare 설정 변경이 필요하지 않다.

최초 통합 확인용 기록은 엔비디아 #1이다. 공개 사례 API와 PC·모바일 화면에서 시세 65거래일, 역할 토론 8개, 동결 RSS 40건, 같은 시각 기준 last30days 3건을 대조할 수 있다. 마지막 3건은 최초 동결 40건 밖에 있던 자료다. 가상매매 리포트가 없는 초기 DB에서는 두 회차의 테스트 데이터를 사용해 출처의 시간 경계, 회차 변경 및 이전 응답 처리를 검증한다.

2026-11-25에 공개한 통합 콘솔의 태그는 `gant-v3-preview.2`다. Windows에서 Python 테스트 146건, 프런트엔드 단위 테스트 2건, Svelte 타입 검사를 통과했다. 공개 주소에서 360·393·1440px로 리포트 목록부터 엔비디아 사례, 원문 목록과 발행 당시 시각, 역할별 토론, 기존 북마크까지 검증했다. 12개 공개 화면과 5개 운영자 화면에서 조회를 확인했다. 공개 서버의 쓰기 요청은 405였으며 v2의 두 공개 주소가 제공한 번들은 배포 전 해시와 일치했다.
