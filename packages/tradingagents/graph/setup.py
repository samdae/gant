# TradingAgents/graph/setup.py

from typing import Dict, Any, Optional, Callable
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode

from tradingagents.agents import *
from tradingagents.agents.utils.agent_states import AgentState

from .conditional_logic import ConditionalLogic


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: BaseChatModel,
        deep_thinking_llm: BaseChatModel,
        tool_nodes: Dict[str, ToolNode],
        memory,
        conditional_logic: ConditionalLogic,
        status_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        """Initialize with required components.

        FR-031: Single shared memory instance replaces 5 per-agent memories.
        """
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.memory = memory
        self.conditional_logic = conditional_logic
        self.status_callback = status_callback

    def set_status_callback(
        self, callback: Optional[Callable[[str, str, str], None]]
    ) -> None:
        self.status_callback = callback

    def _wrap_node(self, name: str, node):
        def wrapped(state):
            if self.status_callback:
                self.status_callback(name, "running", f"{name} running")
            try:
                result = node(state)
            except Exception as e:
                if self.status_callback:
                    self.status_callback(name, "error", f"{name} error: {e}")
                raise
            if self.status_callback:
                self.status_callback(name, "completed", f"{name} completed")
            return result

        return wrapped

    def setup_graph(
        self, selected_analysts=["market", "social", "news", "fundamentals"]
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
        """
        if len(selected_analysts) == 0:
            raise ValueError("Trading Agents Graph Setup Error: no analysts selected!")

        # Create analyst nodes
        analyst_nodes = {}
        delete_nodes = {}
        tool_nodes = {}

        if "market" in selected_analysts:
            analyst_nodes["market"] = self._wrap_node(
                "Market Analyst",
                create_market_analyst(self.quick_thinking_llm),
            )
            delete_nodes["market"] = create_msg_delete()
            tool_nodes["market"] = self.tool_nodes["market"]

        if "social" in selected_analysts:
            analyst_nodes["social"] = self._wrap_node(
                "Social Analyst",
                create_social_media_analyst(self.quick_thinking_llm),
            )
            delete_nodes["social"] = create_msg_delete()
            tool_nodes["social"] = self.tool_nodes["social"]

        if "news" in selected_analysts:
            analyst_nodes["news"] = self._wrap_node(
                "News Analyst",
                create_news_analyst(self.quick_thinking_llm),
            )
            delete_nodes["news"] = create_msg_delete()
            tool_nodes["news"] = self.tool_nodes["news"]

        if "fundamentals" in selected_analysts:
            analyst_nodes["fundamentals"] = self._wrap_node(
                "Fundamentals Analyst",
                create_fundamentals_analyst(self.quick_thinking_llm),
            )
            delete_nodes["fundamentals"] = create_msg_delete()
            tool_nodes["fundamentals"] = self.tool_nodes["fundamentals"]

        # Create researcher and manager nodes
        # FR-031: All agents share single HybridMemory instance
        bull_researcher_node = self._wrap_node(
            "Bull Researcher",
            create_bull_researcher(self.quick_thinking_llm),
        )
        bear_researcher_node = self._wrap_node(
            "Bear Researcher",
            create_bear_researcher(self.quick_thinking_llm),
        )
        research_manager_node = self._wrap_node(
            "Research Manager",
            create_research_manager(self.deep_thinking_llm),
        )
        trader_node = self._wrap_node(
            "Trader",
            create_trader(self.quick_thinking_llm),
        )

        # Create risk analysis nodes
        aggressive_analyst = self._wrap_node(
            "Aggressive Analyst",
            create_aggressive_debator(self.quick_thinking_llm),
        )
        neutral_analyst = self._wrap_node(
            "Neutral Analyst",
            create_neutral_debator(self.quick_thinking_llm),
        )
        conservative_analyst = self._wrap_node(
            "Conservative Analyst",
            create_conservative_debator(self.quick_thinking_llm),
        )
        risk_manager_node = self._wrap_node(
            "Risk Judge",
            create_risk_manager(self.deep_thinking_llm),
        )

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        for analyst_type, node in analyst_nodes.items():
            workflow.add_node(f"{analyst_type.capitalize()} Analyst", node)
            workflow.add_node(
                f"Msg Clear {analyst_type.capitalize()}", delete_nodes[analyst_type]
            )
            workflow.add_node(f"tools_{analyst_type}", tool_nodes[analyst_type])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Risk Judge", risk_manager_node)

        # Define edges
        # Start with the first analyst
        first_analyst = selected_analysts[0]
        workflow.add_edge(START, f"{first_analyst.capitalize()} Analyst")

        # Connect analysts in sequence
        for i, analyst_type in enumerate(selected_analysts):
            current_analyst = f"{analyst_type.capitalize()} Analyst"
            current_tools = f"tools_{analyst_type}"
            current_clear = f"Msg Clear {analyst_type.capitalize()}"

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{analyst_type}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(selected_analysts) - 1:
                next_analyst = f"{selected_analysts[i+1].capitalize()} Analyst"
                workflow.add_edge(current_clear, next_analyst)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # Add remaining edges
        workflow.add_conditional_edges(
            "Bull Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bear Researcher": "Bear Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_conditional_edges(
            "Bear Researcher",
            self.conditional_logic.should_continue_debate,
            {
                "Bull Researcher": "Bull Researcher",
                "Research Manager": "Research Manager",
            },
        )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        workflow.add_conditional_edges(
            "Aggressive Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Conservative Analyst": "Conservative Analyst",
                "Risk Judge": "Risk Judge",
            },
        )
        workflow.add_conditional_edges(
            "Conservative Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Neutral Analyst": "Neutral Analyst",
                "Risk Judge": "Risk Judge",
            },
        )
        workflow.add_conditional_edges(
            "Neutral Analyst",
            self.conditional_logic.should_continue_risk_analysis,
            {
                "Aggressive Analyst": "Aggressive Analyst",
                "Risk Judge": "Risk Judge",
            },
        )

        workflow.add_edge("Risk Judge", END)

        # Compile and return
        return workflow.compile()
