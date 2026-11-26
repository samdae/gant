# 조회 상태와 갱신 검증

V3의 데이터 조회 중에는 뷰포트 중앙에 회전 표시를 하나만 보여준다. 표시는 포인터 이벤트를 받지 않아 뒤의 버튼, 스크롤, 탭을 사용할 수 있다. 스크린리더에는 조회 상태를 전달하고 동작 줄이기를 설정하면 회전을 멈춘다. 가상매매 실행 단계와 연구 사례의 채점 대기는 서버가 기록한 상태이므로 그대로 표시한다.

예측 성과와 관측 현황을 새로고침할 때는 같은 기간의 마지막 응답을 유지한다. 갱신에 실패하면 마지막 응답임을 알린다. 시장이나 기간이 달라지면 이전 집계는 제거한다. 거래 차트의 빈 시세와 조회 오류도 별도로 표시한다.

다음 명령은 운영 번들 바깥에 후보를 만들고 Chromium에서 360, 393, 1440픽셀로 확인한다. 테스트는 성과 API의 첫 응답과 수동 갱신을 지연시키고 503 이후 재시도를 검증한다. 실제 계정이나 데이터베이스는 필요 없다.

```powershell
$env:VITE_FORECAST_LAB = "1"
$env:FORECAST_PUBLIC_UI_DIST = "$env:TEMP/gant-loading-preview"
npm --prefix apps/web run build -- --outDir "$env:FORECAST_PUBLIC_UI_DIST"
.venv/Scripts/python.exe -m unittest discover -s tests -p test_v3_reporting_browser.py
```
