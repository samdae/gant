"""Trade Manager for virtual trading.

Manages virtual trading state, positions, and history for a single ticker.
Storage: JSON file per ticker at virtual_trade/tickers/{TICKER}/trade.json

Features:
- Atomic writes (tmp + os.replace)
- Position tracking (multiple entries with separate entry prices)
- Trade history logging
- Realized return calculation on close
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TradeManager:
    """Manages virtual trading state for tickers."""

    def __init__(self, base_dir: str):
        """Initialize the trade manager.

        Args:
            base_dir: Base directory for virtual trade data
                     (e.g., "virtual_trade/tickers")
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        # In-memory cache: ticker -> trade state
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _get_trade_path(self, ticker: str) -> str:
        """Get path to trade.json for a ticker."""
        ticker_dir = os.path.join(self.base_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        return os.path.join(ticker_dir, "trade.json")

    def load(self, ticker: str) -> Dict[str, Any]:
        """Load trade state for a ticker.

        If file doesn't exist or is corrupted, creates initial trade state.

        Args:
            ticker: Ticker symbol (e.g., "NVDA")

        Returns:
            Trade state dict
        """
        # Check cache first
        if ticker in self._cache:
            return self._cache[ticker]

        trade_path = self._get_trade_path(ticker)

        # Load from file
        if os.path.exists(trade_path):
            try:
                with open(trade_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)

                # Validate required fields
                required_fields = ["ticker", "cash", "status"]
                if all(field in state for field in required_fields):
                    self._cache[ticker] = state
                    return state
                else:
                    logger.warning(
                        f"trade.json for {ticker} missing required fields, "
                        "reinitializing"
                    )
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(
                    f"Failed to load trade.json for {ticker}: {e}, "
                    "creating new trade state"
                )

        # Create initial trade state
        initial_state = self.create_initial_trade(ticker)
        self._cache[ticker] = initial_state
        self.save(ticker)
        return initial_state

    def save(self, ticker: str):
        """Save trade state for a ticker using atomic write.

        Args:
            ticker: Ticker symbol
        """
        if ticker not in self._cache:
            logger.warning(f"No cached state for {ticker}, skipping save")
            return

        state = self._cache[ticker]
        trade_path = self._get_trade_path(ticker)

        # Atomic write: tmp + os.replace
        tmp_path = trade_path + ".tmp"

        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)

            # Atomic replace (works on both Unix and Windows)
            os.replace(tmp_path, trade_path)

            logger.info(f"Saved trade state for {ticker}")

        except Exception as e:
            logger.error(f"Error saving trade state for {ticker}: {e}")
            # Clean up tmp file if it exists
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except:
                    pass
            raise

    def create_initial_trade(
        self,
        ticker: str,
        initial_capital: float = 1000.0
    ) -> Dict[str, Any]:
        """Create initial trade state for a ticker.

        Args:
            ticker: Ticker symbol
            initial_capital: Starting cash amount

        Returns:
            Initial trade state dict
        """
        return {
            "ticker": ticker,
            "initial_capital": initial_capital,
            "cash": initial_capital,
            "status": "open",
            "positions": [],
            "strategy": {
                "stop_loss": None,
                "target": None,
                "next_action": "HOLD"
            },
            "history": [],
            "closed_date": None,
            "realized_return_pct": None,
            "total_invested": None,
            "total_returned": None,
            "profit": None,
        }

    def open_position(
        self,
        ticker: str,
        shares: int,
        price: float,
        date: str
    ) -> Dict[str, Any]:
        """Open a new position (buy shares).

        Args:
            ticker: Ticker symbol
            shares: Number of shares to buy
            price: Entry price per share
            date: Entry date (YYYY-MM-DD)

        Returns:
            Updated trade state

        Raises:
            ValueError: If insufficient cash or invalid parameters
        """
        state = self.load(ticker)

        # Validate parameters
        if shares <= 0:
            raise ValueError(f"shares must be positive, got {shares}")
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")

        # Check cash balance
        cost = shares * price
        if state["cash"] < cost:
            raise ValueError(
                f"Insufficient cash: need {cost}, have {state['cash']}"
            )

        # Deduct cash
        state["cash"] -= cost

        # Add position
        state["positions"].append({
            "shares": shares,
            "entry_price": price,
            "entry_date": date
        })

        # Update cache
        self._cache[ticker] = state

        logger.info(
            f"Opened position for {ticker}: {shares} shares @ ${price} "
            f"on {date}, remaining cash: ${state['cash']:.2f}"
        )

        return state

    def close_all_positions(
        self,
        ticker: str,
        current_price: float,
        date: str
    ) -> Dict[str, float]:
        """Close all positions (sell all shares).

        Args:
            ticker: Ticker symbol
            current_price: Current price per share
            date: Close date (YYYY-MM-DD)

        Returns:
            Dict with realized_return_pct, profit, total_invested, total_returned
        """
        state = self.load(ticker)

        if not state["positions"]:
            logger.warning(f"No positions to close for {ticker}")
            return {
                "realized_return_pct": 0.0,
                "profit": 0.0,
                "total_invested": 0.0,
                "total_returned": 0.0,
            }

        # Calculate returns
        result = self.calculate_realized_return(ticker, current_price)

        # Add proceeds to cash
        state["cash"] += result["total_returned"]

        # Clear positions
        state["positions"] = []

        # Mark as closed
        state["status"] = "closed"
        state["closed_date"] = date
        state["realized_return_pct"] = result["realized_return_pct"]
        state["total_invested"] = result["total_invested"]
        state["total_returned"] = result["total_returned"]
        state["profit"] = result["profit"]

        # Update cache
        self._cache[ticker] = state

        logger.info(
            f"Closed all positions for {ticker} on {date}: "
            f"return {result['realized_return_pct']:.2f}%, "
            f"profit ${result['profit']:.2f}"
        )

        return result

    def calculate_realized_return(
        self,
        ticker: str,
        current_price: float
    ) -> Dict[str, float]:
        """Calculate realized return for current positions.

        Args:
            ticker: Ticker symbol
            current_price: Current price per share

        Returns:
            Dict with realized_return_pct, profit, total_invested, total_returned
        """
        state = self.load(ticker)

        if not state["positions"]:
            return {
                "realized_return_pct": 0.0,
                "profit": 0.0,
                "total_invested": 0.0,
                "total_returned": 0.0,
            }

        # Sum up all positions
        total_invested = sum(
            pos["shares"] * pos["entry_price"]
            for pos in state["positions"]
        )

        total_shares = sum(pos["shares"] for pos in state["positions"])
        total_returned = total_shares * current_price

        profit = total_returned - total_invested

        if total_invested > 0:
            realized_return_pct = (profit / total_invested) * 100.0
        else:
            realized_return_pct = 0.0

        return {
            "realized_return_pct": realized_return_pct,
            "profit": profit,
            "total_invested": total_invested,
            "total_returned": total_returned,
        }

    def get_position_summary(self, ticker: str) -> str:
        """Get human-readable position summary.

        Args:
            ticker: Ticker symbol

        Returns:
            Position summary string
            (e.g., "Holding 2 shares NVDA avg $257.50" or "No position")
        """
        state = self.load(ticker)

        if not state["positions"]:
            return f"No position in {ticker}"

        total_shares = sum(pos["shares"] for pos in state["positions"])
        total_cost = sum(
            pos["shares"] * pos["entry_price"]
            for pos in state["positions"]
        )

        avg_price = total_cost / total_shares if total_shares > 0 else 0.0

        return f"Holding {total_shares} shares {ticker} avg ${avg_price:.2f}"

    def append_history(
        self,
        ticker: str,
        date: str,
        analysis_no: int,
        decision: str,
        action: str,
        rationale: str
    ):
        """Append an entry to trade history.

        Args:
            ticker: Ticker symbol
            date: Date (YYYY-MM-DD)
            analysis_no: Analysis number (incremental)
            decision: BUY | SELL | HOLD
            action: Action taken description
            rationale: Reason for action
        """
        state = self.load(ticker)

        entry = {
            "date": date,
            "analysis_no": analysis_no,
            "decision": decision,
            "action": action,
            "rationale": rationale,
            "cash_after": state["cash"],
        }

        state["history"].append(entry)
        self._cache[ticker] = state

        logger.info(
            f"Appended history for {ticker}: {date} - {decision} - {action}"
        )


if __name__ == "__main__":
    # Example usage
    print("Testing TradeManager...")

    import tempfile
    import shutil

    # Create temp directory for testing
    temp_dir = tempfile.mkdtemp()
    print(f"Test directory: {temp_dir}")

    try:
        manager = TradeManager(base_dir=os.path.join(temp_dir, "tickers"))

        # Test 1: Create initial trade
        print("\n1. Creating initial trade for NVDA...")
        state = manager.load("NVDA")
        print(f"   Initial cash: ${state['cash']:.2f}")
        print(f"   Status: {state['status']}")
        print(f"   Summary: {manager.get_position_summary('NVDA')}")

        # Test 2: Open position
        print("\n2. Opening position: 3 shares @ $250.00...")
        manager.open_position("NVDA", shares=3, price=250.0, date="2026-01-01")
        manager.save("NVDA")
        print(f"   Cash after: ${state['cash']:.2f}")
        print(f"   Summary: {manager.get_position_summary('NVDA')}")

        # Test 3: Calculate current return
        print("\n3. Calculate return @ $270.00...")
        result = manager.calculate_realized_return("NVDA", current_price=270.0)
        print(f"   Invested: ${result['total_invested']:.2f}")
        print(f"   Current value: ${result['total_returned']:.2f}")
        print(f"   Profit: ${result['profit']:.2f}")
        print(f"   Return: {result['realized_return_pct']:.2f}%")

        # Test 4: Append history
        print("\n4. Appending history entry...")
        manager.append_history(
            "NVDA",
            date="2026-01-05",
            analysis_no=2,
            decision="HOLD",
            action="Continue holding position",
            rationale="Strong uptrend continues"
        )

        # Test 5: Close all positions
        print("\n5. Closing all positions @ $280.00...")
        close_result = manager.close_all_positions("NVDA", current_price=280.0, date="2026-01-10")
        manager.save("NVDA")
        print(f"   Return: {close_result['realized_return_pct']:.2f}%")
        print(f"   Profit: ${close_result['profit']:.2f}")
        print(f"   Final cash: ${manager.load('NVDA')['cash']:.2f}")
        print(f"   Status: {manager.load('NVDA')['status']}")

        print("\n✅ All tests passed!")

    finally:
        # Clean up
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up test directory")
