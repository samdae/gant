"""Report repository for CRUD operations on reports table."""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .database import Database

logger = logging.getLogger(__name__)


class ReportRepository:
    """Repository for reports table CRUD operations."""

    def __init__(self, db: Database):
        """Initialize repository with database connection.

        Args:
            db: Database instance
        """
        self.db = db
        self.conn = db.get_connection()

    def create(
        self,
        schedule_id: int,
        position_id: Optional[int],
        summaries: Dict[str, str],
        commit: bool = True,
        conn=None,
    ) -> int:
        """Create a new report with 13 summary columns.

        Args:
            schedule_id: Schedule ID (required)
            position_id: Position ID (optional, can be None for no-position cases)
            summaries: Dict with 13 column names as keys, summary texts as values
                      Expected keys: market_report, fundamentals_report, bull_history,
                                   bear_history, investment_debate_judge_decision,
                                   aggressive_history, conservative_history, neutral_history,
                                   trader_investment_judge_decision, trader_investment_decision,
                                   investment_plan, final_trade_decision, pa_opinion

        Returns:
            Report ID
        """
        created_at = datetime.now().isoformat()

        # Extract summaries (use None for missing keys)
        connection = conn or self.db.get_connection()
        cursor = connection.execute(
            """
            INSERT INTO reports (
                schedule_id, position_id,
                market_report, fundamentals_report,
                bull_history, bear_history, investment_debate_judge_decision,
                aggressive_history, conservative_history, neutral_history,
                trader_investment_judge_decision, trader_investment_decision,
                investment_plan, final_trade_decision, pa_opinion,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                schedule_id,
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
                summaries.get("pa_opinion"),
                created_at,
            )
        )
        if commit:
            connection.commit()

        row = cursor.fetchone()
        report_id = int(row["id"]) if row else 0
        logger.info(f"Created report {report_id} for schedule {schedule_id}")
        return report_id

    def get_by_position(self, position_id: int) -> List[Dict[str, Any]]:
        """Get all reports for a position (ordered by creation time).

        Args:
            position_id: Position ID

        Returns:
            List of report dicts (ordered oldest to newest)
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_id, position_id,
                   market_report, fundamentals_report,
                   bull_history, bear_history, investment_debate_judge_decision,
                   aggressive_history, conservative_history, neutral_history,
                   trader_investment_judge_decision, trader_investment_decision,
                   investment_plan, final_trade_decision, pa_opinion,
                   created_at
            FROM reports
            WHERE position_id = %s
            ORDER BY created_at ASC
            """,
            (position_id,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_by_schedule(self, schedule_id: int) -> Optional[Dict[str, Any]]:
        """Get report for a schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            Report dict or None if not found
        """
        cursor = self.db.get_connection().execute(
            """
            SELECT id, schedule_id, position_id,
                   market_report, fundamentals_report,
                   bull_history, bear_history, investment_debate_judge_decision,
                   aggressive_history, conservative_history, neutral_history,
                   trader_investment_judge_decision, trader_investment_decision,
                   investment_plan, final_trade_decision, pa_opinion,
                   created_at
            FROM reports
            WHERE schedule_id = %s
            """,
            (schedule_id,)
        )

        row = cursor.fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    # Test report repository
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from .database import Database
        from .schedule_repo import ScheduleRepository
        from .position_repo import PositionRepository

        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            print("SUPABASE_DB_URL not set; skipping test")
            raise SystemExit(0)

        db = Database(db_url)
        db.init_schema()

        # Create dependencies
        schedule_repo = ScheduleRepository(db)
        position_repo = PositionRepository(db)

        schedule_id = schedule_repo.create("NVDA", 1)
        position_id = position_repo.create("NVDA")

        repo = ReportRepository(db)

        # Test create
        print("\n1. Creating report...")
        summaries = {
            "market_report": "Market analysis summary...",
            "fundamentals_report": "Fundamental analysis summary...",
            "bull_history": "Bull arguments...",
            "bear_history": "Bear arguments...",
            "investment_debate_judge_decision": "Investment judge decision...",
            "aggressive_history": "Aggressive risk view...",
            "conservative_history": "Conservative risk view...",
            "neutral_history": "Neutral risk view...",
            "trader_investment_judge_decision": "Trader judge decision...",
            "trader_investment_decision": "Trader decision...",
            "investment_plan": "Investment plan...",
            "final_trade_decision": "Final decision: BUY",
            "pa_opinion": "PA opinion..."
        }
        report_id = repo.create(schedule_id, position_id, summaries)
        print(f"   Created report ID: {report_id}")

        # Test get_by_schedule
        print("\n2. Getting report by schedule...")
        report = repo.get_by_schedule(schedule_id)
        print(f"   Found report: {report['id']}")
        print(f"   Market report: {report['market_report'][:30]}...")
        print(f"   PA opinion: {report['pa_opinion'][:30]}...")

        # Test get_by_position
        print("\n3. Getting reports by position...")
        reports = repo.get_by_position(position_id)
        print(f"   Found {len(reports)} reports")
        for r in reports:
            print(f"   - Report {r['id']}: schedule={r['schedule_id']}")

        print("\n✅ ReportRepository test passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up test directory")
