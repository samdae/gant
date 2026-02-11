import os
import sys
import asyncio
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG


async def main():
    print("🥊 [Antigravity] Trading System Initializing... 🥊")

    # 1. Configuration
    config = DEFAULT_CONFIG.copy()

    # Force Antigravity settings
    config["llm_provider"] = "antigravity"
    config["deep_think_llm"] = "gemini-3-pro-high"  # The Beast
    config["quick_think_llm"] = "gemini-3-flash"

    print(f"   Provider: {config['llm_provider']}")
    print(f"   Deep Model: {config['deep_think_llm']}")
    print(f"   Quick Model: {config['quick_think_llm']}")

    # 2. Initialize System
    print("\n🏗️  Initializing Trading Agent Graph...")
    # Select analysts (excluding news if desired, but keeping default for now)
    analysts = ["market", "social", "news", "fundamentals"]
    system = TradingAgentsGraph(selected_analysts=analysts, config=config, debug=True)

    # 3. Define Task
    ticker = "AAPL"

    # Run for a specific date (e.g., yesterday)
    # Note: The system usually runs day-by-day in a loop.
    # Here we simulate a single day execution for testing.
    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\n🎯 Target: {ticker}")
    print(f"📅 Date: {target_date}")

    # 4. Run!
    print("\n🚀 Launching Antigravity Engine...")
    print("(If browser opens, please authenticate!)\n")

    try:
        # Propagate (Run the graph for one day)
        final_state, processed_signal = system.propagate(ticker, target_date)

        # 5. Output Result
        print("\n" + "=" * 50)
        print("✅ Trading Decision Reached")
        print("=" * 50)

        # Signal is usually: 1 (Buy), -1 (Sell), 0 (Hold) or similar float
        print(f"\n📢 Signal Value: {processed_signal}")

        decision = final_state.get("final_trade_decision", {})
        if decision:
            print(f"📝 Raw Decision: {decision}")
        else:
            print("\n❌ No final decision returned.")

    except Exception as e:
        print(f"\n💥 CRASHED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Ensure event loop for async operations if needed (though propagate seems synchronous/internal async)
    # The original main.py doesn't use asyncio run, but we wrap it just in case tools need it.
    # Check if system.propagate is async? No, based on source it uses self.graph.invoke which is sync (or graph.ainvoke for async).
    # trading_graph.py uses invoke(), so it's synchronous.

    # Run synchronous main wrapper
    asyncio.run(main())
