"""Report Store for analysis reports.

Manages analysis reports (pipeline execution summaries) for a single ticker.
Storage: JSON array at memory/trade/{TICKER}/report.json (FR-027: reports.json → report.json)

Features:
- Append-only JSON array
- Auto-incrementing analysis_no
- State summary excerpts (first 500 chars)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ReportStore:
    """Manages analysis reports for tickers."""

    def __init__(self, base_dir: str):
        """Initialize the report store.

        Args:
            base_dir: Base directory for virtual trade data
                     (e.g., "virtual_trade/tickers")
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def _get_reports_path(self, ticker: str) -> str:
        """Get path to report.json for a ticker (FR-027)."""
        ticker_dir = os.path.join(self.base_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        return os.path.join(ticker_dir, "report.json")

    def load(self, ticker: str) -> List[Dict[str, Any]]:
        """Load all reports for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            List of report entries (empty list if file doesn't exist)
        """
        reports_path = self._get_reports_path(ticker)

        if not os.path.exists(reports_path):
            return []

        try:
            with open(reports_path, 'r', encoding='utf-8') as f:
                reports = json.load(f)

            if not isinstance(reports, list):
                logger.warning(
                    f"report.json for {ticker} is not a list, reinitializing"
                )
                return []

            return reports

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(
                f"Failed to load report.json for {ticker}: {e}, "
                "returning empty list"
            )
            return []

    def append(
        self,
        ticker: str,
        date: str,
        decision: str,
        strategy_summary: str,
        has_memory: bool,
        state_summary: Dict[str, str]
    ) -> int:
        """Append a new report entry.

        Args:
            ticker: Ticker symbol
            date: Analysis date (YYYY-MM-DD)
            decision: BUY | SELL | HOLD
            strategy_summary: Strategy description
            has_memory: Whether analysis used prior memories
            state_summary: Dict with market_report_excerpt, final_decision_excerpt

        Returns:
            analysis_no (auto-incremented)
        """
        reports = self.load(ticker)

        # Auto-increment analysis_no
        if reports:
            last_analysis_no = max(r.get("analysis_no", 0) for r in reports)
            analysis_no = last_analysis_no + 1
        else:
            analysis_no = 1

        # Create entry
        entry = {
            "date": date,
            "analysis_no": analysis_no,
            "decision": decision,
            "strategy_summary": strategy_summary,
            "has_memory": has_memory,
            "state_summary": state_summary,
        }

        reports.append(entry)

        # Save back to file
        reports_path = self._get_reports_path(ticker)

        try:
            with open(reports_path, 'w', encoding='utf-8') as f:
                json.dump(reports, f, indent=2, ensure_ascii=False)

            logger.info(
                f"Appended report for {ticker}: {date} (analysis #{analysis_no})"
            )

            return analysis_no

        except Exception as e:
            logger.error(f"Error saving report.json for {ticker}: {e}")
            raise

    def get_analysis_count(self, ticker: str) -> int:
        """Get total number of analysis reports for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            Number of reports
        """
        reports = self.load(ticker)
        return len(reports)


if __name__ == "__main__":
    # Example usage
    print("Testing ReportStore...")

    import tempfile
    import shutil

    # Create temp directory for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        store = ReportStore(base_dir=os.path.join(temp_dir, "tickers"))

        # Test 1: Load empty reports
        print("\n1. Loading reports for NVDA (should be empty)...")
        reports = store.load("NVDA")
        print(f"   Count: {len(reports)}")
        print(f"   Analysis count: {store.get_analysis_count('NVDA')}")

        # Test 2: Append first report
        print("\n2. Appending first report...")
        analysis_no = store.append(
            ticker="NVDA",
            date="2026-01-01",
            decision="BUY",
            strategy_summary="Strong bullish momentum with positive earnings",
            has_memory=False,
            state_summary={
                "market_report_excerpt": "NVDA showing strong uptrend with RSI at 65...",
                "final_decision_excerpt": "Recommend BUY based on technical and fundamental strength..."
            }
        )
        print(f"   Analysis #: {analysis_no}")

        # Test 3: Append second report
        print("\n3. Appending second report...")
        analysis_no = store.append(
            ticker="NVDA",
            date="2026-01-05",
            decision="HOLD",
            strategy_summary="Maintaining position, consolidation phase",
            has_memory=True,
            state_summary={
                "market_report_excerpt": "NVDA consolidating near recent highs...",
                "final_decision_excerpt": "Continue holding position, wait for breakout..."
            }
        )
        print(f"   Analysis #: {analysis_no}")

        # Test 4: Load all reports
        print("\n4. Loading all reports...")
        reports = store.load("NVDA")
        print(f"   Total reports: {len(reports)}")
        for r in reports:
            print(f"   - {r['date']}: {r['decision']} (analysis #{r['analysis_no']}, has_memory={r['has_memory']})")

        # Test 5: Get analysis count
        print("\n5. Get analysis count...")
        count = store.get_analysis_count("NVDA")
        print(f"   Count: {count}")

        print("\n✅ All tests passed!")

    finally:
        # Clean up
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up test directory")
