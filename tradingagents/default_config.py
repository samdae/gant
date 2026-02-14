import os

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
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
    # FR-030: Database path (SQLite)
    "database_path": os.getenv(
        "TRADINGAGENTS_DATABASE_PATH",
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")), "memory", "trading.db")
    ),
    # FR-030: ChromaDB path (Vector store)
    "chroma_path": os.getenv(
        "TRADINGAGENTS_CHROMA_PATH",
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")), "memory", "chroma")
    ),
    "default_initial_capital": 1000.0,
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": False,
}
