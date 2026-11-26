# GANT v3 Windows 개발 운영

| 구성 | v3 위치 |
|---|---|
| 소스 | C:\Users\samda\dev\TradingAgents-V3 · codex/gant-v3 |
| 런타임 | %LOCALAPPDATA%\TradingAgentsV3 |
| 운영 데이터 | v2 PostgreSQL 55434의 연구·매매 데이터와 v2 콘솔 8014의 공개 조회 API |
| 보조 출처·검증 | v3 PostgreSQL 55436, 독립 pgdata · v3 실험 기록과 아카이브 보존 · 별도 acceptance DB |
| v3 읽기 전용 서버 | 127.0.0.1:8024 내부 조회 · 127.0.0.1:8025 공개 뷰어 |
| 외부 운영 | [v3 읽기 전용 프리뷰](https://v3.daehun.app/) · [v2 메인](https://daehun.app/) · [v2 기존 공개 주소](https://research.daehun.app/) · [v2 관리자](https://lab.daehun.app/) |

예측·모의매매·학습·채점의 실행 주체는 v2다. v3의 두 웹 서버는 읽기 전용이다. 관측 현황에 표시되는 스케줄러 상태와 분석 예약 목록도 v2의 것이다. v3 설치 앱은 ‘리포트’로 시작한다. 좌측 상단 GANT 로고는 대시보드를 연다.

## 개발 도구

현재 Windows 사용자에 설치한 Impeccable은 화면 설계와 실제 렌더링 점검에, last30days는 출처를 수동으로 조사할 때 사용한다. Codex 사용자 스킬은 %USERPROFILE%\.codex\skills 아래에 있다. last30days 4.6.0은 Python 3.12 이상으로 실행한다.

예약 종목의 자동 검색은 별도의 고정된 last30days 실행본을 사용한다. v2의 예약 프로그램이 수집기를 호출하고, v3의 읽기 전용 웹 서버는 발행 시점까지 저장된 자료를 조회한다. 검색기·전용 Python 설치, 중복 방지, 실패 상태 점검은 [이슈 수집 운영](ISSUES.md)의 예약 수집 절차를 따른다.

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

기존 PC는 아래 **공유 뷰어 기동**으로 진행한다. 새 PC에 빈 v3 실험 클러스터와 검증 DB가 필요할 때만 아래 초기화 명령을 사용한다. 기존 기록은 해당 버전의 백업으로 복원한다. v2 운영 서비스와 PostgreSQL은 v2 런치패드를 따른다.

~~~powershell
.\.venv\Scripts\python.exe scripts/initialize-v3-runtime.py
~~~

## 공유 뷰어 기동

v2의 `TradingAgents Forecast Lab` 예약 작업이 8014 운영 콘솔과 8015 공개 뷰어를 관리한다. `TradingAgents V3 Preview`는 사용자 로그온 시와 15분 간격으로 v3의 웹 프로세스와 보조 아카이브 DB를 확인한다. Cloudflare의 `TradingAgents Public Tunnel`은 v2 체크아웃에서 관리하며 v3 호스트는 8025로 연결된다.

공유 모드를 처음 설정할 때 두 클러스터가 기동된 상태에서 아래 명령으로 제한된 조회 역할과 로컬 설정을 만든다. 이미 설정된 PC에서 같은 명령을 다시 실행할 수 있다. 비밀번호는 보호된 런타임 내부에만 보관한다. 8024만 이 읽기 전용 설정을 사용한다. 8025는 허용된 조회 경로만 제공한다.

~~~powershell
.\.venv\Scripts\python.exe scripts/provision-v3-shared-reader.py
$marker = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/shared-viewer.enabled'
if (!(Test-Path -LiteralPath $marker)) { New-Item -ItemType File -Path $marker }
~~~

이전 독립 모드가 실행 중인 PC의 최초 전환에서는 v3 연구 상태가 유휴 상태이고 매매 대기열이 비어 있는지 먼저 확인한다. 8024의 v3 `lab.env … serve --console`, 8025의 v3 `public_app:app`을 명령줄·loopback 주소로 식별한 후 각 이전 리스너를 종료하고 아래 명령을 실행한다. 이후 재기동은 같은 명령만 사용한다.

~~~powershell
.\scripts\start-forecast-lab-services.ps1
Invoke-RestMethod 'http://127.0.0.1:8024/healthz'
Invoke-RestMethod 'http://127.0.0.1:8025/healthz'
Invoke-RestMethod 'http://127.0.0.1:8025/ready'
~~~

`/healthz`의 source는 v2, role은 각각 core와 edge여야 한다. `/ready`는 v2 연구 상태를 조회한다. 공개 원본이 중단되면 v2 서비스와 8014를 확인한다. 출처만 실패하면 v3 55436과 `logs/shared-core.err.log`를 확인한다. 8024·8025를 재기동해도 예약이나 모델 실행이 생성되지 않는다. 원본 DB 백업은 v2 체크아웃에서 관리하고, v3 아카이브는 v3 체크아웃의 `scripts/backup-forecast-lab.py`로 백업한다.

### 격리된 개발 실험

아래는 별도 실험 DB에서 모델과 수집기를 검증하는 예시다. 운영 뷰어 배포 명령은 위의 공유 뷰어 기동으로 끝난다.

~~~powershell
$labEnv = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env'
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app --env-file $labEnv seed --us NVDA WMT KO --kr 316140.KS
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.issue_collector --env-file $labEnv
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.app --env-file $labEnv run-once --limit 1
~~~

run-once는 실험 DB에 실제 모델 예측을 발행한다. 채점에는 다섯 번째 거래일의 관측이 필요하다. 별도 아카이브 수집 방법은 [수집 운영 문서](ISSUES.md)에 있다.

## 검증

### 리포트·연구의 출처 목록 · gant-v3-preview.9

프런트엔드 정적 번들만 갱신한다. 배포 후 월마트 리포트 3회차에서 첫 기사와 ‘뉴스 40건’ 제목 행을 확인한다. 제목 행을 누르면 나머지 기사가 펼쳐지고 다시 누르면 첫 기사로 돌아간다. 조사 자료가 한 건인 그룹은 원문을 바로 열 수 있다. 엔비디아 연구 사례 #55에서는 뉴스와 last30days 두 그룹을 따로 조작해 한쪽을 접어도 다른 쪽이 열린 상태를 유지하는지 확인한다.

### 종목별 예측 회차와 공개 조회 캐시 · gant-v3-preview.8

v3 내부 조회 서버(8024)를 먼저 갱신하고 공개 뷰어(8025)를 갱신한다. 두 포트의 `/ready`와 `/api/forecast-tickers`를 확인한 뒤 후보의 정적 번들과 `gant.webmanifest`를 게시한다. 기존 v2 조회 계정으로 발행된 예측을 읽으므로 DB 마이그레이션이나 스케줄러 재시작은 필요하지 않다.

운영 데이터 대조 시 v2의 발행 사례를 마지막 페이지까지 조회해 종목별로 묶는다. v3 예측 디렉터리의 종목, 최신 관측일과 사례 ID가 일치해야 한다. 같은 날 발행된 예측의 순서는 사례 ID로 정한다. 해당 종목 상세의 ‘예측 회차’에는 최신부터 첫 발행까지 표시하며, 선택한 회차를 직접 열거나 브라우저로 뒤로 가도 동일한 예측이 열린다.

공개 조회의 기본 보관 시간은 4시간이다. 호스트 전용 쿠키 `gant_read_cache`는 캐시 식별자이며, 리포트 본문과 예측 기록은 브라우저 로컬 저장소에 보관한다. 만기 대기 중인 사례 상세는 다음 진입·만기 시각이 먼저 오면 그때 만료된다. 수동 새로고침은 브라우저 캐시를 건너뛴다. 상태·대기열·보유 자산 조회와 인증 요청은 이 캐시를 사용하지 않는다. 저장소 이용이 제한된 브라우저도 서버에서 자료를 조회할 수 있다.

2026-11-26 배포 시 운영 사례 65건과 디렉터리 21종목을 대조했다. 공개 주소에서 320·393·1440px로 SK하이닉스의 4개 회차와 엔비디아의 3개 회차를 열었다. 같은 날 발행한 SK하이닉스 1·2회차도 각각 해당 사례로 연결됐다. 새로 연 페이지는 이미 조회한 회차 목록을 재사용했고, 수동 갱신은 새 요청을 보냈다. 모바일 스와이프와 취소, 화면 중앙 로딩 중 검색, 서비스 워커가 활성화된 상태에서의 새로고침과 저장소 차단 환경도 검증했다. Windows 자동 테스트 163건과 프런트엔드 테스트 9건이 통과했다.

### 리포트 탭과 모바일 대시보드 · gant-v3-preview.7

프런트엔드 번들만 교체한다. 공개 `/#/reports`를 새로 열면 첫 번째 ‘분석 리포트’ 탭에 매매 분석이 표시되고 예측 목록 요청은 0건이다. `/#/reports?tab=forecast`에서는 확률 예측을 읽고 오른쪽 위 아이콘으로 갱신한다. 사례 상세에서 뒤로 가면 예측 탭으로 복귀한다. 320·393·768·1440px 공개 화면에서 탭 전환, 갱신 실패와 재시도, 모바일 하단 중앙 대시보드 위치를 검증했다.

### 예약 last30days · gant-v3-preview.6

v2 코드 `01947b0`과 v3 수집기를 함께 배포했다. 운영 v2 예약 콜백으로 엔비디아 검색을 동시에 두 번 호출했을 때 수집 실행 #27 한 건에 적격 자료 7건이 기록됐다. 우리금융지주 실행 #28은 3건이었다. 두 종목 모두 즉시 재호출 시 같은 수집을 재사용했다. 기존 사례 #35와 매매 리포트 #1286에는 두 기록이 소급 표시되지 않았다. 연동 검증에서 분석·매매 예약을 추가로 발행하지 않았다.

v2 운영자의 `/ready`, `/api/status`와 v3의 읽기 전용 상태, 두 화면의 분석 예약 24개를 대조한다. 작업을 되돌릴 때는 v2 런타임의 `GANT_LAST30DAYS_COLLECTOR_ROOT` 한 줄을 제거하고 유휴 상태에서 8014만 다시 기동한다. 아카이브에 이미 확보한 자료는 계속 읽을 수 있다.

### 공유 뷰어 · gant-v3-preview.5

2026-11-26 KST에 두 공개 주소를 대조했다. 예측 사례 52건, 24개 종목의 매매 분석 리포트 48건, 분석 예약 24개가 일치했다. 사례 #52 SK이노베이션의 단일 모델 29.0%와 토론 모델 40.0%는 목록·상세·v2 발행값이 동일했고, 리포트 #1286 우리금융지주의 3회차 본문을 모바일과 데스크톱에서 열었다. 이 수치는 전환 시점의 기록으로 이후에는 최신 v2 응답과 대조한다.

외부 Chrome에서 320·393·768·1440px로 홈 진입, 로딩 표시, 공개 열람등, 새로고침 중 중복 입력 방지, 설치 매니페스트와 아이콘을 검증했다. 모바일 메뉴는 오른쪽 스와이프와 바깥 탭으로 닫히고 세로 스크롤 중에는 열려 있었다. 대표 화면 14개를 모바일·데스크톱에서 열어 콘솔 오류·HTTP 오류·가로 넘침을 확인했다. Windows 기동 작업을 반복해도 두 버전의 리스너 PID가 유지됐고 v3의 이전 실행 콘솔 프로세스는 0개였다.

이번 릴리스에서 Windows 자동 테스트 155건과 프런트엔드 단위 테스트 2건이 통과했고 Svelte 검사에서 오류와 경고는 0건이었다.

### 자동 검사

~~~powershell
$env:PG_TEST_BINDIR = Join-Path $env:LOCALAPPDATA 'TradingAgentsDeploy/pgsql/bin'
$env:FORECAST_PUBLIC_UI_DIST = (Resolve-Path apps/web/dist).Path
$line = Get-Content (Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/acceptance.env') | Where-Object { $_ -like 'FORECAST_LAB_DSN=*' }
$env:FORECAST_LAB_ACCEPTANCE_DSN = $line.Substring('FORECAST_LAB_DSN='.Length)
try { .\.venv\Scripts\python.exe -m unittest discover -s tests -v }
finally { Remove-Item Env:FORECAST_LAB_ACCEPTANCE_DSN -ErrorAction SilentlyContinue }
~~~

브라우저 검증에는 Windows Chrome 설치가 필요하다. 별도 경로를 사용하면 CHROME_BIN에 실행 파일을 지정한다. 프런트엔드 검사와 단위 테스트는 apps/web에서 `npm run check`와 `node --test tests/api-cache.test.mjs tests/research-markdown.test.mjs tests/public-reads.test.mjs`를 실행한다. 수집·채점 회귀는 검증 DB 또는 별도 임시 PostgreSQL에서 수행한다.

## 첫 Windows 프리뷰 검증 · 2026-11-25 KST

새 DB에서 관찰 종목 23개를 대상으로 RSS 수집을 실행해 모든 종목에서 적격 기사를 받았다. 개발용 last30days는 Hacker News 검색으로 실제 결과 3건을 내보냈고 수집 명령에서 별도로 가져왔다. 수집 결과는 저장 당시의 검색 범위에 의존한다.

첫 실제 사례는 NVDA #1이다. 11월 24일 미국 거래일 자료로 기준선·단일 모델·토론 확률을 발행했다. 첫 토론 시도는 시간 제한으로 실패했다. 같은 사례의 동결된 근거로 재시도해 토론 결과를 저장했고 기존 단일 모델 결과를 유지했다. 만기 전에는 두 가격 조건이 대기이고, 사용할 수 있는 성숙 기억이 없어 기억 실험 두 가지는 건너뛰었다. 최신순 이슈 40건을 보관했다. 만기 예정은 12월 3일 06:00 KST다.

앞 문단의 #1은 최초 실험 클러스터의 번호다. 공유 뷰어에서 #1은 v2의 SK하이닉스이며, v2의 [엔비디아 사례는 #35](https://v3.daehun.app/#/research/35)다.

이 프리뷰는 gant-v3-preview.1 태그로 재현한다. Windows PostgreSQL과 Chrome을 사용한 전체 테스트 142건, 프런트엔드 단위 테스트 2건이 통과했고 Svelte 검사에서 오류·경고가 0건이었다. 아래 두 가지 동작도 실행 중인 인스턴스에서 확인했다. 8024·8025에서 같은 NVDA 사례의 기준선·단일 모델·토론 결과를 읽을 수 있고, 8025의 쓰기 요청은 HTTP 405로 차단된다.

## 통합 콘솔의 배포와 검증

연구 사례와 분석 리포트는 같은 Svelte 앱에서 읽는다. 예측은 `/#/research/{id}`, 매매 분석은 `/#/reports/{ticker}`에서 열며, 리포트 목록은 `/#/reports`다. 기존 `/research/?case=1`, `/research/#results`, `/research/#observe` 북마크도 각각 해당 화면으로 연결된다.

운영 중에는 두 Vite 환경 변수로 후보를 별도 폴더에 빌드하고 전체 테스트의 `FORECAST_PUBLIC_UI_DIST`를 그 폴더로 지정한다. 백엔드 변경은 각 리스너가 v3 packages에서 `shared_view:build_shared_core`(8024) 또는 `shared_view:build_shared_edge`(8025)로 기동됐는지 확인한 뒤 해당 프로세스만 재시작한다. 위 공유 뷰어 기동 명령은 이미 실행 중인 정상 프로세스를 재사용한다.

기존 v3 dist의 index.html과 변경할 공개 파일을 보관한다. 후보의 해시가 붙은 JS·CSS, 매니페스트, 아이콘, 서비스 워커를 반영한 뒤 index.html을 원자적으로 교체한다. 직전 자산을 보관하면 화면만 이전 버전으로 복구할 수 있다. 공유 모드와 v2 단독 실행을 유지한 채 운영 주소에서 홈, 설치 가능 여부, 최신 사례·리포트·예약의 일치를 확인한다.

최초 통합 확인용 기록은 엔비디아 #1이다. 공개 사례 API와 PC·모바일 화면에서 시세 65거래일, 역할 토론 8개, 동결 RSS 40건, 같은 시각 기준 last30days 3건을 대조할 수 있다. 마지막 3건은 최초 동결 40건 밖에 있던 자료다. 가상매매 리포트가 없는 초기 DB에서는 두 회차의 테스트 데이터를 사용해 출처의 시간 경계, 회차 변경 및 이전 응답 처리를 검증한다.

2026-11-25에 공개한 통합 콘솔의 태그는 `gant-v3-preview.2`다. Windows에서 Python 테스트 146건, 프런트엔드 단위 테스트 2건, Svelte 타입 검사를 통과했다. 공개 주소에서 360·393·1440px로 리포트 목록부터 엔비디아 사례, 원문 목록과 발행 당시 시각, 역할별 토론, 기존 북마크까지 검증했다. 12개 공개 화면과 5개 운영자 화면에서 조회를 확인했다. 공개 서버의 쓰기 요청은 405였으며 v2의 두 공개 주소가 제공한 번들은 배포 전 해시와 일치했다.

### 흑연색 연구 콘솔 · gant-v3-preview.3

연구 사례는 실제 시세와 모델별 확률을 나란히 표시한다. 배포 확인 시 엔비디아 사례의 라인·캔들을 전환하고 거래일별 시세 표를 연다. 8024와 8025의 `/api/cases/1`에서 65거래일의 날짜·OHLC·거래량이 일치해야 한다. 이 사례의 마지막 거래량은 383,594,200주다. 공개 변환기는 소수점 아래가 0인 거래량도 주 단위 정수로 전달하며, 결측과 0을 구별한다.

연보라색 확률을 누르면 선택한 모델의 근거로 이동한다. 엔비디아 사례에서 단일 모델은 39.0%, 역할 토론은 47.0%로 기록되어 있으며 방법별 차이는 8.0%p다. 휴대폰에서 하단 전체 메뉴로 예약을 열고 기존 연구 북마크로 돌아갈 수 있는지도 확인한다. 테마와 차트 스타일은 해시가 붙은 앱 CSS에 함께 들어간다. 아이콘이 바뀌는 릴리스에서는 `favicon.svg`도 직전 파일을 보관한 뒤 교체한다.

2026-11-25 검증에서는 Windows Python 테스트 147건과 프런트엔드 단위 테스트 2건이 통과했고 Svelte 검사 오류·경고는 0건이었다. 배포 후 외부 도메인에서 360·393·768·1440px로 엔비디아의 차트, 모델 근거, 출처와 북마크를 조작했다. 두 화면 너비에서 공개 경로 12개와 데스크톱 운영 경로 5개를 확인했다. 8025 공개 쓰기 차단과 v2 양쪽 도메인의 기존 번들도 대조했다.

### 콘솔 선택창과 관측 기간 · gant-v3-preview.4

프런트엔드 정적 번들만 위 절차대로 교체한다. 공개 대시보드에서 모드와 통화의 목록을 열고, 모의계좌로 전환한 뒤 표시 통화를 바꾼다. 좁은 화면에서도 선택 항목과 체크 표시가 보여야 한다.

연구 사례 상세에서 **사례 선택 → 관측 기간**을 열고 한 날짜를 누른다. 이때는 사례 목록을 다시 요청하지 않는다. 다른 달의 날짜를 고르면 `/api/cases`에 정렬된 `from_date`와 `to_date`가 함께 전달되고, 사례 선택 창은 필터링한 결과를 보여준다. 이어 같은 날을 두 번 고르거나 기간을 초기화해 변경된 목록도 확인한다. 연구 성과·관측 현황에서는 같은 달력이 `/api/stats`의 기간을 변경한다.

2026-11-25 배포 후 공개 주소에서 320·360·393·768·1440px로 터치 또는 키보드 조작, 날짜 역순·월 경계·윤일, 초기화와 뒤로가기를 확인했다. 리포트·연구 성과·운영 인증 화면에서 27개 치수를 대조했다. 공개 경로 12개를 두 화면 너비에서 점검했고 Windows 전체 테스트 147건, 프런트엔드 단위 테스트 2건과 Svelte 검사를 통과했다.
