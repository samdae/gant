# TradingAgents/graph/reflection.py

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseChatModel
import logging
import time

logger = logging.getLogger(__name__)


class Reflector:
    """Handles reflection on closed positions and updating memory.
    
    FR-031: Centralized reflection - reflects on entire position lifecycle
    instead of per-agent reflections.
    """

    def __init__(self, deep_thinking_llm: BaseChatModel):
        """Initialize the reflector with an LLM.
        
        FR-031: Changed from quick_thinking_llm to deep_thinking_llm
        for comprehensive reflection on position lifecycle.
        """
        self.deep_thinking_llm = deep_thinking_llm
        self.reflection_system_prompt = self._get_reflection_prompt()

    def _get_reflection_prompt(self) -> str:
        """Get the system prompt for position-level reflection."""
        return """
당신은 포지션 생애주기 전체를 복기하는 전문 트레이딩 회고 분석가입니다.
아래 정보가 제공됩니다.
1) 포지션 기간 동안의 모든 분석 요약(사이클별)
2) 전체 매매 이력(BUY/SELL 전부)
3) 최종 성과(수익률, 보유기간 등)

목표:
아래 4가지를 반드시 포함한 고품질 회고를 작성하세요.

1. **Cycle-by-Cycle Analysis**
   - 각 사이클의 핵심 판단(시장/펀더멘털/토론/최종결정)을 검토
   - 무엇이 맞았고 무엇이 틀렸는지 명확히 구분
   - 보유 기간 동안 시장 레짐이 어떻게 변했는지 설명

2. **Trading Execution Review**
   - 진입 타이밍과 사이징의 적절성 평가
   - 청산 타이밍과 실행 품질 평가
   - 분할매수/분할매도의 타당성 검토

3. **Key Lessons (가장 중요)**
   - 잘된 점과 원인
   - 잘못된 점과 원인
   - 재발 방지를 위한 구체 패턴
   - 섹터/시장 맥락에서 중요한 포인트
   - 리스크 관리 인사이트

4. **Actionable Insights**
   - 유사 상황에서 바로 쓸 수 있는 실행 규칙
   - 경고 신호(Warning signals)
   - 최적 진입/청산 기준

중요 지침:
- 출력은 **반드시 한국어**로 작성합니다.
- 감상문이 아닌, 데이터/사실 기반으로 냉정하게 작성합니다.
- 다음 형식을 반드시 지켜 출력하세요.
  - **Reflection**: (충분히 상세한 본문)
  - **Key Lessons**: (RAG 검색용 핵심 요약)
"""

    def reflect_on_position(
        self,
        position_id: int,
        db,
        ticker: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reflect on a closed position's complete lifecycle.

        FR-031: Single reflection method replacing 5 per-agent reflections.

        Args:
            position_id: Position ID to reflect on
            db: Database instance (for accessing repositories)
            ticker: Optional ticker symbol (for logging)

        Returns:
            Dict with keys:
                - reflection: str (full reflection text)
                - key_lessons: str (concise lessons for RAG)
                - outcome: str ('win' or 'loss')
                - return_pct: float

        Raises:
            ValueError: If position not found or not closed
        """
        from tradingagents.storage import (
            PositionRepository,
            ReportRepository,
            TradeRepository
        )

        # Initialize repositories
        position_repo = PositionRepository(db)
        report_repo = ReportRepository(db)
        trade_repo = TradeRepository(db)

        # 1. Get position metadata
        position = position_repo.get_by_id(position_id)
        if not position:
            raise ValueError(f"Position {position_id} not found")

        if position["status"] != "closed":
            raise ValueError(f"Position {position_id} is not closed (status={position['status']})")

        ticker = ticker or position["ticker"]
        return_pct = position.get("return_pct", 0.0)
        outcome = "win" if return_pct >= 0 else "loss"

        # 2. Get all reports for this position (전 사이클 요약)
        reports = report_repo.get_by_position(position_id)
        if not reports:
            raise ValueError(f"No reports found for position {position_id}")

        # 3. Get all trades for this position (매매 이력)
        trades = trade_repo.get_by_position(position_id)
        if not trades:
            raise ValueError(f"No trades found for position {position_id}")

        # 4. Build comprehensive context for LLM
        context = self._build_reflection_context(
            position=position,
            reports=reports,
            trades=trades,
            ticker=ticker
        )

        # 5. Invoke LLM for reflection
        messages = [
            ("system", self.reflection_system_prompt),
            ("human", context)
        ]

        max_attempts = 3
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.deep_thinking_llm.invoke(messages)
                reflection_text = response.content

                # Parse reflection and key_lessons from response
                reflection, key_lessons = self._parse_reflection_output(reflection_text)

                if not reflection or not key_lessons:
                    raise ValueError("Reflection output is empty")

                logger.info(
                    f"Generated reflection for position {position_id} ({ticker}) on attempt {attempt}: {outcome}"
                )

                return {
                    "reflection": reflection,
                    "key_lessons": key_lessons,
                    "outcome": outcome,
                    "return_pct": return_pct
                }

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Reflection attempt {attempt}/{max_attempts} failed for position {position_id} ({ticker}): {e}"
                )
                if attempt < max_attempts:
                    time.sleep(attempt)  # 1s, 2s backoff

        # Do not save fake fallback text; bubble up for scheduler-level retry/handling.
        raise RuntimeError(
            f"Reflection generation failed after {max_attempts} attempts for position {position_id} ({ticker})"
        ) from last_error

    def _build_reflection_context(
        self,
        position: Dict[str, Any],
        reports: list,
        trades: list,
        ticker: str
    ) -> str:
        """Build comprehensive context string for reflection LLM."""
        context = f"""
=== Position Reflection: {ticker} ===

**Position Metadata**:
- Position ID: {position['id']}
- Ticker: {ticker}
- Opened: {position['opened_at']}
- Closed: {position['closed_at']}
- Total Shares: {position['shares']}
- Avg Cost: ${position.get('avg_cost', 0):.2f}
- Return: {position.get('return_pct', 0):.2f}%
- Outcome: {"WIN ✅" if position.get('return_pct', 0) >= 0 else "LOSS ⚠️"}

"""

        # Trade history
        context += "\n**Trade History** (chronological):\n"
        for i, trade in enumerate(trades, 1):
            context += f"{i}. {trade['action']} {trade['shares']} shares @ ${trade['price']:.2f} on {trade['executed_at']}\n"

        # Analysis cycles (reports) - include key summaries only
        context += f"\n**Analysis Cycles** ({len(reports)} total):\n\n"
        for i, report in enumerate(reports, 1):
            context += f"--- Cycle {i} ({report['created_at']}) ---\n\n"

            if report.get('market_report'):
                context += f"Market: {report['market_report'][:300]}...\n\n"
            
            if report.get('final_trade_decision'):
                context += f"Final Decision: {report['final_trade_decision'][:300]}...\n\n"

            # Pipeline strategy JSON (Judge's structured instruction)
            if report.get('pipeline_strategy'):
                import json
                strategy = report['pipeline_strategy']
                if isinstance(strategy, str):
                    try:
                        strategy = json.loads(strategy)
                    except (json.JSONDecodeError, ValueError):
                        pass
                if isinstance(strategy, dict):
                    context += f"Pipeline Strategy (Judge): action={strategy.get('action')}, conviction={strategy.get('conviction')}, allocation_pct={strategy.get('allocation_pct')}\n\n"

            if report.get('pa_opinion'):
                context += f"PA Opinion: {report['pa_opinion'][:300]}...\n\n"

            if report.get('portfolio_action'):
                context += f"PA Action: {report['portfolio_action']}\n\n"

            context += "\n"

        context += """
**Your Task**:
Reflect on this complete position lifecycle. Analyze what worked, what didn't, and extract actionable lessons.

Provide output in this format:

**Reflection**:
[Comprehensive analysis here - 800-1200 tokens]

**Key Lessons**:
[Concise, actionable insights - 200-400 tokens]
"""

        return context

    def _parse_reflection_output(self, reflection_text: str) -> tuple[str, str]:
        """Parse LLM reflection output into reflection and key_lessons."""
        # Try to split by "Key Lessons:" marker
        parts = reflection_text.split("**Key Lessons**:")
        
        if len(parts) == 2:
            # Successfully split
            reflection = parts[0].replace("**Reflection**:", "").strip()
            key_lessons = parts[1].strip()
        else:
            # Fallback: Use entire text as reflection, extract last paragraph as lessons
            lines = reflection_text.strip().split('\n')
            if len(lines) > 10:
                # Last 5 lines as key_lessons
                reflection = '\n'.join(lines[:-5]).strip()
                key_lessons = '\n'.join(lines[-5:]).strip()
            else:
                # Too short, use entire text for both
                reflection = reflection_text.strip()
                key_lessons = reflection_text.strip()[:500]

        return reflection, key_lessons
