"""Prompt builder for retrospective analysis.

Constructs the LLM prompt based on position status (open vs closed)
with all relevant reports, trades, and context injected.
"""

from typing import Dict, Any, List, Optional


def build_retrospective_prompt(
    position: Dict[str, Any],
    reports: List[Dict[str, Any]],
    trades: List[Dict[str, Any]],
    is_open: bool,
    current_price: Optional[float] = None,
    unrealized_pnl_pct: Optional[float] = None,
) -> str:
    ticker = position["ticker"]
    avg_cost = position.get("avg_cost") or 0
    shares = position.get("shares") or 0
    stop_loss = position.get("stop_loss")
    target = position.get("target")

    reports_text = _format_reports(reports)
    trades_text = _format_trades(trades)

    common_context = f"""=== 회고분석: {ticker} ===

**포지션 정보:**
- 티커: {ticker}
- 진입일: {position['opened_at']}
- 평균단가: {avg_cost:.2f}
- 보유수량: {shares:.4f}
- 손절선: {stop_loss or 'N/A'}
- 목표가: {target or 'N/A'}

**시스템 규칙:**
- stop_loss 또는 target 도달 시 자동 청산
- ±30% 도달 시에도 자동 청산

**분석 사이클 히스토리 ({len(reports)}건):**
{reports_text}

**매매 이력 ({len(trades)}건):**
{trades_text}
"""

    if is_open:
        price_info = ""
        if current_price is not None:
            price_info = f"\n- 현재가: {current_price:.2f}"
        if unrealized_pnl_pct is not None:
            price_info += f"\n- 미실현 손익: {unrealized_pnl_pct:+.2f}%"

        return common_context + f"""
**현재 상태: OPEN (진행 중)**{price_info}

---

당신은 PA(Portfolio Agent)의 판단 품질을 평가하는 전문 분석가입니다.
이 포지션은 아직 진행 중입니다. PA의 각 의사결정이 날카로웠는지 중간 점검하세요.

각 사이클에서 PA의 행동(BUY/SELL/HOLD)을 하나씩 짚고, 다음을 평가하세요:

1. **PA 판단 품질**: PA가 해당 사이클에서 내린 결정(pa_opinion 참조)은 날카로웠는가? 파이프라인 결론과 같은 방향이었다면 — 단순 동조인가, 충분한 근거가 있었는가? 다른 방향이었다면 — PA의 독자 판단에 합리적 근거가 있었는가?

2. **근거 역추적**: PA가 근거로 삼았을 12에이전트 데이터를 역으로 확인하라. 강세/약세 논거, 리스크 의견 중 PA가 간과하거나 과대평가한 신호가 있는가?

3. **전략 파라미터 판단**: PA가 손절선, 목표가, 포지션 사이즈를 결정하거나 변경했다면, 그 시점의 데이터 대비 적절했는가?

4. **RAG 경험 활용**: [RAG 경험 사용됨]으로 표시된 사이클이 있다면, PA가 과거 경험을 판단에 적절히 반영했는가? 경험을 무시하고 판단한 부분이 있는가?

5. **중간 경고**: 현재까지 PA의 판단 패턴에서 우려되는 점이 있는가? (예: 손실 구간에서의 비합리적 낙관, 특정 신호에 대한 과잉 반응 등)

한국어로 작성하세요. 반드시 구체적 사이클 번호, PA의 실제 행동, 근거 데이터를 인용하여 분석하세요.
"""
    else:
        return_pct = position.get("return_pct") or 0
        outcome = "승" if return_pct >= 0 else "패"

        return common_context + f"""
**최종 결과: CLOSED**
- 청산일: {position.get('closed_at', 'N/A')}
- 실현 손익: {return_pct:+.2f}%
- 결과: {outcome}

---

당신은 PA(Portfolio Agent)의 판단 품질을 평가하는 전문 분석가입니다.
이 포지션은 완결되었습니다. PA의 전체 의사결정 흐름을 종합 평가하세요.

**중요: 결과({outcome})에 끌려가지 마세요. 승리했어도 근거 없는 판단이었을 수 있고, 패배했어도 합리적 판단이었을 수 있습니다. 판단의 품질만 평가하세요.**

각 사이클에서 PA의 행동(BUY/SELL/HOLD)을 하나씩 짚고, 다음을 평가하세요:

1. **PA 판단 품질 (사이클별)**: PA가 각 사이클에서 내린 결정(pa_opinion 참조)은 날카로웠는가?
   - 파이프라인과 같은 방향: 단순 동조인가, 데이터에 기반한 확신인가?
   - 파이프라인과 다른 방향: PA의 독자 판단에 합리적 근거가 있었는가?
   - 특히 **진입 시점**과 **청산 시점**의 판단을 집중 분석하라.

2. **근거 역추적**: PA가 근거로 삼았을 12에이전트 데이터를 역으로 확인하라. 강세/약세 논거, 리스크 의견 중 PA가 간과하거나 과대평가한 신호가 있는가?

3. **전략 파라미터 판단**: PA가 설정한 손절선, 목표가, 포지션 사이즈는 해당 시점 데이터 대비 적절했는가? 변경이 있었다면 그 근거는?

4. **RAG 경험 활용**: [RAG 경험 사용됨]으로 표시된 사이클이 있다면, PA가 과거 경험을 적절히 반영했는가? 경험이 없었던 사이클에서, 있었다면 판단이 달라졌을 가능성이 있는가?

5. **PA 편향 패턴**: 전체 사이클을 통해 PA의 판단에 반복되는 편향이 있는가?
   - 확증 편향: 보유 방향을 지지하는 신호만 수용하고 반대 신호를 무시
   - 손실 회피: 손실 구간에서 근거 없이 반등을 기대하며 보유 지속
   - 앵커링: 진입가에 고정되어 현재 시장 상황을 객관적으로 평가하지 못함
   - 과잉 동조: 파이프라인 결론에 무비판적으로 따름

6. **종합 평가**: PA의 판단 품질을 한 문장으로 요약하고, 향후 PA 프롬프트 개선에 반영할 수 있는 구체적 제언을 제시하세요.

한국어로 작성하세요. 반드시 구체적 사이클 번호, PA의 실제 행동, 근거 데이터를 인용하여 분석하세요.
"""


def _format_reports(reports: List[Dict[str, Any]]) -> str:
    if not reports:
        return "(없음)"

    parts = []
    for i, r in enumerate(reports, 1):
        rag_info = ""
        if r.get("rag_used"):
            rag_info = " [RAG 경험 사용됨]"

        parts.append(f"""
--- 사이클 {i} ({r.get('created_at', 'N/A')}){rag_info} ---
시장분석: {_truncate(r.get('market_report'))}
펀더멘탈: {_truncate(r.get('fundamentals_report'))}
강세논거: {_truncate(r.get('bull_history'))}
약세논거: {_truncate(r.get('bear_history'))}
투자토론판정: {_truncate(r.get('investment_debate_judge_decision'))}
공격적리스크: {_truncate(r.get('aggressive_history'))}
보수적리스크: {_truncate(r.get('conservative_history'))}
중립리스크: {_truncate(r.get('neutral_history'))}
트레이더판정: {_truncate(r.get('trader_investment_judge_decision'))}
트레이더결정: {_truncate(r.get('trader_investment_decision'))}
투자계획: {_truncate(r.get('investment_plan'))}
최종결정: {_truncate(r.get('final_trade_decision'))}
파이프라인결론: {r.get('decision_position', 'N/A')}
PA행동: {r.get('portfolio_action', 'N/A')} ({r.get('portfolio_shares', 0)} shares)
PA의견: {_truncate(r.get('pa_opinion'))}
""")
    return "\n".join(parts)


def _format_trades(trades: List[Dict[str, Any]]) -> str:
    if not trades:
        return "(없음)"

    parts = []
    for i, t in enumerate(trades, 1):
        parts.append(
            f"{i}. [{t.get('executed_at', 'N/A')}] "
            f"{t['action']} {t.get('shares', 0):.4f} shares @ "
            f"{t.get('price', 0):.2f}"
        )
    return "\n".join(parts)


def _truncate(text: Optional[str], max_len: int = 500) -> str:
    if not text:
        return "(없음)"
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."
