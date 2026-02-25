"""Report repository for CRUD operations on reports table."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ReportRepository:
    """Repository for reports table CRUD operations."""

    def __init__(self, db: Database):
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        schedule_job_id: int,
        position_id: Optional[int],
        summaries: Dict[str, Any],
        commit: bool = True,
        conn=None,
    ) -> int:
        created_at = datetime.now().isoformat()

        pipeline_strategy = summaries.get("pipeline_strategy")
        if isinstance(pipeline_strategy, dict):
            pipeline_strategy = json.dumps(pipeline_strategy, ensure_ascii=False)

        rag_docs_raw = summaries.get("rag_docs")
        if isinstance(rag_docs_raw, dict):
            rag_docs_raw = json.dumps(rag_docs_raw, ensure_ascii=False)

        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO reports (
                schedule_job_id, position_id,
                market_report, fundamentals_report,
                bull_history, bear_history, investment_debate_judge_decision,
                aggressive_history, conservative_history, neutral_history,
                trader_investment_judge_decision, trader_investment_decision,
                investment_plan, final_trade_decision, decision_position,
                portfolio_action, portfolio_shares, portfolio_rationale,
                pa_opinion, pipeline_strategy,
                rag_used, rag_docs,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                schedule_job_id,
                position_id,
                summaries.get("market_report"),
                summaries.get("fundamentals_report"),
                summaries.get("bull_history"),
                summaries.get("bear_history"),
                summaries.get("investment_debate_judge_decision"),
                summaries.get("aggressive_history"),
                summaries.get("conservative_history"),
                summaries.get("neutral_history"),
                summaries.get("trader_investment_judge_decision"),
                summaries.get("trader_investment_decision"),
                summaries.get("investment_plan"),
                summaries.get("final_trade_decision"),
                summaries.get("decision_position"),
                summaries.get("portfolio_action"),
                summaries.get("portfolio_shares"),
                summaries.get("portfolio_rationale"),
                summaries.get("pa_opinion"),
                pipeline_strategy,
                summaries.get("rag_used", False),
                rag_docs_raw,
                created_at,
            ),
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        report_id = int(row["id"]) if row else 0
        logger.info(f"Created report {report_id} for job {schedule_job_id}")
        return report_id

    def get_by_position(self, position_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT r.id, r.schedule_job_id, r.position_id,
                   r.market_report, r.fundamentals_report,
                   r.bull_history, r.bear_history, r.investment_debate_judge_decision,
                   r.aggressive_history, r.conservative_history, r.neutral_history,
                   r.trader_investment_judge_decision, r.trader_investment_decision,
                   r.investment_plan, r.final_trade_decision, r.decision_position,
                   r.portfolio_action, r.portfolio_shares, r.portfolio_rationale,
                   r.pa_opinion, r.pipeline_strategy,
                   r.rag_used, r.rag_docs,
                   r.created_at,
                   sj.scheduled_cycle
            FROM reports r
            JOIN schedule_jobs sj ON r.schedule_job_id = sj.id
            WHERE r.position_id = %s
            ORDER BY sj.scheduled_cycle DESC, r.created_at DESC
            """,
            (position_id,),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_by_job(self, schedule_job_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_job_id, position_id,
                   market_report, fundamentals_report,
                   bull_history, bear_history, investment_debate_judge_decision,
                   aggressive_history, conservative_history, neutral_history,
                   trader_investment_judge_decision, trader_investment_decision,
                   investment_plan, final_trade_decision, decision_position,
                   portfolio_action, portfolio_shares, portfolio_rationale,
                   pa_opinion, pipeline_strategy,
                   rag_used, rag_docs,
                   created_at
            FROM reports
            WHERE schedule_job_id = %s
            """,
            (schedule_job_id,),
        )

        row = cursor.fetchone()
        return dict(row) if row else None
