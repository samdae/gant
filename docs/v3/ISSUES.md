# v3 시장 이슈 수집 운영

공개 프리뷰는 v2의 사례·매매 리포트를 읽는다. v2의 사례 관측 시각 또는 리포트 생성 시각 전에 v3가 확보했고 당시 이미 발행된 같은 종목의 기사만 보조자료로 표시한다. 해당 시점에 수집한 기록이 없으면 미수집으로 표시한다. 예약 실행 시 v2가 last30days 검색을 호출한다. v3 뷰어와 검색기는 별도의 프로세스다.

연구 사례를 처음 저장할 때 수집 DB에서 당시 읽을 수 있었던 최근 30일 근거를 별도 레코드에 동결한다. 기존 사례의 근거나 다섯 거래일 확률은 이 작업으로 다시 계산하지 않는다. 종목명 검색 결과는 함께 읽을 수 있는 시장 자료이며 가격 변동의 원인이나 투자 성과를 입증하지 않는다.

## 예약 수집

운영 검색기는 Windows 런타임 아래 고정된 upstream 체크아웃과 전용 Python 가상환경을 사용한다. 현재 구성은 last30days 4.6.0 (`7c2e1c2b099b13abd4397910168c4f53e638bb21`), Python 3.12, yt-dlp 2026.11.23이다. 검색 소스는 Hacker News와 YouTube다. 한국 종목에는 한국어 종목명을 사용한다. 출처와 날짜를 검증한 결과만 공개한다.

새 Windows 설치에서는 v3 루트에서 다음과 같이 검색기를 준비한다. 기존 설치에서는 HEAD와 가상환경 패키지 버전을 확인한다. v2·v3 앱의 기존 Python 환경은 따로 운영한다.

~~~powershell
$integrations = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/integrations'
$engine = Join-Path $integrations 'last30days'
$venv = Join-Path $integrations 'last30days-python'
New-Item -ItemType Directory -Force $integrations | Out-Null
git clone --filter=blob:none --no-checkout https://github.com/mvanhorn/last30days-skill.git $engine
git -C $engine sparse-checkout set skills/last30days
git -C $engine checkout --detach 7c2e1c2b099b13abd4397910168c4f53e638bb21
uv venv --python 3.12 $venv
uv pip install --python "$venv/Scripts/python.exe" yt-dlp==2026.11.23
~~~

v2의 종목별 예측·가상매매 예약이 검색의 유일한 기동점이다. 시세가 준비된 새 예측은 관측 시각을 확정하기 전에, 유효한 매매 분석은 리포트를 생성하기 전에 끝난 검색 결과를 사용할 수 있다. 동결 사례 재시도와 시세 미갱신으로 건너뛰는 매매 예약은 새 검색을 만들지 않는다. 예측 진입 시각이 임박했다면 모델 추론 시간을 확보하도록 검색을 건너뛴다.

같은 종목에 대한 예측과 매매 요청은 DB 잠금과 수집 기록을 공유한다. 정상 결과와 적격 항목 0건은 6시간, 실패는 15분 동안 재사용한다. 부분 실패 시 응답한 출처에서 확보한 적격 자료도 같은 실행에 저장한다. 15분이 지나면 다음 적격 요청이 재시도할 수 있다. 잠금은 프로세스 종료 시 해제된다. 출처별 검색은 병렬로 최대 70초, v2 콜백 전체는 최대 110초로 제한한다. 검색 지연·실패는 가격 예측, 점수, 매매 실행을 취소하지 않는다. 이전 사례에 미래의 수집 결과를 소급하지 않는다.

예약 전용 CLI는 v3 연구 DB에 검색 결과와 완료 시각을 저장한다. 아래 점검 명령도 같은 수집 경로를 실행한다. 출력의 `id`는 수집 실행 번호, `item_count`는 해당 실행의 적격 자료 수, `disposition`은 새 검색(`collected`) 또는 기존 결과 재사용(`reused`)이다. 0건이면 대기 시간과 빈 결과·실패 상태를 함께 확인한다.

~~~powershell
.\.venv\Scripts\python.exe -I -X utf8 -m tradingagents.forecast_lab.scheduled_issues --ticker NVDA --market us
~~~

## 별도 RSS 수집 및 수동 가져오기

네이티브 v3 체크아웃에서 실행한다. 프로젝트 가상환경에 서비스 패키지가 설치되어 있어야 한다. 전용 DB는 127.0.0.1:55436이며 명령에 전달하는 환경 파일은 현재 사용자의 %LOCALAPPDATA%\TradingAgentsV3\lab.env다. 수집 명령은 v3 웹 서버나 모델 로그인 없이 실행할 수 있다.

```powershell
$labEnv = Join-Path $env:LOCALAPPDATA 'TradingAgentsV3/lab.env'
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.issue_collector --env-file $labEnv --ticker 005930.KS
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.issue_collector --env-file $labEnv
```

두 번째 명령은 현재 등록된 종목 전체를 최대 세 개씩 병렬로 조회한다. 종목별 결과를 JSON으로 출력한다. 하나라도 수집 또는 저장에 실패하면 종료 코드는 1이며 나머지 종목 수집은 계속한다. 실패한 종목은 같은 명령으로 재시도한다. 최초 성공 관측의 시각과 제목은 재수집해도 바뀌지 않는다.

```powershell
.\scripts\register-v3-issues.ps1 -EnvFile $labEnv -WhatIf
.\scripts\register-v3-issues.ps1 -EnvFile $labEnv
Get-ScheduledTaskInfo -TaskName 'TradingAgents V3 Issue Collection'
```

예약 작업은 현재 사용자가 로그인하면 실행하고, 등록 직후부터 4시간 간격으로 반복한다. 이미 실행 중이면 해당 반복은 건너뛴다. 앱과 예측 워커는 이 작업을 기다리지 않는다. 일시 중단과 재개는 각각 Disable-ScheduledTask, Enable-ScheduledTask를 사용한다.

## 출처와 시간

Google News RSS 검색은 한국 종목을 한국어판, 미국 종목을 미국 영어판에서 찾는다. 등록된 주요 종목은 회사명·상품명을 사용하고 그 밖의 종목은 티커로 검색한다. Google이 제공하는 기사 링크, 매체명, 제목과 공개 시각만 보관한다. 기사 본문과 검색 결과의 설명은 보관하지 않는다. 피드는 최대 1 MiB이며 최신 적격 결과를 한 번에 종목당 40개까지 저장한다. 공급자 순위와 검색어에 따라 기사가 빠지거나 다른 회사를 다루는 결과가 포함될 수 있다.

last30days의 최근 기간 검색·다중 출처·근거 추적 방식을 적용했다. 개발 계정에서 생성한 구조화 결과도 명시적으로 가져올 수 있다. 기본 RSS 수집기는 개발자용 스킬이나 별도의 API 키가 필요 없다. [upstream 저장소](https://github.com/mvanhorn/last30days-skill) · [agent export v1 예제](https://github.com/mvanhorn/last30days-skill/blob/main/tests/fixtures/agent_export_v1.json)

```powershell
.\.venv\Scripts\python.exe -m tradingagents.forecast_lab.issue_collector --env-file $labEnv --ticker NVDA --import-agent-export C:\research\nvidia-agent-export.json
```

가져오기는 30일 창의 v1.x agent export를 읽는다. query에 대상 티커 또는 수집기 등록명이 있어야 한다. results에서 Reddit 게시물, X 게시물, YouTube 동영상, Hacker News 항목, GitHub 이슈·PR·토론의 허용된 HTTPS 링크만 선별한다. Hacker News 결과가 토론 ID 없이 제출한 원문 주소를 제공하는 경우, 공개 DNS 이름 형식의 HTTPS 원문 링크도 보존한다. 출처에는 원문 호스트명과 발견 경로인 Hacker News를 표시한다. 서버는 이 원문 URL을 조회하거나 DNS를 확인하지 않는다. IP·로컬 이름·비표준 포트·자격증명·리디렉션 경로·임의 쿼리는 거부하고 추적 매개변수는 제거한다. 요약·참여 점수·원본 프롬프트·생성 시각은 근거로 사용하지 않는다. 시간대가 있는 공개 시각은 UTC로 정규화한다. 날짜만 있는 결과는 UTC+14에서 해당 날짜가 시작되는 시각부터 UTC−12에서 해당 날짜가 끝날 때까지 전 구간이 30일 범위에 들어와야 인정한다. API의 published_day는 원래 날짜, published_precision=day는 시각 미상, published_at은 공개 가능 구간의 보수적인 상한을 뜻한다.

최초 관측 시각은 수집 또는 가져오기 당시 PostgreSQL 시계로 기록한다. 사례 조회는 공개 시각과 최초 관측 시각이 모두 근거 동결 시각보다 앞선 자료만 허용한다. 같은 티커의 중복 URL 또는 같은 매체·제목·공개 시각은 기존 레코드를 유지한다. 향후 수집된 과거 기사나 사후 수정 제목이 이미 동결한 근거에 들어가지 않는다.

## 연구 사례와 매매 리포트에서 읽는 방법

**예약 매매의 뉴스 입력**은 v2가 기존 뉴스 분석가를 호출할 때 고정한다. 종가로 모의체결하는 한국·미국 주식과 ETF는 거래소 달력을 적용하고, 거래 중인 봉은 가격 조회 시각까지만 사용한다. 자료는 기준 전 30일 내에 공개되고 기준 시각 전에 시스템에 관측돼야 한다. 기준 이후에 확보한 종목 뉴스는 다음 회차에 사용할 수 있다.

v2는 v3의 읽기 전용 조회 명령으로 last30days와 RSS에서 각각 최신 40건까지 읽고, 같은 URL을 한 번만 전달한다. 뉴스 분석가는 제목, 매체, 수집 출처, 공개·최초 관측 시각을 받는다. 원문 주소는 리포트에 보존해 각 인용에서 열 수 있다. 기사 전문은 이 경로로 제공하지 않는다. 제공한 각 자료에는 회차 한정 번호 `N1` 등이 붙는다. 종목 판단에 관련된 근거를 썼을 때만 해당 번호를 인용한다.

v2의 `reports.news_evidence`는 전달 시각 기준, 자료, 수집 상태와 두 단계의 명시적 인용을 같은 리포트에 기록한다. v3는 이를 그대로 읽어 뉴스 분석가 인용과 최종 판단 인용을 표시한다. 뉴스 분석가가 실행되지 않은 회차와 도입 전 기록은 NULL이다. 일부 수집 실패, 자료 없음, 입력 검증 실패를 각 상태에 맞게 표시한다. 별도로 조회되는 발행 시점의 참고 목록은 그 이후에 보관된 기사를 포함할 수 있다. 과거 기록에 인용을 소급 부여하지 않는다.

연구 사례의 기준은 가격 스냅숏의 `observed_at`이다. `GET /api/cases/{id}`의 `issues`에는 처음 사례를 만들 때 출처 전체에서 최신순으로 동결한 최대 40건이 들어간다. `last30days`는 같은 종목·기준 시각에서 last30days 수집 건만 최대 40건까지 따로 읽는다. RSS 기사가 많은 날에도 그전에 수집한 원문을 열 수 있다. 두 목록은 겹칠 수 있다. 둘의 합을 고유 출처 수로 해석하지 않는다. 현재 모델 확률을 산출하는 입력에는 이 기사들이 들어가지 않는다.

모의매매 분석에서는 `GET /api/report-sources/{id}`로 선택한 회차를 조회한다. 서버가 **v2** 콘솔 DB의 발행 기록에서 종목과 `created_at`을 구한 뒤 그 시각까지 공개·관측된 RSS와 last30days를 **v3** 아카이브에서 각각 조회한다. 이후 회차의 기사나 다른 종목의 자료는 앞선 회차에 표시되지 않는다. 없는 회차는 404이며 공개 화면에서는 조회만 가능하다.

| 상태 | 의미 |
|---|---|
| available | 시점에 맞는 근거가 있음 |
| uncollected | 해당 30일 동안 사례 동결 전 수집 기록이 없음 |
| empty | 수집은 했으나 당시 사용할 수 있는 근거가 없음 |
| failed | 최근 실행에서 확인하지 못한 출처가 있음. 그 실행과 앞선 실행에서 기준 시각까지 확보한 적격 자료를 표시 |
| storage_failed | CLI 상태. 저장소 장애로 실패 기록도 남기지 못함 |

조사는 전용 DB의 v3_issue_runs에서 종목·검색어·소스·완료 시각·상태·적격 건수로 시작한다. v3_issues는 출처·제목·주소·공개·관측 시각과 최초 수집 실행을 보관한다. last30days 장애는 고정된 실행본·전용 Python과 yt-dlp·외부 출처 연결·v3 아카이브 상태를, RSS 장애는 Google News 피드 연결을 확인한다.
