import os
from urllib.parse import quote


def _get_env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_database_url() -> str:
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
    port = os.getenv("POSTGRES_PORT") or "5432"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{quote(database, safe='')}"

DEFAULT_CONFIG = {
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
        "dataflows/data_cache",
    ),
    # Data cache window (yfinance/stockstats)
    "stock_download_days": int(os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_DAYS") or "330"),
    "stock_download_buffer_days": int(
        os.getenv("TRADINGAGENTS_STOCK_DOWNLOAD_BUFFER_DAYS") or "300"
    ),
    "stock_cache_stale_days": int(os.getenv("TRADINGAGENTS_STOCK_CACHE_STALE_DAYS") or "3"),
    # LLM settings — uses Google OAuth, no API keys
    # Providers: "gemini-cli" (default), "antigravity", "codex"
    # Override via LLM_PROVIDER env var
    "llm_provider": os.getenv("LLM_PROVIDER", "gemini-cli"),
    "deep_think_llm": os.getenv("CODEX_MODEL", "gpt-6.2-sol") if os.getenv("LLM_PROVIDER", "").lower() == "codex" else "gemini-3-pro-high",
    "quick_think_llm": os.getenv("CODEX_MODEL", "gpt-6.2-sol") if os.getenv("LLM_PROVIDER", "").lower() == "codex" else "gemini-3-flash",
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
    "database_path": get_database_url(),
    # FR-030: ChromaDB path (Vector store)
    "chroma_path": os.getenv(
        "TRADINGAGENTS_CHROMA_PATH",
        os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")), "memory", "chroma")
    ),
    "rag_top_k": int(os.getenv("RAG_TOP_K") or "1"),
    # Portfolio mode (FR-056~061)
    "portfolio_enabled": _get_env_bool("PORTFOLIO_ENABLED", False),
    "portfolio_initial_capital": float(os.getenv("PORTFOLIO_INITIAL_CAPITAL") or "100000000"),
    "portfolio_fee_enabled": _get_env_bool("PORTFOLIO_FEE_ENABLED", True),
    "portfolio_snapshot_retention_days": int(os.getenv("PORTFOLIO_SNAPSHOT_RETENTION_DAYS") or "14"),
    "portfolio_read_auth_required": _get_env_bool("PORTFOLIO_READ_AUTH_REQUIRED", False),
    "exchange_rate_cache_ttl": int(os.getenv("EXCHANGE_RATE_CACHE_TTL") or "3600"),
    "exchange_rate_fallback": float(os.getenv("EXCHANGE_RATE_FALLBACK") or "1380.0"),
    "api_rate_limit_per_min": int(os.getenv("API_RATE_LIMIT_PER_MIN") or "120"),
    "default_initial_capital": 5000.0,
    # FR-016: Scheduler
    "schedules": [],  # List[{"ticker": str, "interval_days": int}]
    "scheduler_enabled": _get_env_bool("TRADINGAGENTS_SCHEDULER_ENABLED", False),
}
