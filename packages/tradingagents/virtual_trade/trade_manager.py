"""Trade Manager for virtual trading (DB-based).

FR-030: Refactored to use SQLite repositories instead of JSON files.

Manages virtual trading state, positions, and history for tickers.
Storage: SQLite positions + trades tables (via repositories).
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TradeManager:
    """Manages virtual trading state for tickers using SQLite."""

    def __init__(self, db):
        """Initialize the trade manager.

        FR-030: Changed from file-based to DB-based storage.

        Args:
            db: Database instance for accessing repositories
        """
        self.db = db

        # Import repositories
        from tradingagents.storage import PositionRepository, TradeRepository
        
        self.position_repo = PositionRepository(db)
        self.trade_repo = TradeRepository(db)

        logger.info("TradeManager initialized (DB-based)")

    def load(self, ticker: str) -> Dict[str, Any]:
        """Load trade state for a ticker.

        FR-030: Loads from SQLite positions table instead of JSON file.

        Args:
            ticker: Ticker symbol (e.g., "NVDA")

        Returns:
            Trade state dict with keys:
                - ticker: str
                - position: dict or None (active position data)
                - status: str ('open' if active position, 'no_position' otherwise)
        """
        # Get active position
        position = self.position_repo.get_active(ticker)

        if position:
            return {
                "ticker": ticker,
                "position": position,
                "status": "open",
                "shares": position["shares"],
                "avg_cost": position.get("avg_cost"),
            }
        else:
            return {
                "ticker": ticker,
                "position": None,
                "status": "no_position",
                "shares": 0,
                "avg_cost": None,
            }

    def open_position(
        self,
        ticker: str,
        shares: float,
        price: float,
        date: str,
        commit: bool = True,
        conn=None,
    ) -> Dict[str, Any]:
        """Open a new position or add to existing position (buy shares).

        FR-030: Uses PositionRepository.create() or update_shares().

        Args:
            ticker: Ticker symbol
            shares: Number of shares to buy
            price: Entry price per share
            date: Entry date (YYYY-MM-DD)

        Returns:
            Updated trade state

        Raises:
            ValueError: If invalid parameters
        """
        # Validate parameters
        shares = self._round_shares(shares)
        price = self._round_price(price)
        if shares <= 0:
            raise ValueError(f"shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Get active position
        state = self.load(ticker)
        position = state.get("position")

        if position:
            # Add to existing position
            position_id = position["id"]
            old_shares = float(position["shares"])
            old_avg_cost = self._round_price(position.get("avg_cost", 0))

            # Calculate new average cost
            total_cost = (old_shares * old_avg_cost) + (shares * price)
            new_shares = self._round_shares(old_shares + shares)
            new_avg_cost = self._round_price(total_cost / new_shares)

            # Update position
            self.position_repo.update_shares(
                position_id,
                new_shares,
                new_avg_cost,
                commit=commit,
                conn=conn,
            )

            logger.info(
                f"Added to position {position_id} for {ticker}: "
                f"+{self._format_shares(shares)} shares @ ${price:.2f}, "
                f"total {self._format_shares(new_shares)} shares @ ${new_avg_cost:.2f}"
            )
        else:
            # Create new position
            position_id = self.position_repo.create(ticker, commit=commit, conn=conn)

            # Update with initial shares and cost
            self.position_repo.update_shares(
                position_id,
                shares,
                price,
                commit=commit,
                conn=conn,
            )

            logger.info(
                f"Opened new position {position_id} for {ticker}: "
                f"{self._format_shares(shares)} shares @ ${price:.2f}"
            )

        # Reload state
        return self.load(ticker)

    def close_positions(
        self,
        ticker: str,
        shares: float,
        current_price: float,
        date: str,
        commit: bool = True,
        conn=None,
    ) -> Dict[str, Any]:
        """Close positions partially (sell specified number of shares).

        FR-030: Uses PositionRepository.update_shares().

        Args:
            ticker: Ticker symbol
            shares: Number of shares to sell
            current_price: Current price per share
            date: Close date (YYYY-MM-DD)

        Returns:
            Dict with:
                - realized_return_pct: float (based on avg_cost)
                - profit: float
                - remaining_shares: int

        Raises:
            ValueError: If shares exceed available shares
        """
        state = self.load(ticker)
        position = state.get("position")

        if not position:
            logger.warning(f"No position to close for {ticker}")
            return {
                "realized_return_pct": 0.0,
                "profit": 0.0,
                "remaining_shares": 0,
            }

        position_id = position["id"]
        total_shares = float(position["shares"])
        avg_cost = self._round_price(position.get("avg_cost", 0))
        current_price = self._round_price(current_price)

        shares = self._round_shares(shares)
        if shares > total_shares + 1e-8:
            raise ValueError(
                f"Insufficient shares: trying to sell {shares}, "
                f"but only have {total_shares}"
            )

        # Calculate profit based on average cost
        profit = (current_price - avg_cost) * shares
        realized_return_pct = (
            ((current_price - avg_cost) / avg_cost * 100.0)
            if avg_cost > 0 else 0.0
        )

        # Update position shares
        remaining_shares = self._round_shares(total_shares - shares)
        if abs(remaining_shares) <= 1e-8:
            remaining_shares = 0.0
        
        if remaining_shares > 0:
            # Partial close - update shares
            self.position_repo.update_shares(
                position_id,
                remaining_shares,
                avg_cost,
                commit=commit,
                conn=conn,
            )
        else:
            # Full close - mark position as closed
            self.position_repo.close_position(
                position_id,
                realized_return_pct,
                commit=commit,
                conn=conn,
            )

        logger.info(
            f"Closed {self._format_shares(shares)} shares for {ticker}: "
            f"return {realized_return_pct:.2f}%, profit ${profit:.2f}, "
            f"remaining {self._format_shares(remaining_shares)} shares"
        )

        return {
            "realized_return_pct": realized_return_pct,
            "profit": profit,
            "remaining_shares": remaining_shares,
        }

    def close_all_positions(
        self,
        ticker: str,
        current_price: float,
        date: str,
        commit: bool = True,
        conn=None,
    ) -> Dict[str, float]:
        """Close all positions (sell all shares).

        FR-030: Wrapper around close_positions() that sells all shares.

        Args:
            ticker: Ticker symbol
            current_price: Current price per share
            date: Close date (YYYY-MM-DD)

        Returns:
            Dict with realized_return_pct, profit, total_invested, total_returned
        """
        state = self.load(ticker)
        position = state.get("position")

        if not position:
            logger.warning(f"No position to close for {ticker}")
            return {
                "realized_return_pct": 0.0,
                "profit": 0.0,
                "total_invested": 0.0,
                "total_returned": 0.0,
            }

        total_shares = float(position["shares"])
        avg_cost = self._round_price(position.get("avg_cost", 0))

        total_invested = total_shares * avg_cost
        total_returned = total_shares * current_price

        # Use close_positions to handle the sale
        result = self.close_positions(
            ticker,
            total_shares,
            current_price,
            date,
            commit=commit,
            conn=conn,
        )

        logger.info(
            f"Closed all positions for {ticker}: "
            f"return {result['realized_return_pct']:.2f}%, "
            f"profit ${result['profit']:.2f}"
        )

        return {
            "realized_return_pct": result["realized_return_pct"],
            "profit": result["profit"],
            "total_invested": total_invested,
            "total_returned": total_returned,
        }

    def calculate_realized_return(
        self,
        ticker: str,
        current_price: float
    ) -> Dict[str, float]:
        """Calculate realized return for current position.

        FR-030: Uses PositionRepository.get_active().

        Args:
            ticker: Ticker symbol
            current_price: Current price per share

        Returns:
            Dict with realized_return_pct, profit, total_invested, total_returned
        """
        state = self.load(ticker)
        position = state.get("position")

        if not position:
            return {
                "realized_return_pct": 0.0,
                "profit": 0.0,
                "total_invested": 0.0,
                "total_returned": 0.0,
            }

        total_shares = float(position["shares"])
        avg_cost = self._round_price(position.get("avg_cost", 0))

        total_invested = total_shares * avg_cost
        total_returned = total_shares * current_price
        profit = total_returned - total_invested

        realized_return_pct = (
            (profit / total_invested * 100.0)
            if total_invested > 0 else 0.0
        )

        return {
            "realized_return_pct": realized_return_pct,
            "profit": profit,
            "total_invested": total_invested,
            "total_returned": total_returned,
        }

    def get_position_summary(self, ticker: str) -> str:
        """Get human-readable position summary.

        FR-030: Uses PositionRepository.get_active().

        Args:
            ticker: Ticker symbol

        Returns:
            Position summary string
            (e.g., "Holding 2 shares NVDA avg $257.50" or "No position")
        """
        state = self.load(ticker)
        position = state.get("position")

        if not position or position["shares"] == 0:
            return f"No position in {ticker}"

        shares = position["shares"]
        avg_cost = self._round_price(position.get("avg_cost", 0))

        return (
            f"Holding {self._format_shares(float(shares))} shares {ticker} "
            f"avg ${avg_cost:.2f}"
        )

    @staticmethod
    def _round_shares(value: float) -> float:
        return round(float(value), 2)

    @staticmethod
    def _round_price(value: float) -> float:
        return round(float(value), 2)

    @staticmethod
    def _format_shares(value: float) -> str:
        text = f"{float(value):.2f}".rstrip("0").rstrip(".")
        return text if text else "0"

    # Note: append_history is removed (FR-030)
    # Trade history is now stored via TradeRepository.create() directly in scheduler


if __name__ == "__main__":
    # Test trade manager
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        import os
        from tradingagents.storage import Database

        db_url = os.getenv("SUPABASE_DB_URL")
        if not db_url:
            print("SUPABASE_DB_URL not set; skipping test")
            raise SystemExit(0)

        db = Database(db_url)
        db.init_schema()

        manager = TradeManager(db)

        # Test 1: Load (no position)
        print("\n1. Loading state for NVDA (no position)...")
        state = manager.load("NVDA")
        print(f"   Status: {state['status']}")
        print(f"   Summary: {manager.get_position_summary('NVDA')}")

        # Test 2: Open position
        print("\n2. Opening position: 3 shares @ $250.00...")
        manager.open_position("NVDA", shares=3, price=250.0, date="2026-01-01")
        state = manager.load("NVDA")
        print(f"   Shares: {state['shares']}")
        print(f"   Summary: {manager.get_position_summary('NVDA')}")

        # Test 3: Add to position
        print("\n3. Adding to position: 2 shares @ $260.00...")
        manager.open_position("NVDA", shares=2, price=260.0, date="2026-01-05")
        state = manager.load("NVDA")
        print(f"   Shares: {state['shares']}, Avg Cost: ${state['avg_cost']:.2f}")

        # Test 4: Calculate current return
        print("\n4. Calculate return @ $270.00...")
        result = manager.calculate_realized_return("NVDA", current_price=270.0)
        print(f"   Invested: ${result['total_invested']:.2f}")
        print(f"   Current value: ${result['total_returned']:.2f}")
        print(f"   Profit: ${result['profit']:.2f}")
        print(f"   Return: {result['realized_return_pct']:.2f}%")

        # Test 5: Partial close
        print("\n5. Partial close: 2 shares @ $275.00...")
        close_result = manager.close_positions("NVDA", shares=2, current_price=275.0, date="2026-01-10")
        print(f"   Return: {close_result['realized_return_pct']:.2f}%")
        print(f"   Remaining: {close_result['remaining_shares']} shares")

        # Test 6: Close all
        print("\n6. Closing all positions @ $280.00...")
        close_result = manager.close_all_positions("NVDA", current_price=280.0, date="2026-01-15")
        print(f"   Return: {close_result['realized_return_pct']:.2f}%")
        print(f"   Profit: ${close_result['profit']:.2f}")

        # Test 7: Check final state
        print("\n7. Checking final state...")
        state = manager.load("NVDA")
        print(f"   Status: {state['status']}")
        print(f"   Summary: {manager.get_position_summary('NVDA')}")

        print("\n✅ All tests passed!")

        db.close()

    finally:
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up test directory")
