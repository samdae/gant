"""Collect the optional archive before the research observation or trade report is frozen."""

import logging
import os
import re
from pathlib import Path

from .bounded_process import bounded_run

logger = logging.getLogger(__name__)
COLLECTOR_ROOT = "GANT_LAST30DAYS_COLLECTOR_ROOT"
COLLECTION_TIMEOUT = 110
MODEL_TURN_RESERVE = 300
# Trade schedules also accept Yahoo's hyphenated dollar pairs (e.g. BTC-USD).
SYMBOL_PATTERNS = {"us": r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?", "kr": r"[0-9]{6}\.(?:KS|KQ)"}


def collect_scheduled_issues(ticker, market, *, seconds_to_entry=None):
    root_setting = os.environ.get(COLLECTOR_ROOT)
    if not root_setting:
        return
    # Leave time for the original inference path when a delayed run approaches entry.
    if seconds_to_entry is not None and seconds_to_entry < COLLECTION_TIMEOUT + MODEL_TURN_RESERVE:
        logger.info("last30days deferred for %s near forecast entry", ticker)
        return
    try:
        pattern = SYMBOL_PATTERNS.get(market)
        if pattern is None or not re.fullmatch(pattern, ticker):
            raise ValueError("Unsupported instrument")
        root = Path(root_setting)
        if not root.is_absolute() or root.drive.startswith("\\\\"):
            raise ValueError("Local absolute collector root required")
        python = root / ".venv" / "Scripts" / "python.exe"
        command = [str(python), "-I", "-X", "utf8", "-m",
                   "tradingagents.forecast_lab.scheduled_issues", "--ticker", ticker, "--market", market]
        # The archive resolves its own protected settings. Never inherit the v2 database,
        # console token, model credentials, virtual environment or Python import path.
        env = {k: os.environ[k] for k in (
            "SystemRoot", "WINDIR", "APPDATA", "LOCALAPPDATA", "USERPROFILE",
            "TEMP", "TMP", "ProgramFiles", "ProgramFiles(x86)", "ProgramData",
        ) if k in os.environ}
        env["PATH"] = str(Path(env["SystemRoot"]) / "System32")
        env["GANT_LAST30DAYS_SCHEDULED_HANDSHAKE"] = "1"
        bounded_run(command, "start\n", COLLECTION_TIMEOUT, "last30days collector", env=env, cwd=root)
        logger.info("last30days collection checked for %s", ticker)
    except Exception as exc:
        # Search/archive availability cannot determine whether an otherwise valid case is issued.
        logger.warning("last30days collection unavailable for %s (%s)", ticker, type(exc).__name__)
