# TradingAgents Windows 배포 Launchpad

메인은 [v2 공개 콘솔](https://daehun.app/)이다. [v3 프리뷰](https://v3.daehun.app/)도 별도로 열려 있다. 공용 터널은 TradingAgents Public Tunnel 작업이 기동한다. v1 API·Nginx·DB와 v1 예약 작업은 중지 상태다.

[공개 콘솔](https://research.daehun.app/)과 [관리용 콘솔](https://lab.daehun.app/)은 같은 화면 번들을 사용한다. 방문자는 로그인 없이 모의계좌와 리포트를 조회하고 관리자는 이메일 인증 후 설정을 변경한다. 이 브랜치의 연구실은 전용 DB와 별도 웹 포트를 사용한다. 연구실을 시작·백업·복구하려면 [Windows 연구실 운영 문서](docs/forecast-lab/OPERATIONS.md)를 따른다. 아래 v1 이력은 복구 참고용이다.

이 저장소를 처음 여는 운영자와 LLM을 위한 배포·복구 절차다. Windows PowerShell에서 실행한다. 기준 경로는 C:\Users\samda\dev\TradingAgents다. 경로와 포트는 아래 실측값을 출발점으로 삼고 실행 직전에 다시 확인한다.

## v1 운영 기록 — 2026-11-23 KST

**Windows 단독 공개 배포 완료.** 운영 주소는 https://daehun.app 이다. 아래의 최초 이전 절차는 복구·재구축 참고용이다. 이미 운영 중인 DB에 최초 생성/복원 절차를 다시 실행하지 않는다.

| 구성 | 실제 운영 위치 |
|---|---|
| 운영 파일 | `%LOCALAPPDATA%/TradingAgentsDeploy` (현재 samda 사용자 전용, SYSTEM 접근 허용) |
| PostgreSQL | Windows x64 17.10, 포트 55432, 운영 파일 아래 `pgsql/bin`, `pgdata`, `postgres.log`. 서비스 등록 대신 현재 사용자로 pg_ctl 실행 |
| 백엔드 | 프로젝트 루트 .env, 127.0.0.1:8001, Windows 사용자 samda의 Codex 구독 인증. 실행 로그 logs/windows-api.err 및 .out |
| 프런트엔드 | VITE_API_BASE_URL=/api로 빌드. 운영 파일 아래 web-20261123-outcomes. 직전 릴리스 web-20261123-audit 보관 |
| Nginx | 운영 파일 아래 nginx-1.30.7, conf/tradingagents.conf, 127.0.0.1:18080 |
| Cloudflare | 운영 파일 아래 cloudflared.exe, tunnel.yml 및 기존 UUID 자격증명. Windows 프로세스로 구동, 로그 tunnel.err. 추가 DNS 변경 없이 공개 검증 성공 |
| 시작 작업 | Windows 작업 스케줄러 **TradingAgents Windows Deployment**. samda 로그온 트리거. scripts/start-windows-deployment.ps1가 DB → BE → Nginx → 터널을 시작한다 |
| 백업 작업 | **TradingAgents PostgreSQL Backup**, 매일 03:10 로컬 시간. 같은 사용자의 대화형 세션에서 실행, 놓친 일정은 가능해지면 실행. scripts/backup-windows-db.py가 사용자 dev/TradingAgents-backups 아래에 custom dump를 생성하고 읽기 검증. 자동 삭제 없음 |

이 구성은 관리자 권한 없이 설치했다. 재부팅 후 **samda Windows 로그인**이 필요하다. 매번 Docker/WSL을 시작할 필요가 없다. Windows 서비스 방식으로 무인 부팅하려는 경우 아래 서비스 절차와 Codex 프로필 접근을 별도 검증한다. 운영 시에는 같은 프로세스를 Windows 서비스와 로그온 작업 양쪽에 등록하지 않는다.

**실행과 복구** — 같은 계정에서 PowerShell로 `Start-ScheduledTask -TaskName 'TradingAgents Windows Deployment'` 실행 후 `Get-ScheduledTaskInfo`와 로컬/공개 health, WSS 첫 메시지를 확인한다. 배포 작업은 로그온 시 시작하거나 수동 실행하는 시작기다. 프로세스 하나가 중단되면 같은 작업을 재실행한다. FE 변경 시 새 dist를 별도 릴리스 폴더로 복사하고 실제 conf/tradingagents.conf의 root를 바꾼 뒤 같은 설정 파일을 명시해 nginx -t 및 reload한다. 백업은 `Start-ScheduledTask -TaskName 'TradingAgents PostgreSQL Backup'`으로 즉시 실행할 수 있다. 덤프는 같은 PC에 보관되므로 PC 자체 장애에 대비하려면 별도 보관처가 필요하다.

**인수 검증 기록** — 기존 Docker DB를 정지하기 전 Windows DB와 14개 public 테이블별 행 수 및 최신 리포트/작업 ID가 일치했다. 리포트 1238건, 거래 371건, 작업 1403건, 최신 GOOGL 리포트 1238 / 작업 1395 / 67회차. 원본 덤프는 `C:/Users/samda/dev/TradingAgents-backups/20261123-214526/tradingagents_dev.dump`. 이전 .env는 운영 파일 아래 env-before-native. 원래 Docker DB는 중지하고 볼륨을 보존했다. 운영 DB 첫 예약 작업 수동 백업은 20261123-214734. Windows 스택을 전부 정지한 뒤 로그온 작업을 수동 실행해 재기동과 공개 리포트 응답을 검증했다. PC 전체 재부팅은 수행하지 않았다.

2026-11-23 22:04 KST 감사 릴리스. 수정·검증 내역은 [코드 감사 보고서](docs/CODE_AUDIT.md)에 있다. 운영 관리자 토큰은 교체됐으며 프로젝트 .env에서 관리한다. 이전 환경 파일을 원복할 때 현재 관리자 토큰을 보존한다. DB 자격은 별도 관리한다. 개발은 .env.dev.example을 .env.dev로 복사해 개발 전용 자격을 설정한다. 운영 API 8001과 별도로 개발 API는 8011을 사용한다.

### 종목별 교훈 효과 평가 릴리스

운영 LLM은 `codex login`으로 연결한 ChatGPT 구독을 사용한다. 선택형 Google 공급자의 새 로그인·토큰 갱신에는 해당 공급자의 `*_CLIENT_ID`와 `*_CLIENT_SECRET`을 로컬 환경에 설정한다. 변수 이름은 `.env.example`에 있다.

- Windows 체크아웃의 배포 브랜치는 `dev`다. 잠금 파일 기준으로 `uv sync --frozen`을 실행한다. 운영 DB에 연결한 기존 API에서 `GET /queue`가 비었는지 확인하고 `.venv\Scripts\python.exe scripts/backup-windows-db.py`로 덤프를 검증한다. 이번 배포 직전 덤프는 `TradingAgents-backups/20261123-230953-jfz3gyq6/tradingagents_dev.dump`다.
- 8001 리스너와 부모 프로세스가 이 프로젝트의 uvicorn인지 확인하고 API만 재기동한다. 로그온 작업으로 시작하면 스케줄러 초기화가 관측 테이블 `rag_outcome_evaluations`와 조회 뷰 `rag_outcome_scores`를 생성한다. 스케줄러는 시작 시와 매일 16:10 한국시간에 평가한다. 운영 최신 로그에서 `Lesson outcome evaluation`을 확인한다. 새 판단 쌍이 없거나 아직 평가 기간이 지나지 않았으면 0건이 정상이다.
- FE는 새 릴리스 폴더를 준비한 뒤 Nginx 설정의 `root`를 교체하고 해당 설정으로 `nginx -t`, `nginx -s reload`를 실행한다. 공개 `/api/health`, 기존 리포트 조회, 대시보드 채점 기준 열기·닫기와 새로고침 후 동작까지 점검한다. 브라우저는 빌드된 JS 경로를 `/sw.js?build=…`에 넣어 해당 버전의 서비스 워커를 등록한다. 공개 HTML의 JS 파일명과 로컬 dist가 같은지 확인한다.
- 화면을 원복할 때는 Nginx의 `root`를 직전 폴더로 되돌리고 설정 검사 후 reload한다. 백엔드를 원복할 때는 직전 배포 소스와 당시 잠금 파일을 준비하고 같은 계정·운영 환경으로 API를 재기동한다. 추가한 관측 테이블과 뷰는 그대로 보존할 수 있다.

## 이전 전 상태와 최초 구축 계획 (이력)



2026-11-23 KST에 확인한 상태다. **로컬 앱 실행은 완료, WSL 독립 및 공개 배포는 미완료**다.

| 구성 | 인수 시점 | WSL 없는 목표 |
|---|---|---|
| DB | Docker Desktop, WSL2 커널, PostgreSQL 17, tradingagents-postgres-dev, localhost:5433, DB tradingagents_dev, 볼륨 infra_tradingagents_pgdata_dev | Windows PostgreSQL 17 서비스, loopback:55432, 같은 DB 이름·소유자 |
| 별도 과거 DB | tradingagents-postgres, 포트 5432, 볼륨 tradingagents_tradingagents_pgdata. 과거 백업 별도 보관 | 보존용. 앱 연결 대상은 tradingagents_dev |
| BE | Windows Python 3.11, uv, FastAPI, 127.0.0.1:8001, .env, 내부 스케줄러 | 동일. Windows 작업 스케줄러로 한 인스턴스 실행 |
| AI | 공식 openai-codex SDK, Windows 사용자의 ChatGPT 로그인 | 같은 사용자 프로필에서 실행 |
| FE | Windows Vite 개발 서버 5174 | npm 빌드 산출물을 Windows Nginx가 제공 |
| 프록시 | Ubuntu Nginx가 8080 사용, 과거 upstream 8000 | Windows Nginx 127.0.0.1:18080 → 8001 |
| 외부 접속 | 기존 locally-managed named tunnel tradingagents, daehun.app. 이전 점검 시 커넥터 중지 | Windows cloudflared 서비스 → 127.0.0.1:18080 |

55432와 18080은 기존 서비스와 나란히 검증하기 위한 **제안 포트**다. Windows 11 Home에서 현재 Docker 엔진은 실제로 microsoft-standard-WSL2를 사용한다. 이 문서의 목표 구성은 Windows용 PostgreSQL로 데이터를 논리 복원하므로 일상 배포 시 Ubuntu, Docker Desktop, WSL 명령이 필요 없다.

## 1. 점검 및 원본 보존

~~~powershell
Set-Location C:\Users\samda\dev\TradingAgents
git status --short
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 5432,5433,55432,5174,8001,8080,18080
docker context show
docker info --format '{{.KernelVersion}}'
docker inspect --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{end}}' tradingagents-postgres-dev
Get-Service | Where-Object Name -match 'postgres|cloudflared'
codex login status
Invoke-RestMethod http://127.0.0.1:8001/queue
~~~

이 절차에서 Docker 명령은 최초 데이터 인수와 원복 때만 사용한다. 기존 컨테이너가 중지돼 있으면 Docker Desktop을 시작하고 docker start tradingagents-postgres-dev로 원래 볼륨을 연다. 작업 트리에는 커밋되지 않은 사용자 변경이 있다. .env, .env.dev, 관리자 토큰, 터널 자격증명, DB 덤프는 Git과 로그에서 제외한다. 앱은 .env를 사용한다. scripts/dev/start-all.ps1은 개발용 DB 초기화와 Vite를 함께 호출하므로 운영 시작 경로로 쓰지 않는다.

**중단 전 챙길 자료**는 Windows 프로젝트·환경 파일, DB별 최신 덤프, 터널 설정과 UUID 자격증명이다. 기존 터널 파일은 Ubuntu 홈의 .cloudflared/config.yml 및 40748fbe-a98f-4ea2-9059-0b14d287a794.json에 있다. Ubuntu를 처분하기 전에 Windows의 접근 제한된 디렉터리로 복사한다. JSON은 터널 실행 자격증명이다. 계정 관리용 cert.pem은 커넥터 실행에 필요하지 않다. 기존 20261123-203926 백업은 C:\Users\samda\dev\TradingAgents-backups 아래에 있고 이후에 생성된 리포트가 있으므로 최종 이전에는 새 덤프를 쓴다.

## 2. PostgreSQL 17 인수

Windows용 PostgreSQL 17에서 서버와 명령줄 도구를 설치한다. 서비스 관리 계정과 DB 관리자 암호는 설치 시 설정한다. 포트 55432가 비어 있는지 확인하고 인스턴스를 loopback에 바인딩한다. pg_hba.conf는 로컬 TCP 암호 인증을 사용한다. 서비스 이름은 Get-Service에서 확인한다.

전환 직전 예약 실행 시각을 확인한다. 큐가 비고 실행 중인 분석이 끝난 뒤 기존 API와 다른 DB 쓰기 프로세스를 중지한다. 중지 대상 PID와 명령줄이 이 프로젝트인지 확인한다. 마지막 덤프부터 대상 검증까지 쓰기 중지 상태를 유지한다. DB 컨테이너는 백업이 끝날 때까지 실행한다.

~~~powershell
$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$backup = New-Item -ItemType Directory "$env:USERPROFILE\dev\TradingAgents-backups\$stamp"
$dump = Join-Path $backup.FullName 'tradingagents_dev.dump'
$tmpDump = "/tmp/tradingagents-$stamp.dump"
docker exec tradingagents-postgres-dev pg_dump -U trading -d tradingagents_dev -Fc -f $tmpDump
if ($LASTEXITCODE) { throw 'pg_dump failed' }
docker cp "tradingagents-postgres-dev:${tmpDump}" $dump
if ($LASTEXITCODE) { throw 'docker cp failed' }
$srcHash = (docker exec tradingagents-postgres-dev sha256sum $tmpDump).Split(' ')[0]
if ((Get-FileHash $dump).Hash -ne $srcHash) { throw 'backup checksum mismatch' }
$sql = 'select current_database(), count(*) as reports, max(id) as latest_id from reports; select count(*) from trades; select count(*) from schedule_jobs;'
docker exec tradingagents-postgres-dev psql -X -v ON_ERROR_STOP=1 -U trading -d tradingagents_dev -c $sql
~~~

기본 설치 경로를 사용한 예다. 최초에만 trading 역할과 빈 DB를 만든다. 기존 대상 DB에 덮어쓰지 않고, 이름이 이미 있으면 소유자와 내용을 먼저 확인한다. 비밀번호는 프롬프트에서 입력하며 앱의 POSTGRES_PASSWORD와 일치시킨다. 자동화에서는 기존 비밀 저장소 또는 접근 권한이 제한된 PostgreSQL passfile을 사용한다.

~~~powershell
$pg = 'C:\Program Files\PostgreSQL\17\bin'
& "$pg\createuser.exe" -h 127.0.0.1 -p 55432 -U postgres --pwprompt trading
if ($LASTEXITCODE) { throw 'role setup failed' }
& "$pg\createdb.exe" -h 127.0.0.1 -p 55432 -U postgres -O trading tradingagents_dev
if ($LASTEXITCODE) { throw 'database setup failed' }
& "$pg\pg_restore.exe" -h 127.0.0.1 -p 55432 -U postgres -d tradingagents_dev --exit-on-error --single-transaction $dump
if ($LASTEXITCODE) { throw 'restore failed' }
& "$pg\psql.exe" -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U trading -d tradingagents_dev -c $sql
~~~

동일 SQL 결과와 테이블 목록(양쪽 psql에서 \dt)을 비교한다. 최종 덤프의 최신 리포트 ID·종목·작업 ID를 기록한다. 2026-11-23 검증 기준은 리포트 1238건, GOOGL 리포트 1238, 작업 1395, 67회차였다. 이후 증가하는 값이다. 원본과 대상의 결과가 일치하면 .env를 접근 제한된 위치에 백업하고 POSTGRES_HOST=127.0.0.1, POSTGRES_PORT=55432, POSTGRES_DB=tradingagents_dev로 변경한다. SUPABASE_DB_URL, TRADINGAGENTS_DB_URL, DATABASE_URL은 우선 적용되므로 값 노출 없이 설정 여부를 확인한다. 별도 과거 DB가 필요하면 자체 덤프를 별도 DB tradingagents에 복원한다.

## 3. Windows 백엔드와 프런트엔드

저장소 루트에서 uv, Node/npm, 공식 Codex 로그인을 확인한다. API의 Windows 실행 계정에서 codex login status가 ChatGPT 인증을 표시해야 한다. 필요하면 같은 사용자로 codex login을 실행해 사람이 로그인한다. .env의 관리자 토큰과 LLM_PROVIDER=codex를 유지한다. 운영 CORS에는 https://daehun.app을 반영하고, 로컬 개발 화면을 계속 쓸 경우 기존 허용 origin도 포함한다.

~~~powershell
uv sync --frozen --python 3.11
if ($LASTEXITCODE) { throw 'backend dependency sync failed' }
Push-Location apps/web
try {
    npm.cmd ci
    if ($LASTEXITCODE) { throw 'frontend dependency install failed' }
    $env:VITE_API_BASE_URL='/api'
    npm.cmd run build
    if ($LASTEXITCODE -or !(Test-Path dist/index.html)) { throw 'frontend build failed' }
} finally { Pop-Location }
.\.venv\Scripts\python.exe -m uvicorn apps.api.app:app --env-file .env --host 127.0.0.1 --port 8001
~~~

마지막 명령은 포그라운드 검증용이다. 다른 PowerShell에서 /health와 /reports를 확인한다. 운영은 같은 실행 파일·인수와 저장소 루트를 작업 디렉터리로 지정한다. 프로세스 내부에 APScheduler와 큐가 있으므로 worker는 1개로 유지한다. FE는 빌드가 끝난 dist 전체를 버전별 디렉터리(예: C:/TradingAgents/releases/20261123-1/web)로 복사한다. 직전 릴리스 디렉터리를 보존한다.

## 4. Windows Nginx

공식 Windows 배포판을 예를 들어 C:/nginx에 설치한다. Windows판은 콘솔 프로그램이며 공식 문서상 beta다. 기존 nginx.conf의 http 블록에 아래 server를 포함한다. mime.types 포함을 유지하고 root는 실제 배포한 릴리스로 교체한다. FE가 /api를 기준으로 REST와 WebSocket 주소를 생성하므로 /api/ws/를 먼저 고려한다. 아래 proxy_pass 끝의 슬래시는 백엔드 경로 변환에 필요하다.

~~~nginx
server {
    listen 127.0.0.1:18080;
    server_name daehun.app localhost;
    root C:/TradingAgents/releases/20261123-1/web;
    index index.html;

    location /api/ws/ {
        proxy_pass http://127.0.0.1:8001/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8001/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location ~ ^/(sw\.js|registerSW\.js|cleanup-api-caches\.js|index\.html)$ { add_header Cache-Control "no-store" always; try_files $uri =404; }
  location / { try_files $uri $uri/ /index.html; }
}
~~~

C:/nginx에서 .\nginx.exe -t 실행 후 최초에는 .\nginx.exe로 시작한다. 갱신에는 .\nginx.exe -s reload, 정상 종료에는 .\nginx.exe -s quit를 같은 prefix에서 실행한다. 로컬에서 http://127.0.0.1:18080/ 및 /api/health, /api/reports?ticker=GOOGL&limit=1을 확인한다. 프런트엔드 소스가 실제 요청하는 /api/ws/analyze/GOOGL에서 HTTP 101과 첫 JSON 이벤트를 확인한다. 분석이 없는 경우 waiting이 정상이다.

## 5. Cloudflare Tunnel과 도메인

기존 도메인은 daehun.app, 기존 터널 이름은 tradingagents다. 같은 터널 UUID를 유지하면 기존 DNS 라우트를 재사용할 수 있다. Cloudflare 대시보드에서 DNS가 이 UUID의 cfargotunnel.com 대상으로 연결되는지 확인한다. 기존 커넥터가 다른 origin으로 실행 중이면 새 커넥터와 트래픽을 나눌 수 있으므로 전환 시 상태를 확인한다.

Windows용 cloudflared를 설치한 뒤 다음을 예를 들어 C:/ProgramData/TradingAgents/cloudflared/config.yml에 둔다. credentials-file은 앞서 인수한 실제 JSON을 가리킨다. 디렉터리는 관리자와 실행 계정만 접근할 수 있게 한다.

~~~yaml
tunnel: 40748fbe-a98f-4ea2-9059-0b14d287a794
credentials-file: C:/ProgramData/TradingAgents/cloudflared/40748fbe-a98f-4ea2-9059-0b14d287a794.json
ingress:
  - hostname: daehun.app
    service: http://127.0.0.1:18080
  - service: http_status:404
~~~

~~~powershell
$cfg = 'C:\ProgramData\TradingAgents\cloudflared\config.yml'
cloudflared tunnel --config $cfg ingress validate
if ($LASTEXITCODE) { throw 'invalid tunnel ingress' }
cloudflared tunnel --config $cfg run
~~~

마지막 명령은 실제로 공개 트래픽을 받을 수 있다. 로컬 검증이 끝나고 공개 배포를 요청받은 시점에 실행한다. Windows 서비스 등록은 Cloudflare의 locally-managed Windows 서비스 절차를 따른다. 관리자 PowerShell에서 cloudflared service install 후 서비스의 실행 파일 경로와 인수가 **위 config 절대경로와 tunnel run**을 사용하도록 구성한다. sc.exe qc cloudflared로 BINARY_PATH_NAME, 서비스 계정, 자동 시작을 검증한다. 해당 계정에서 JSON 읽기와 로그 쓰기가 가능해야 한다. 대화형 검증 프로세스와 서비스는 중복 실행하지 않는다. 로컬 origin과 DB를 위한 인터넷 인바운드 포트 개방은 필요 없다.

## 6. 자동 기동, 인수 테스트, 장애 복구

- PostgreSQL과 cloudflared는 Windows 서비스의 자동 시작·실패 후 재시작을 설정한다. BE와 Nginx는 작업 스케줄러에서 각 하나씩 실행한다. BE는 ChatGPT 로그인 사용자로, Nginx는 설치 폴더를 시작 위치로 실행한다. 서비스가 로그인 전에도 필요하면 BE 작업의 비대화형 실행 권한과 해당 사용자 프로필 인증을 재부팅으로 검증한다. 로그온 트리거만 사용한 경우 로그인 후 서비스다.
- DB 준비는 pg_isready.exe -h 127.0.0.1 -p 55432로 확인한다. BE 부팅 실패 시 작업 재시도를 설정한다. 게시 전 재기동 테스트에는 API와 프록시의 종료·다시 시작을 포함한다. PC 재부팅은 사용자 작업에 영향을 주므로 합의된 시점에 수행한다.
- 순서대로 검사한다. 직접 API /health → Nginx /api/health → 외부 네트워크의 https://daehun.app/api/health → /api/reports의 최신 ID가 DB와 일치 → 브라우저 https://daehun.app/#/reports/googl 상세 회차 → wss://daehun.app/api/ws/analyze/GOOGL의 첫 이벤트. PWA 캐시 영향을 피하려면 새 브라우저 세션과 직접 API 응답을 함께 본다. 관리자 쓰기 경로는 인증 없는 요청을 거부하는지 부작용 없는 방식으로 확인한다.
- 새 분석까지 요구되면 기존 실패 작업 한 건을 인증된 재시도 API로 실행해 작업 ID를 기록한다. PostgreSQL에서 done·새 리포트 ID를 확인하고 API·브라우저에서 대조한다. 실제 분석은 구독 한도를 사용하고 가상 매매 기록을 갱신할 수 있다.
- 로그 위치는 PostgreSQL 서비스 설정, Windows 작업 기록, BE stdout/stderr, Nginx logs/error.log·access.log, cloudflared 서비스 로그를 확인한다. origin 접근 실패는 Nginx와 18080부터, API 502는 8001과 BE의 DB 연결부터, 터널 연결 실패는 서비스 계정의 config·JSON 접근과 DNS 라우트부터 점검한다.
- 원복은 문제가 생긴 계층부터 한다. FE는 직전 root로 되돌려 nginx -t 후 reload한다. DB 전환 직후 쓰기가 없으면 BE를 중지하고 기존 .env 복구 → 원래 Docker DB 시작 → BE 하나를 시작한다. 대상에 새 쓰기가 생겼다면 먼저 쓰기를 멈추고 대상 덤프 및 차이를 보존한 후 이전 방향을 결정한다. Docker 볼륨과 WSL 배포판 제거는 별도 작업이다.
- 전환 후에는 **Windows PostgreSQL의 데이터**를 정기 pg_dump -Fc로 백업한다. 서비스 계정과 저장 경로 권한, 여유 공간, 백업 주기와 보관 기간을 운영자와 맞추고 별도 빈 DB에 복원해 읽기 검증한다. dump 파일 생성만으로 복구 테스트를 대신하지 않는다.
- 인수 기록에 실제 적용 포트·서비스명·실행 계정·시작 트리거·릴리스 폴더·백업 경로·검증 시각·최신 리포트 ID와 미검증 항목을 남긴다. 자격증명 값은 기록하지 않는다. 이후 세션은 이 기록과 현재 실행 상태를 다시 대조한다.

공식 참고 문서: [Windows PostgreSQL 설치](https://www.postgresql.org/download/windows/) · [Docker Desktop Windows 요구사항](https://docs.docker.com/desktop/setup/install/windows-install/) · [Nginx Windows 운영](https://nginx.org/en/docs/windows.html) · [Cloudflare Windows 터널 서비스](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/windows/)
