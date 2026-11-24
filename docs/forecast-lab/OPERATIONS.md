# Windows 연구실 실행과 복구

## 인계 시 먼저 확인할 항목

기획과 측정 규약은 [기획](PRODUCT.md)과 [설계](DESIGN.md)에 있다. 프로젝트는 `C:\Users\samda\dev\TradingAgents-ForecastLab`의 `codex/forecast-lab` 브랜치다. 기존 공개 사이트는 별도 프로젝트에서 계속 실행된다. 연구실 주소는 이 PC의 [로컬 대시보드](http://127.0.0.1:8014/)다.

| 구성 | 연구실 설정 |
|---|---|
| DB | 별도 Windows PostgreSQL 17 클러스터, `127.0.0.1:55434`, DB `forecast_lab_research`, 비관리자 앱 역할 `forecast_lab_app`, 시간대 UTC |
| 가상매매 콘솔 | 같은 클러스터의 별도 DB `forecast_lab_console`, 전용 비관리자 역할 `forecast_lab_console_app`, `console.env`. 콘솔의 에이전트·포트폴리오 모드와 24개 예약은 이 DB를 사용 |
| 검증 | 같은 연구 클러스터 안에 별도 DB `forecast_lab_acceptance`, 테스트마다 임시 스키마 사용 |
| 런타임 | `%LOCALAPPDATA%\TradingAgentsForecastLab` 아래 `pgdata`, 운영용 `lab.env`, 테스트용 `acceptance.env`, 작업 상태·로그 |
| 모델 | 현재 Windows 사용자의 Codex ChatGPT 로그인. 모델은 `FORECAST_LAB_MODEL`에 명시 |
| 기억 | PostgreSQL에 성숙한 확률·근거·특징·시장 관측을 저장. 운영 Chroma와 별도 |
| 마켓 데이터 | 종목 식별과 기업행위는 Yahoo, 한국 가격은 NAVER 차트, 미국 가격은 Yahoo. 정규장 시각은 XKRX/XNYS 거래소 달력 |
| 선택형 외부 비교 | `FORECAST_LAB_LEGACY_REFERENCE=1`에서 기존 공개 리포트의 루프백 읽기 경로 사용. 장애 시 연구는 계속됨 |

## 평상시 시작과 점검

로그인 없이 [공개 콘솔](https://research.daehun.app/)에서 대시보드, 종목별 분석 리포트, 연구 결과, 가상계좌 잔고·수량·체결, 예약과 회고를 조회한다. [운영 콘솔](https://lab.daehun.app/)은 승인된 이메일로 받은 Cloudflare Access 일회용 코드로 로그인한다. 관리 세션은 12시간이며 가상매매 변경에는 콘솔 자체 관리자 인증도 필요하다.

### 외부 경로와 복구

| 호스트 | 터널 원본 | 외부 방문자의 권한 |
|---|---|---|
| `research.daehun.app` | `http://127.0.0.1:8015` | 운영 콘솔과 같은 화면으로 익명 조회 |
| `lab.daehun.app` | `http://127.0.0.1:8014` | **Forecast Lab** Access 앱의 개별 이메일 정책으로 전체 콘솔 보호 |
| `daehun.app` | `http://127.0.0.1:18080` | 기존 사이트의 독립적인 Nginx 경로 |

공개 앱은 관리 서버와 같은 `apps/web/dist` 파일에 읽기 전용 표시를 넣어 제공한다. 공개 프로세스는 DB 인증 없이 지정된 8014 조회 결과를 사용한다. 핵심 경로는 `/workspace-api/reports`, `/workspace-api/portfolio/config`, `/api/cases` 및 연구 상세다. 초기 공개판의 `/public-api/` 경로도 호환용으로 제공한다. 검색·필터는 읽기 요청이며 게시·삭제·설정 변경·작업 실행과 WebSocket 연결은 공개 서버가 차단한다.

1. Windows의 기존 named tunnel 설정은 `%LOCALAPPDATA%\TradingAgentsDeploy\tunnel.yml`에 있다. 변경 전에 현재 설정을 접근 제한된 런타임 폴더로 백업한다. 관리 호스트 규칙의 `originRequest.access.required: true`, 팀 `daehun-forecast-lab` 및 Access 앱의 실제 `audTag`를 유지한다. 기존 정책은 승인 이메일 하나 및 일회용 코드 로그인으로 보호한다.
2. 위 표의 호스트를 각각 정확히 지정한다. 공개 규칙은 오직 8015를 향하고 마지막 미일치 규칙은 `http_status:404`다. 공개·운영 연구 호스트의 DNS는 모두 기존 터널을 가리키는 프록시된 CNAME이다. 최초 등록은 Cloudflare DNS 관리 화면 또는 도메인 관리 권한이 있는 환경의 `cloudflared tunnel route dns <터널> research.daehun.app`에서 한다. 일상적인 Windows 기동에는 DNS 관리용 인증서가 필요하지 않다.
3. 로컬 준비 상태와 공개 상세를 확인한 뒤 `cloudflared tunnel --config <후보 파일> ingress validate`와 각 호스트의 `ingress rule`을 확인한다. 활성 파일에 후보를 원자적으로 반영하고 같은 구성 경로로 새 커넥터를 시작한다. 새 프로세스에서 등록 로그를 확인한 뒤 실행 경로와 PID를 확인한 이전 커넥터만 종료한다. **TradingAgents Windows Deployment** 작업은 기존 사이트와 터널, **TradingAgents Forecast Lab** 작업은 8014와 8015를 기동한다.
4. 새 브라우저로 공개 홈과 실제 상세를 열고, 공개 호스트의 리포트·포트폴리오 조회가 200이고 내부 실행 이벤트가 404인지 확인한다. 공개 경로의 쓰기 차단은 격리 테스트에서 확인한다. 익명으로 운영 호스트에 접속하면 팀의 `cloudflareaccess.com`으로 이동하며 기존 `daehun.app/api/health`는 200이어야 한다.
5. 공개를 중단해야 하면 공개 호스트 규칙을 제거하고 새 커넥터를 등록한 뒤 이전 커넥터를 종료한다. 그 도메인은 마지막 404 규칙을 사용한다. 공개 앱만 다시 시작할 때는 8015 소유 프로세스의 체크아웃과 모듈을 검증한 뒤 전용 기동 스크립트 `scripts/start-forecast-lab-public.ps1`를 실행한다. 프라이빗 운영 앱과 DB는 계속 동작한다.

프런트엔드 변경 시 8014와 8015가 동일한 새 해시 파일을 쓰도록 assets를 먼저 복사하고 index.html을 마지막에 교체한다. API가 변경되면 연구 및 가상매매 워커가 유휴 상태일 때 두 서비스의 프로세스 ID와 체크아웃을 확인한 뒤 재기동한다. 새 브라우저로 공개 대시보드, 종목 리포트, 포트폴리오, 예약, 연구 사례와 성과 탭을 점검한다.

2026-11-24 배포 후 로그인 없는 외부 Chrome 393px·1440px에서 대시보드, 코카콜라 리포트 본문, 보유·포트폴리오, 예약·회고, 29번 예측 상세와 성과를 조회했다. 운영 조회 경로와 대조한 최근 리포트 20건의 분석 본문 260개가 일치했다. 공개 조회 API는 200, 쓰기 메서드는 405, 내부 실행 이벤트는 404였다. 검증 시점에 포트폴리오 계좌가 설정되지 않아 해당 화면은 빈 상태였다. 관리 호스트의 익명 접속은 Cloudflare Access 인증으로 연결된다.

### Windows에서 실행

Windows PowerShell에서 해당 프로젝트를 열고 다음을 실행한다.

```powershell
Set-Location 'C:\Users\samda\dev\TradingAgents-ForecastLab'
uv sync --frozen
codex login status
Push-Location apps/web
try {
    npm ci
    if ($LASTEXITCODE) { throw '프런트엔드 의존성 설치 실패' }
    $env:VITE_FORECAST_LAB = '1'
    $env:VITE_API_BASE_URL = '/workspace-api'
    npm run build
    if ($LASTEXITCODE) { throw '통합 프런트엔드 빌드 실패' }
} finally {
    Remove-Item Env:VITE_FORECAST_LAB,Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}
.\scripts\start-forecast-lab-services.ps1
Invoke-RestMethod http://127.0.0.1:8015/healthz
Invoke-RestMethod http://127.0.0.1:8014/ready
Invoke-RestMethod http://127.0.0.1:8014/api/status
Invoke-RestMethod http://127.0.0.1:8014/workspace-api/health
```

작업 스케줄러의 **TradingAgents Forecast Lab**은 같은 사용자 로그온 시, 그리고 로그인 중 15분마다 이 시작 스크립트를 호출한다. 수동 기동·준비 상태 점검 명령은 `Start-ScheduledTask -TaskName 'TradingAgents Forecast Lab'`이다. 스크립트는 전용 pgdata와 포트 소유를 확인한 후 필요한 프로세스를 시작한다. 이미 실행 중인 연구 앱은 계속 동작한다. 현재 사용자 로그인과 Codex 로그인 상태가 필요하다. 연구 HTTP API는 조회용이고, 가상매매 콘솔의 쓰기에는 전용 관리자 인증이 필요하다. 공개 앱 로그는 `logs/public.err.log` 및 `logs/public.out.log`다. 운영 앱 오류는 런타임의 `logs/app.err.log`, 진행 상태는 `scan-progress.json`과 `/api/status`에서 확인한다.

백그라운드 스캔은 시작 직후와 한 차례 스캔이 끝난 뒤 지정된 간격(현재 900초)에 다시 돈다. 시장별로 완료된 거래 세션과 다음 개장 시각을 확인한다. 장중에 이미 열린 진입 창은 건너뛴다. 독립 프로세스가 동시에 실행되면 PostgreSQL 잠금을 획득한 하나만 무거운 작업을 한다. 최초 며칠 동안 성과 공통 표본이 비어 있고 기억 방법이 보류되는 것이 정상이다.

대시보드의 사례 수는 입력을 동결해 DB에 기록한 사례 수다. 사전 입력 검증에서 탈락한 티커나 이미 개장한 시장은 현재 스캔의 보류 사유에서 확인한다. 백테스트로 빈 날짜를 채우지 않는다. 날짜 필터는 시장 현지의 데이터 기준일을 사용하고, 화면의 발행·개장·만기 시각은 한국시간(KST)으로 표시한다.

## 콘솔의 데이터와 권한

브라우저에서 `/#/research`는 연구, `/#/`는 대시보드, `/#/portfolio`는 포트폴리오, `/#/schedules`는 가상매매 분석 예약이다. `/research/`는 연구 단독 보기다. `/api/`는 전향 연구, `/workspace-api/`는 이 앱의 가상매매 REST·WebSocket 경로다. 연구의 관찰 티커와 콘솔의 분석 예약은 주기와 용도가 다르다. 8014 콘솔의 변경은 별도 DB에 저장한다.

화면 배포 때는 Svelte 번들과 연구실 정적 파일을 함께 확인한다. Svelte는 파일명 해시로 버전을 구분한다. 연구실 CSS·JS·공통 스타일을 바꾸면 연구실 HTML의 해당 자산 URL에 붙은 `v` 값을 갱신한다. 공통 스타일 URL은 Svelte 진입점에도 있으므로 같은 버전을 지정한 뒤 빌드한다. 8014에서 연구 사례의 종가 차트, 리포트 본문, 모바일 전체 메뉴를 열고 외부 호스트가 Cloudflare Access로 연결되는지 확인한다.

보유 종목·거래 상세·매매 검증의 레이아웃을 변경했을 때는 저장소 루트에서 `.\.venv\Scripts\python.exe scripts/check-forecast-review-layout.py apps/web/dist`를 실행한다. 배포 전에는 마지막 인수로 빌드한 후보 폴더도 인자로 쓸 수 있다. 이 검사는 Chrome에서 로컬 검증 자료를 열어 빈 목록과 기록이 있는 목록, 한국어 버튼과 건수의 실제 줄 위치를 확인한다. `--screenshots <폴더>`를 붙이면 화면 캡처도 저장한다.

처음 통합할 때 기존 운영 DB의 읽기 전용 스냅샷을 비어 있던 콘솔 DB로 한 번 복원했고 15개 테이블의 행 수를 대조했다. 이 시점에 분석 예약 24개, 실제 리포트 2개, 예약 실행 기록 3개, 포트폴리오 계좌 0개였다. 이후에는 각 DB가 독립적으로 누적된다. 이전 콘솔의 리포트·거래는 연구실 Brier 점수의 표본에 포함되지 않는다. 최초 계좌의 통화·자본은 포트폴리오 화면에서 설정한다.

새 PC에서는 `forecast_lab_console_app`을 전용 비관리자 로그인 역할로 만들고 이 역할이 소유한 `forecast_lab_console`을 준비한다. 접근을 제한한 런타임 디렉터리의 `console.env`에 `FORECAST_LAB_CONSOLE_DSN`(호스트 127.0.0.1, 포트 55434, 전용 역할과 DB)과 이 콘솔만의 `TRADINGAGENTS_ADMIN_TOKEN`을 둔다. 콘솔 캐시와 벡터 저장소는 런타임의 `console` 아래에 둔다. 새 설치 시 전용 콘솔 백업이 있으면 해당 덤프를 복원한다.

예약·가상계좌를 변경할 때는 8014의 ‘관리자 인증’에 **콘솔 전용** 토큰을 입력한다. 이 PC의 Windows 사용자 세션에서 아래 명령으로 값을 화면에 출력하지 않고 클립보드에 복사할 수 있다. 입력 후 클립보드를 비운다.

```powershell
$consoleEnv = Join-Path $env:LOCALAPPDATA 'TradingAgentsForecastLab/console.env'
$entry = Get-Content -LiteralPath $consoleEnv | Where-Object { $_ -like 'TRADINGAGENTS_ADMIN_TOKEN=*' }
Set-Clipboard -Value $entry.Substring('TRADINGAGENTS_ADMIN_TOKEN='.Length)
```

## 연구 대상과 수동 검증

`forecast_lab/classification.py`의 등록 분류는 `/api/status`에서 먼저 확인할 수 있다. 새 사례에서는 가격 공급자가 확인한 상품 유형에 맞춰 정책 버전과 분류를 동결한다. 신규 티커·사업 재편·ETF 추종 대상 변경을 반영할 때는 근거를 확인해 카탈로그와 분류 버전을 갱신하고 한글 표시명을 함께 점검한다. 미분류 사례도 발행하며 다른 종목과의 전이에는 일치하는 분류가 필요하다. 기초자산 구분의 예시는 운용사가 명시한 금, 은, 미국 물가연동 국채다. [GLD](https://www.ssga.com/us/en/individual/etfs/spdr-gold-shares-gld) · [SLV](https://www.ishares.com/us/products/239855/ishares-silver-trust-fund) · [SCHP](https://www.schwabassetmanagement.com/products/schp)

배포 직후 `/api/stats`의 `sector_coverage`에서 대상과 비교 완료 건수를 확인한다. 기존 사례의 종목명이 오늘의 관찰 목록에 있어도 과거 스냅샷의 정책은 유지한다. 상세에서 `same_memory`는 기존 검색과 같은 기억 선택, `no_eligible_sector_memory`는 근거 부족을 뜻한다. 두 상태 모두 별도 모델 호출을 생략한다. `sector_by_basis`는 실제 채점 쌍을 동일 종목·동종 주식·같은 노출의 ETF로 나눈다. 과거 사례를 재현할 때는 별도 인수 DB를 사용한다.

통합 앱의 종목 이름은 콘솔의 `/workspace-api/tickers/names`에서 조회한다. 기본 관찰 종목과 시장 기준 종목 이름은 `packages/tradingagents/forecast_lab/web/instrument-names.json`에도 있어 단독 연구 화면에서 사용할 수 있다. 기본 이름을 갱신할 때는 이 파일과 콘솔 번들을 함께 배포하고 연구 스크립트가 불러오는 카탈로그 URL의 버전을 갱신한다. 이름 표시는 예측 사례나 관찰 티커를 수정하지 않는다.

초기 목록은 기존 24개 예약 중 주식·ETF 23개(한국 10개, 미국 13개)다. 비트코인은 주식 거래소 달력 실험에서 제외했다. 이후 연구 목록은 연구실에서 독립 관리한다. 티커 등록은 다음 형식으로 실행한다.

```powershell
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app seed --us WMT KO --kr 316140.KS
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app run-once --limit 1
```

`run-once`는 실제 발행이 가능한 경우 실제 연구 사례를 생성한다. 과거 시점 시뮬레이션과 장애 주입은 별도 검증 DB에서 실행한다. 프로젝트에는 접속 문자열을 커밋하지 않는다. PowerShell 7에서 전체 검증을 실행하는 예는 다음과 같다.

```powershell
$env:PG_TEST_BINDIR = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin'
$acceptance = Join-Path $env:LOCALAPPDATA 'TradingAgentsForecastLab/acceptance.env'
$line = Get-Content -LiteralPath $acceptance | Where-Object { $_ -like 'FORECAST_LAB_DSN=*' }
$env:FORECAST_LAB_ACCEPTANCE_DSN = $line.Substring('FORECAST_LAB_DSN='.Length)
try { .\.venv\Scripts\python.exe -m unittest discover -s tests -q }
finally { Remove-Item Env:FORECAST_LAB_ACCEPTANCE_DSN -ErrorAction SilentlyContinue }
```

## 이전·백업·장애 복구

- 같은 Windows 사용자의 접근 제한 디렉터리에 `lab.env`와 `acceptance.env`를 분리해 보관한다. 운영값은 연구 DSN, 모델, 스케줄러 활성 플래그, 스캔 간격, 외부 비교 활성 플래그다. 검증의 `FORECAST_LAB_STATE_DIR`도 분리한다.
- 새 PC에서는 별도 pgdata를 `initdb --auth=scram-sha-256 --encoding=UTF8`로 생성하고 loopback 55434로 구동한다. 전용 로그인 역할을 만든 뒤 연구·검증 DB만 소유하게 한다. `lab.env`에는 `FORECAST_LAB_DSN=postgresql://forecast_lab_app:<전용 암호>@127.0.0.1:55434/forecast_lab_research`를 설정한다. 검증 DSN은 동일 형식으로 별도 DB명을 사용한다. 실행 전 두 설정의 접근 권한과 포트를 확인한다.
- 연구 백업은 PostgreSQL custom dump 형식(`pg_dump -Fc`)으로 생성하고 `pg_restore -l`과 읽기 검증을 수행한다. 연구 원본에 복원하기 전에 별도 빈 연구 DB에서 사례 수·방법별 발행 수·만기 결과·기억 수가 일치하는지 확인한다. 기존 공개 서비스의 DB 리셋·백업 스크립트는 기존 서비스 전용이다.
- 앱 코드를 교체할 때는 `/api/status`에서 활성 분석을 확인한다. 8014 리스너가 이 체크아웃의 `tradingagents.forecast_lab.app`인 것을 확인한 후에만 해당 프로세스를 재시작한다. PostgreSQL은 계속 실행해도 된다. 다시 시작하면 이미 발행된 확률은 재발행하지 않고, 개장 전 남은 방법을 처리한다.

### 자동 작업과 복원 확인

두 Windows 작업은 현재 사용자, 대화형 로그온, 일반 권한으로 등록되어 있다. 기동 작업은 Windows PowerShell을 숨김 모드로 실행하며 인수는 `-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "C:\Users\samda\dev\TradingAgents-ForecastLab\scripts\start-forecast-lab-services.ps1"`이다. 트리거는 사용자 로그온과 15분 간격의 반복이다. 앱 내부 스캔과 별개로 프로세스 종료에서 복구한다. 시장 공급자 조회 한 번은 60초, 모델 응답 한 번은 최대 300초로 제한한다. 개장이 더 가까우면 남은 시간이 모델 호출의 상한이다.

**TradingAgents Forecast Lab Backup**은 매일 03:25 KST에 이 체크아웃의 `.venv\Scripts\python.exe`로 `scripts\backup-forecast-lab.py`를 실행한다. 수동 실행은 프로젝트 루트에서 `.\.venv\Scripts\python.exe scripts\backup-forecast-lab.py`다. 연구·콘솔 DB를 별도 덤프로 만들고 각각 전체 아카이브를 읽어 검증한 파일만 `%LOCALAPPDATA%\TradingAgentsForecastLab\backups\*.dump`에 저장한다. 이 백업은 연구 DB와 동일한 PC에 있다. 디스크 자체의 장애에 대비하려면 검증된 덤프를 다른 저장소에도 보관한다.

복원 검증 시 연구 클러스터에 새 이름의 빈 DB를 만들고 앱 역할을 소유자로 지정한다. 연구실 접속 환경에서 `pg_restore --single-transaction --exit-on-error -d <새 검증 DB명> <덤프 경로>`로 복원한다. `lab_watchlist`, `lab_cases`, `lab_arms`, `lab_outcomes`, `lab_memories`의 건수와 알려진 완료 사례의 발행 시각·확률을 비교한다. 마지막으로 확인한 실제 복원 결과는 [설계 인수 기록](DESIGN.md)에 있다.
