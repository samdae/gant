# Antigravity 개선 제안서 v2

> 기반: proposal.md Phase 1~4 (구현 완료)
> 일자: 2026-02-13
> 상태: 설계 확정 (구현 전)

---

## Phase 5: PA 편향 방지 + 저장 아키텍처 개편

### 5-1. 분석플로우 객관성 확보

12에이전트 분석 파이프라인에서 포지션 주입을 제거한다.

| 항목 | 기존 (FR-017) | 변경 |
|------|--------------|------|
| Research Manager | 포지션 주입 ✅ | 주입 제거 ❌ |
| Trader | 포지션 주입 ✅ | 주입 제거 ❌ |
| Risk Manager | 포지션 주입 ✅ | 주입 제거 ❌ |
| Portfolio Agent | 포지션 인식 ✅ | **유일하게 유지** ✅ |

- `propagate()`의 `current_position` 파라미터는 유지 (PA에서 사용)
- 12에이전트는 순수 시장 데이터만으로 분석 → 객관성 보장

### 5-2. PA 프롬프트 강화

PA가 유일한 포지션 인식 에이전트로서 최종 판단을 내린다.

- **가중치**: 분석 결과(6) > 과거 경험(4) 기반 판단
- **디바이어싱 지시**: "포지션 때문에 편향되지 마라. 손실 포지션이 보유 이유가 되어선 안 된다."
- **HybridMemory 연결**: `decide()` 시 과거 매매 기억 검색하여 판단에 활용

### 5-3. 저장 경로 통합

모든 데이터를 `memory/` 아래로 통합하고, 역할별로 명확히 분리한다.

**기존:**
```
tradingagents/memory/data/        ← JSONL + ChromaDB
virtual_trade/tickers/AAPL/       ← trade.json, reports.json
```

**확정:**
```
memory/
├── experience/                   ← 반성문 JSONL + ChromaDB (RAG 학습)
│   ├── bull_memory.jsonl
│   ├── bear_memory.jsonl
│   ├── trader_memory.jsonl
│   ├── judge_memory.jsonl
│   ├── risk_memory.jsonl
│   └── chroma/
├── trade/                        ← 활성 매매 (진행 중)
│   └── AAPL/
│       ├── trade.json
│       └── report.json           ← reports.json → report.json 변경
└── archive/                      ← 완료된 매매 기록 (보관)
    └── AAPL/
        └── 1/                    ← 순번 디렉터리 (자동 증가)
            ├── trade.json
            └── report.json
```

**규칙:**
1. 포지션 close 시: `trade/AAPL/` → `archive/AAPL/{n}/` 이동 + trade/ 초기화
2. 포지션 잡지 않은 분석은 저장하지 않음 (검증 불가)
3. RAG 소스는 `experience/` (반성문 JSONL) — 기존 방식 유지
4. `archive/`는 원본 아카이브 전용, RAG 대상 아님
5. 순번(n)은 기존 디렉터리 카운팅으로 자동 결정

---

## Phase 6: 웹 백엔드 API

### 6-1. 프레임워크

- **FastAPI** 기반 REST API + WebSocket
- 단일 프로세스 배포: FastAPI lifespan 이벤트로 스케줄러 자동 기동/종료
- 분석 요청 시 `asyncio.to_thread()`로 동기 분석 함수를 스레드풀에서 실행 (논블로킹)

### 6-2. 보안

- **READ(GET)**: 공개 접근 🌐
- **WRITE(POST/PUT/DELETE)**: 인증 필요 🔒
- 인증 방식: `.env`의 `ADMIN_TOKEN` + `Authorization: Bearer {token}` 헤더
- 배포: Cloudflare Tunnel로 로컬 노출

### 6-3. API 엔드포인트 (BE 관점)

| # | Method | Endpoint | 인증 | 설명 |
|---|--------|----------|------|------|
| 1 | GET | `/schedules` | 🌐 | 등록된 스케줄 목록 |
| 2 | POST | `/schedules` | 🔒 | 스케줄 등록 (티커 검색 포함) |
| 3 | DELETE | `/schedules/{ticker}` | 🔒 | 스케줄 삭제 |
| 4 | GET | `/trade/{ticker}` | 🌐 | 활성 매매 상태 조회 |
| 5 | GET | `/trade/{ticker}/report` | 🌐 | 분석 결과 상세 |
| 6 | GET | `/archive/{ticker}` | 🌐 | 과거 매매 기록 목록 |
| 7 | GET | `/archive/{ticker}/{n}` | 🌐 | 과거 매매 기록 상세 |
| 8 | POST | `/analyze/{ticker}` | 🔒 | 수동 1회 분석 실행 |
| 9 | WS | `/ws/analyze/{ticker}` | 🌐 | 분석 진행현황 실시간 스트리밍 |
| 10 | GET | `/positions` | 🌐 | 활성 포지션 전체 + 수익률 |
| 11 | GET | `/search` | 🌐 | RAG 검색 (후순위) |

### 6-4. 에이전트 진행현황

- 실시간 스트리밍만 (WebSocket), 저장하지 않음
- reports에는 최종 분석 결과만 저장

---

## FE 메모 (백엔드 설계 완료 후)

- **첫 화면**: 대시보드 (Active Schedules + Open Positions + 최근 Activity)
- **차트 옆 카드**: 전략 표시 (레포트 대신) — stop_loss, target, next_action 등
- **관리자 모드**: 토글 → ADMIN_TOKEN 입력 → localStorage 저장 → 이후 자동 인증

---

## 설계 결정 (확정, 추가분)

8. **분석플로우 객관성**: 12에이전트 파이프라인은 포지션 정보 없이 완전 객관적 분석. 포지션 기반 판단은 PA에게만 위임.
9. **저장 경로 통합**: `memory/` 아래 experience(학습), trade(활성), archive(보관) 3분류. `virtual_trade/` 디렉터리 폐기.
10. **파일명 변경**: `reports.json` → `report.json` (단수형 통일).
11. **웹 프레임워크**: FastAPI + Cloudflare Tunnel.
12. **보안 모델**: READ 공개 + WRITE 인증 (Bearer token). 단일 사용자 전용.
13. **에이전트 진행현황**: 실시간 스트리밍만, 영속화 안 함.
14. **배포 모델**: 단일 프로세스 (uvicorn → FastAPI lifespan → APScheduler). 별도 스케줄러 프로세스 불필요.
15. **동시성 모델**: `asyncio.to_thread()` (스레드풀). 에이전트 플로우는 I/O-bound(LLM API 대기)이므로 GIL 경합 없음. 멀티프로세싱 불필요.

---

## Non-goals 수정

- ~~웹 UI/대시보드 (CLI 기반 유지)~~ → **웹 API 제공** (Phase 6)
