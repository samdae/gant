# Proposal v8: 학습 반영 품질 강화 (레짐 태그, 구조화 반성, 증거 기반 배점, 품질 게이트)

상태: Draft -> Ready for implementation
범위: 분석/회고/RAG 학습 루프
비범위: 실매매 연동, 매매 의사결정 강제 차단

---

## 1) 이 문서의 목표

v8의 목표는 기존 철학을 유지하면서 학습 품질을 높이는 것이다.

- 철학 유지: 포워드 분석 + 느린 학습
- 강화 포인트: 검색 오염 방지, 반성 재사용 정확도, +1 오판 축소
- 금지 포인트: BUY/HOLD/SELL 의사결정에 직접 개입하지 않음

---

## 2) 네가 정리한 흐름 기준에서 v8의 위치

분석 모드:

- 스케줄 등록 -> 12에이전트 분석 -> PA 매매결정 -> 포지션 open/close -> 반성 저장 -> 다음 분석에서 RAG 반영

회고/학습 모드:

- 사용자 회고분석 요청 -> 대상 선택/큐잉 -> 회고분석 실행 -> RAG 문서별 판정 -> usefulness 반영

v8 배치:

- 항목 2(레짐 태그): 반성 저장 시 생성, RAG 조회 시 필터/가중치로 사용
- 항목 4(구조화 반성): 반성 생성/저장 시 동시 기록
- 항목 1(증거 기반 +1/-1): 회고분석 이후, 최종 점수 반영 정책에서 적용
- 항목 5(품질 게이트): 항목 1과 같은 구간, 최종 반영 직전 적용

핵심: 항목 1과 5는 회고분석 뒤의 학습 반영 단계에 위치한다.

---

## 3) 운영 규칙 고정값

### 3-1. 회고 대상 규칙

- 제외 조건: 포지션 종료(closed) AND 회고분석 완료(completed)
- 포함 조건: 위 제외 조건을 만족하지 않는 모든 건

주의:

- pending/running은 대상 자체가 아닌 것이 아니라 이미 큐에 올라간 상태다.
- UX에서는 중복 요청 방지를 위해 선택 불가로 보인다.

### 3-2. 포트폴리오 RAG 변인 통제 규칙

- 분석 반성 1개
- 포트폴리오 반성 1개
- 총 2개 고정

동작 규칙:

- 한쪽 소스가 비어도 다른 소스로 보충하지 않는다.
- 같은 소스에서 2개를 채워 넣는 폴백을 금지한다.
- 따라서 최종 주입 수는 0~2개가 될 수 있다.

금지 규칙(하드 제약):

- quota_analysis=1, quota_portfolio=1은 소스별 하드 한도다.
- source_miss 발생 시 total_fill 전략(다른 소스로 채우기)을 사용하지 않는다.

이유:

- 비교 실험에서 변수 통제 우선

---

## 4) 기능 요구사항 (v8 신규)

### FR-064 레짐 태그 저장/검색

- 반성 저장 시 레짐 태그를 함께 저장해야 한다.
- RAG 검색 시 레짐 태그를 검색 조건 또는 가중치에 반영해야 한다.
- 레짐 태그는 원시 시계열 저장이 아니라 버킷 라벨만 저장한다.

### FR-065 반성 구조화 블록 병행 저장

- 반성문 자유 텍스트는 유지한다.
- 동시에 구조화 필드를 저장한다.
- 최소 필드: anti_patterns, do_not_rules, safe_rules

### FR-066 증거 기반 배점 정책

- +1/-1/0 체계는 유지한다.
- +1 적용은 증거 조건 충족 시에만 허용한다.
- ambiguous는 기본 0 처리한다.

### FR-067 학습 반영 품질 게이트

- 품질 게이트는 매매결정 게이트가 아니다.
- 최종 usefulness 반영 직전에 Green/Yellow/Red 판정을 수행한다.
- Red는 반영 스킵이다.

### FR-068 포트폴리오 RAG 1+1 고정

- 포트폴리오 PA의 교차 검색은 1+1 쿼터를 강제한다.
- 기존 2+1 또는 가변 참조를 허용하지 않는다.

---

## 5) 데이터 모델 변경안

v8은 추적 가능성을 위해 반영 결정의 근거를 DB에 남겨야 한다.

### 5-1. reflections 확장

- regime_vol_bucket: low | mid | high | unknown
- regime_rate_bucket: down | flat | up | unknown
- regime_trend_state: bull | neutral | bear | unknown
- regime_risk_state: risk_on | neutral | risk_off | unknown
- anti_patterns: JSONB 배열
- do_not_rules: JSONB 배열
- safe_rules: JSONB 배열
- reflection_schema_version: 정수 (기본 1)

### 5-2. rag_validation_results 확장

- evidence_passed: boolean
- evidence_reasons: JSONB 배열
- quality_grade: green | yellow | red
- quality_reasons: JSONB 배열
- proposed_delta: -1 | 0 | +1
- applied_delta: -1 | 0 | +1
- update_applied: boolean

### 5-3. retrospective_analyses 확장

- structured_parse_error: boolean (기본 false)
- structured_parse_error_reasons: JSONB 배열

의도:

- 후보 점수와 실제 반영 점수를 분리 저장하여 사후 감사 가능
- 구조화 파싱 실패 위치를 회고 실행 단계 테이블에 고정

---

## 6) 레짐 태그 규칙 (결정값)

레짐은 매크로 수치를 버킷으로 압축한 라벨이다.

### 6-1. vol_bucket

- us/kr: VIX 기준
  - low: 15 미만
  - mid: 15 이상 25 미만
  - high: 25 이상
- crypto: BTC 20일 연율화 변동성 기준
  - low: 0.45 미만
  - mid: 0.45 이상 0.75 미만
  - high: 0.75 이상

### 6-2. rate_bucket

- us/kr: 20거래일 변화량 기준
  - us 기준 데이터: ^IRX 종가
  - kr 기준 데이터: USDKRW=X 종가
  - up: +0.20%p 이상
  - down: -0.20%p 이하
  - flat: 그 사이
- crypto: unknown 고정

### 6-3. trend_state

- 시장 대표지수 기준
  - bull: 가격이 50일선/200일선 모두 위
  - bear: 가격이 50일선/200일선 모두 아래
  - neutral: 나머지

### 6-4. risk_state

- risk_off: vol_bucket=high 또는 trend_state=bear
- risk_on: vol_bucket=low AND trend_state=bull
- neutral: 나머지

---

## 7) 구조화 반성 규칙 (항목 4)

### 7-1. 필드 제약

- anti_patterns: 1~5개, 항목당 1~80자
- do_not_rules: 1~5개, 항목당 1~120자
- safe_rules: 1~5개, 항목당 1~120자

### 7-2. 저장 정책

- 파싱 실패 시 빈 배열로 저장하지 않는다.
- 파싱 실패 시 회고 상태를 failed로 두지 않고, `retrospective_analyses.structured_parse_error=true`로 기록한다.
- 상세 실패 이유는 `retrospective_analyses.structured_parse_error_reasons`에 기록한다.

### 7-3. 검색 반영

- 텍스트 유사도 + 구조화 키워드 매칭을 함께 반영
- anti_patterns가 일치하면 가중치 상향

---

## 8) 증거 기반 배점 정책 (항목 1)

### 8-1. 정의

- proposed_delta: 판정 모델이 제안한 점수
- applied_delta: 정책/게이트를 통과한 최종 점수

### 8-2. +1 허용 조건

아래 조건을 모두 만족해야 +1을 허용한다.

- C1. 해당 문서가 실제 RAG 입력으로 사용됨
- C2. 회고 본문 반영 근거를 LLM 이진판정으로 evidence_passed=true로 판정함
- C3. 레짐 태그가 강한 불일치가 아님
- C4. 품질 게이트가 Green

C2 판정 규칙:

- 판정 단위: 문서별(per reflection_id)
- 출력: evidence_passed(boolean), evidence_reasons(JSONB 배열)
- 파싱 실패 시 evidence_passed=false 처리

C3 강한 불일치 규칙:

- trend_state가 bull vs bear로 정반대인 경우
- risk_state가 risk_on vs risk_off로 정반대인 경우
- 위 두 조건 중 하나라도 충족하면 강한 불일치로 본다.

조건 미충족 시 +1은 0으로 강등한다.

### 8-3. -1 조건

- not_reflected 판정이고 근거가 명확하면 -1
- 품질 게이트 Red면 -1도 적용하지 않고 0으로 스킵

### 8-4. ambiguous 정책

- 기본 0
- 재평가 큐는 선택 기능으로 두되 기본 비활성

---

## 9) 품질 게이트 규칙 (항목 5)

품질게이트는 점수 반영에만 관여한다.

### 9-1. 판정 등급

- Green: 정상 반영
- Yellow: +1 금지, 0/-1만 허용
- Red: 전체 스킵(무조건 applied_delta=0)

### 9-2. 체크 항목

- Q1 출력 무결성: 필수 필드 존재 및 형식 정상
- Q2 논리 일관성: 자기모순 규칙 위반 없음
- Q3 근거 충실도: 근거 부족 플래그 없음
- Q4 판정 신뢰도: ambiguous 과다 아님

Q1 필수 필드:

- verdict
- proposed_delta
- evidence_passed
- quality_grade
- applied_delta

Q2 자기모순 규칙:

- verdict=reflected인데 proposed_delta=-1이면 모순
- verdict=not_reflected인데 proposed_delta=+1이면 모순
- quality_grade=red인데 applied_delta!=0이면 모순

### 9-3. 임계값

- Red:
  - 필수 필드 누락
  - 파싱 실패
  - 모순 위반 1건 이상
- Yellow:
  - 근거 부족 경고
  - rag_contribution 해석 불가
  - ambiguous 비율 50% 이상
- Green: 위 조건에 해당하지 않음

ambiguous 비율 단위:

- retrospective 단위로 계산한다.
- 분자: 해당 retrospective_id의 ambiguous 건수
- 분모: 해당 retrospective_id의 전체 평가 건수

---

## 10) 반영 결정 매트릭스

### 10-1. verdict=reflected

- Green + 증거충족: +1
- Green + 증거미충족: 0
- Yellow: 0
- Red: 0

### 10-2. verdict=not_reflected

- Green/Yellow + 근거충족: -1
- Green/Yellow + 근거미충족: 0
- Red: 0

### 10-3. verdict=ambiguous

- 모든 등급에서 0

---

## 11) 모듈 반영 위치 (개발 작업 단위)

### 11-1. 반성 생성/저장 구간

- 레짐 태그 생성
- 구조화 블록 파싱/저장

### 11-2. 메모리 조회 구간

- 레짐 태그 기반 필터/가중치
- 포트폴리오 1+1 쿼터 강제

### 11-3. 회고 후 학습 반영 구간

- proposed_delta 산출
- 증거 검증
- 품질 게이트
- applied_delta 확정 및 저장

---

## 12) 마이그레이션/릴리즈 전략

### 12-1. 단계

- 1단계: 스키마 확장 컬럼 추가 (기본값/널 허용)
- 2단계: 쓰기 경로 업데이트 (신규 필드 기록)
- 3단계: 읽기 경로 업데이트 (신규 필드 활용)
- 4단계: 게이트 활성화

### 12-2. 롤백

- 게이트만 비활성화하면 기존 +1/-1 경로로 즉시 복귀 가능
- 레짐/구조화 필드는 무시 가능하도록 역호환 유지

---

## 13) 검증 시나리오 (필수)

- reflected + 증거충족 + Green -> +1 적용
- reflected + 증거미충족 -> 0 강등
- not_reflected + Green -> -1 적용
- Red 판정 -> 어떤 verdict든 0
- 포트폴리오 RAG는 분석 1 + 포폴 1만 조회
- 포트폴리오 RAG에서 한쪽 소스 miss 시 다른 소스로 보충하지 않음
- 회고 대상 집계에서 closed+completed만 제외

---

## 14) 관측 지표 (주간 운영)

- 게이트 등급 분포(Green/Yellow/Red)
- proposed_delta 대비 applied_delta 변경률
- +1 강등률(증거미충족)
- 스킵률(Red)
- usefulness 분산과 드리프트
- 포트폴리오 1+1 충족률

원칙:

- 관측 지표는 학습 반영 정책 튜닝용이다.
- 매매 의사결정을 강제하지 않는다.

---

## 15) 수용 기준

아래를 모두 만족하면 v8 완료로 판정한다.

- 회고 대상 규칙이 운영 정의와 일치한다.
- 레짐 태그가 저장/조회 양쪽에서 동작한다.
- 반성 구조화 블록이 누락 없이 저장된다.
- +1은 증거 미충족 시 적용되지 않는다.
- 품질 게이트가 최종 반영 전에 항상 동작한다.
- 포트폴리오 RAG가 1+1로 고정된다.
