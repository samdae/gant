import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", "./results"),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # LLM settings — uses Google OAuth, no API keys
    # Providers: "gemini-cli" (default, uses ~/.gemini creds) or "antigravity"
    # Override via LLM_PROVIDER env var
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini-cli"),
    "deep_think_llm": "gemini-3-pro-high",
    "quick_think_llm": "gemini-3-flash",
    "backend_url": None,
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",  # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",  # Options: alpha_vantage, yfinance
        "news_data": "yfinance",  # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # FR-015: Hybrid RAG Memory
    "memory_dir": os.getenv(
        "TRADINGAGENTS_MEMORY_DIR",
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")), "memory", "data")
    ),
    # FR-013: Virtual Trading
    "virtual_trade_dir": os.getenv(
        "TRADINGAGENTS_TRADE_DIR",
        os.path.join(os.path.dirname(os.path.abspath(os.path.join(os.path.dirname(__file__), "."))), "virtual_trade", "tickers")
    ),
    "default_initial_capital": 1000.0,
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int, "initial_capital": float}]
    "scheduler_enabled": False,
}
