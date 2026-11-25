import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.forecast_lab.scheduled_sources import (
    COLLECTION_TIMEOUT, COLLECTOR_ROOT, collect_scheduled_issues,
)


class ScheduledSourcesTest(unittest.TestCase):
    def test_only_fixed_v3_command_and_clean_environment_reach_child(self):
        checkout = Path.cwd().resolve()
        parent = {COLLECTOR_ROOT: str(checkout), "SystemRoot": str(checkout),
                  "LOCALAPPDATA": str(checkout.parent), "TRADINGAGENTS_ADMIN_TOKEN": "private",
                  "FORECAST_LAB_DSN": "private", "PYTHONPATH": "old-checkout", "OPENAI_API_KEY": "private"}
        with patch.dict(os.environ, parent, clear=True), patch(
            "tradingagents.forecast_lab.scheduled_sources.bounded_run"
        ) as run:
            collect_scheduled_issues("000660.KS", "kr")
            cmd, payload, timeout, _label = run.call_args.args
            self.assertEqual(cmd, [str(checkout / ".venv/Scripts/python.exe"), "-I", "-X", "utf8", "-m",
                "tradingagents.forecast_lab.scheduled_issues", "--ticker", "000660.KS", "--market", "kr"])
            self.assertEqual((payload, timeout), ("start\n", COLLECTION_TIMEOUT))
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["cwd"], checkout)
            self.assertEqual(set(kwargs["env"]), {"SystemRoot", "LOCALAPPDATA", "PATH", "GANT_LAST30DAYS_SCHEDULED_HANDSHAKE"})
            self.assertEqual(kwargs["env"]["GANT_LAST30DAYS_SCHEDULED_HANDSHAKE"], "1")
            collect_scheduled_issues("BTC-USD", "us")
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.args[0][-4:], ["--ticker", "BTC-USD", "--market", "us"])

    def test_skip_disabled_unlisted_or_near_deadline_and_fail_open(self):
        with patch.dict(os.environ, {"SystemRoot": str(Path.cwd())}, clear=True), patch(
            "tradingagents.forecast_lab.scheduled_sources.bounded_run", side_effect=TimeoutError
        ) as run:
            collect_scheduled_issues("NVDA", "us")
            os.environ[COLLECTOR_ROOT] = str(Path.cwd())
            collect_scheduled_issues("NVDA", "us", seconds_to_entry=20)
            for symbol, market in [("--flag", "us"), ("NVDA", "kr"), ("005930.KS", "us")]:
                collect_scheduled_issues(symbol, market)
            run.assert_not_called()
            with self.assertLogs("tradingagents.forecast_lab.scheduled_sources", level="WARNING") as logs:
                collect_scheduled_issues("NVDA", "us")
            run.assert_called_once()
            self.assertIn("TimeoutError", logs.output[0])
