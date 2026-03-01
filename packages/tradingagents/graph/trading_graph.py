# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from datetime import date
from typing import Dict, Any, Tuple, List, Optional, Callable

from langgraph.prebuilt import ToolNode

from tradingagents.llm_clients import create_llm_client

from tradingagents.agents import *
from tradingagents.default_config import DEFAULT_CONFIG
# FR-031: Single HybridMemory instance (replaces 5 per-agent instances)
from tradingagents.memory.hybrid_memory import HybridMemory
from tradingagents.agents.utils.agent_states import (
    AgentState,
    InvestDebateState,
    RiskDebateState,
)
from tradingagents.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
from tradingagents.agents.utils.agent_utils import (
    get_stock_data,
    get_indicators,
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
    get_news,
    get_insider_transactions,
    get_global_news,
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
        callbacks: Optional[List] = None,
        status_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
            callbacks: Optional list of callback handlers (e.g., for tracking LLM/tool stats)
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG
        self.callbacks = callbacks or []
        self.status_callback = status_callback

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs with provider-specific thinking configuration
        llm_kwargs = self._get_provider_kwargs()

        # Add callbacks to kwargs if provided (passed to LLM constructor)
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deep_thinking_llm = deep_client.get_llm()
        self.quick_thinking_llm = quick_client.get_llm()

        # FR-031: Single HybridMemory instance shared by all agents
        self.memory = HybridMemory("shared_memory", self.config)

        # Bootstrap tagging flag (FR-019)
        self._last_had_memory = False

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic()
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.memory,
            self.conditional_logic,
            status_callback=self.status_callback,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.deep_thinking_llm)  # FR-031: Changed to deep_thinking_llm
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def set_status_callback(
        self, callback: Optional[Callable[[str, str, str], None]]
    ) -> None:
        self.status_callback = callback
        self.graph_setup.set_status_callback(callback)

    def _get_provider_kwargs(self) -> Dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}

        # Provider name doubles as auth_mode
        provider = self.config.get("llm_provider", "gemini-cli")
        kwargs["auth_mode"] = provider

        return kwargs

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def propagate(self, company_name, trade_date, depth=None, current_position="",
                  macro_context=""):
        """Run the trading agents graph for a company on a specific date.

        Args:
            company_name: Ticker symbol (e.g. "NVDA")
            trade_date: Analysis date "YYYY-MM-DD"
            depth: Optional debate rounds (1=shallow, 3=medium, 5=deep).
                   Sets both max_debate_rounds and max_risk_discuss_rounds.
                   If None, uses config defaults.
            current_position: (DEPRECATED - FR-021) No longer used by 12 agents.
                             Keep for backward compatibility but value is ignored.
            macro_context: v7 macro indicators + sector health text for all agents.

        Returns:
            Tuple of (final_state, (decision, strategy)):
            - final_state: Full agent state dict
            - decision: "BUY", "SELL", or "HOLD"
            - strategy: Optional dict with conviction/allocation from Judge
        """

        if depth is not None:
            self.config["max_debate_rounds"] = depth
            self.config["max_risk_discuss_rounds"] = depth

        self.ticker = company_name

        init_agent_state = self.propagator.create_initial_state(
            company_name, trade_date, current_position, macro_context=macro_context,
        )
        args = self.propagator.get_graph_args()

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    msg = chunk["messages"][-1]
                    # Compact pretty_print: collapse excessive blank lines
                    import re, io, sys

                    buf = io.StringIO()
                    old_stdout = sys.stdout
                    sys.stdout = buf
                    msg.pretty_print()
                    sys.stdout = old_stdout
                    output = re.sub(r"\n{3,}", "\n\n", buf.getvalue())
                    print(output, end="")
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Set bootstrap tagging flag (FR-019)
        # FR-031: Single memory instance — check once
        self._last_had_memory = self.memory.last_query_had_results

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and strategy
        decision, strategy = self.process_signal(final_state["final_trade_decision"])
        return final_state, (decision, strategy)

    def _log_state(self, trade_date, final_state):
        """Log the final state to in-memory dict (P3-A: file I/O removed).

        Legacy eval_results/ file output has been removed per FR-030.
        State data is now stored in DB via reports table.
        In-memory dict retained for debugging/introspection only.
        """
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "aggressive_history": final_state["risk_debate_state"][
                    "aggressive_history"
                ],
                "conservative_history": final_state["risk_debate_state"][
                    "conservative_history"
                ],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

    def reflect_and_remember(self, position_id: int, db):
        """Reflect on a closed position and store to memory.

        FR-031: Simplified reflection - now takes position_id and db,
        calls Reflector.reflect_on_position() once instead of 5 per-agent calls.

        Args:
            position_id: Position ID to reflect on (must be closed)
            db: Database instance for accessing repositories

        Note: This method no longer uses curr_state or individual agent memories.
              All reflection is centralized and stored via HybridMemory.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Call centralized reflection (FR-031)
            reflection_result = self.reflector.reflect_on_position(
                position_id=position_id,
                db=db
            )

            # Store to HybridMemory (which stores to SQLite + ChromaDB)
            # FR-033: HybridMemory now uses ReflectionRepository internally
            # We pass position_id in metadata for proper storage
            from tradingagents.storage import PositionRepository
            position_repo = PositionRepository(db)
            position = position_repo.get_by_id(position_id)
            
            if not position:
                logger.error(f"Position {position_id} not found for reflection storage")
                return

            ticker = position["ticker"]

            # FR-029: Auto-tag metadata (sector, industry, market from yfinance)
            sector = None
            industry = None
            market = None
            
            try:
                import yfinance as yf
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info
                
                sector = info.get("sector")
                industry = info.get("industry")
                # FR-029: Prefer fullExchangeName; fall back to exchange
                market = info.get("fullExchangeName") or info.get("exchange")
                if info.get("quoteType") == "CRYPTOCURRENCY":
                    market = "Crypto"
                
                logger.info(
                    f"Fetched metadata for {ticker}: sector={sector}, industry={industry}, market={market}"
                )
            except Exception as e:
                logger.warning(f"Failed to fetch yfinance metadata for {ticker}: {e}")

            # Store reflection via HybridMemory
            # Note: HybridMemory.add_situations expects (situation, recommendation) tuples
            # We store (key_lessons, reflection) to match RAG query patterns
            metadata = {
                "position_id": position_id,
                "ticker": ticker,
                "outcome": reflection_result["outcome"],
                "return_pct": reflection_result["return_pct"],
                # FR-029: Add auto-tagged metadata
                "sector": sector,
                "industry": industry,
                "market": market,
            }

            # FR-031: Store via single HybridMemory instance
            self.memory.add_situations(
                [(reflection_result["key_lessons"], reflection_result["reflection"])],
                metadata=metadata
            )

            logger.info(
                f"Reflection stored for position {position_id} ({ticker}): "
                f"{reflection_result['outcome']} ({reflection_result['return_pct']:.2f}%)"
            )

        except Exception as e:
            logger.error(f"Failed to reflect and remember for position {position_id}: {e}")
            # Don't raise - reflection failure shouldn't block scheduler

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision and strategy."""
        return self.signal_processor.process_signal(full_signal)
