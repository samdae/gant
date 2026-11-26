import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.forecast_lab.scheduled_sources import (
    COLLECTION_TIMEOUT, COLLECTOR_ROOT, READ_TIMEOUT, collect_scheduled_issues, read_trade_news,
)


class ScheduledSourcesTest(unittest.TestCase):
    def test_read_validated_trade_news_or_fall_back_without_model_secrets(self):
        cutoff = "2025-03-01T12:00:00+00:00"
        item = {"ref": "N1", "source": "last30days agent export", "publisher": "hackernews",
                "url": "https://news.ycombinator.com/item?id=1", "title": "테스트 자료",
                "published_at": "2025-02-26T12:00:00+00:00", "first_seen_at": "2025-02-27T15:00:00+00:00",
                "published_day": "2025-02-25"}
        packet = {"version": 1, "status": "partial", "ticker": "WMT", "as_of": cutoff, "items": [item]}
        fallback = {**packet, "status": "unavailable", "items": []}
        root = str(Path.cwd())
        with patch.dict(os.environ, {"SystemRoot": root, "FORECAST_LAB_DSN": "private"}, clear=True), patch(
            "tradingagents.forecast_lab.scheduled_sources.bounded_run"
        ) as run:
            self.assertEqual(read_trade_news("WMT", "us", cutoff), fallback)
            run.assert_not_called()
            os.environ[COLLECTOR_ROOT] = root
            run.return_value = json.dumps(packet)
            self.assertEqual(read_trade_news("WMT", "us", cutoff), packet)
            command, payload, timeout, _label = run.call_args.args
            self.assertEqual(command[-5:], ["tradingagents.forecast_lab.trade_news", "--ticker", "WMT", "--as-of", cutoff])
            self.assertEqual((payload, timeout), ("start\n", READ_TIMEOUT))
            self.assertNotIn("FORECAST_LAB_DSN", run.call_args.kwargs["env"])
            # A full horizon can exceed the old message size even with valid article fields.
            rows = []
            for source in ("last30days agent export", "Google News RSS"):
                for _ in range(40):
                    n = len(rows) + 1
                    rows.append({"ref": f"N{n}", "source": source, "title": "가" * 490, "publisher": "매체",
                                 "url": "https://example.org/" + "a" * 1000 + str(n),
                                 "published_at": item["published_at"], "first_seen_at": item["first_seen_at"]})
            full = {**packet, "status": "available", "items": rows}
            run.return_value = json.dumps(full, ensure_ascii=False)
            self.assertGreater(len(run.return_value.encode("utf8")), 128 * 1024)
            self.assertEqual(read_trade_news("WMT", "us", cutoff), full)
            invalid_items = [
                [{**item, "first_seen_at": cutoff}], [{**item, "published_at": "2025-01-01T00:00:00Z"}],
                [{**item, "published_day": "2025-02-24"}], [{**item, "ref": "N77"}],
                [item, {**item, "ref": "N2"}],
                [*rows, {**rows[-1], "ref": "N81", "url": "https://example.org/81"}],
                [{**rows[0], "source": "Google News RSS"}, *rows[1:]],
            ]
            for wrong in ([{**packet, "items": rows} for rows in invalid_items]
                          + [{**packet, "ticker": "KO"}, {**packet, "as_of": "2025-03-02T12:00:00Z"}]):
                with self.subTest(wrong=wrong):
                    run.return_value = json.dumps(wrong)
                    self.assertEqual(read_trade_news("WMT", "us", cutoff), fallback)
            run.side_effect = TimeoutError
            self.assertEqual(read_trade_news("WMT", "us", cutoff), fallback)

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
