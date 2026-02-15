import os


def _get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_database_url() -> str:
    for key in ("SUPABASE_DB_URL", "TRADINGAGENTS_DB_URL", "DATABASE_URL"):
        value = os.getenv(key)
        if value:
            return value

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DB")
    if not (user and password and database):
        return ""

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # Data cache window (yfinance/stockstats)
    "stock_download_days": int(os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_DAYS", "330")),
    "stock_download_buffer_days": int(
        os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_BUFFER_DAYS", "300")
    ),
    "stock_cache_stale_days": int(os.getenv("TRADINGAGENTS_STOCK_CACHE_STALE_DAYS", "3")),
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
    # FR-030: Database URL (Postgres)
    "database_path": _get_database_url(),
    # FR-030: ChromaDB path (Vector store)
    "chroma_path": os.getenv(
        "TRADINGAGENTS_CHROMA_PATH",
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")), "memory", "chroma")
    ),
    "default_initial_capital": 1000.0,
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": _get_env_bool("TRADINGAGENTS_SCHEDULER_ENABLED", False),
}
