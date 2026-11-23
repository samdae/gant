"""Offline regressions for credential handling and historical market-data requests."""
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import pandas as pd
import requests

from tradingagents.default_config import get_database_url
from tradingagents.dataflows.alpha_vantage_common import _make_api_request
from tradingagents.dataflows.stockstats_utils import load_price_window


class RuntimeTests(unittest.TestCase):
    def test_google_refresh_uses_only_the_selected_providers_credentials(self):
        from tradingagents.llm_clients.antigravity_client import AntigravityAuth, GeminiCLIAuth

        for auth_type, provider in ((AntigravityAuth, "ANTIGRAVITY"), (GeminiCLIAuth, "GEMINI_CLI")):
            with self.subTest(provider=provider), patch.dict(os.environ, {}, clear=True):
                auth = object.__new__(auth_type)
                auth.access_token, auth.expires_at = None, 0
                auth.refresh_token, auth.project_id = "refresh", "project"
                with patch.object(auth, "_refresh_access_token", return_value=True) as refresh:
                    with self.assertRaisesRegex(RuntimeError, provider + "_CLIENT_ID"):
                        auth.ensure_token()
                    refresh.assert_not_called()
                    os.environ.update({provider + "_CLIENT_ID": "local-id", provider + "_CLIENT_SECRET": "local-secret"})
                    auth.ensure_token()
                    refresh.assert_called_once()
                    self.assertEqual((auth.client_id, auth.client_secret), ("local-id", "local-secret"))

    def test_db_url_escapes_credentials_and_ipv6(self):
        with patch.dict(os.environ, {"POSTGRES_USER": "a:b", "POSTGRES_PASSWORD": "a@/#%",
                                    "POSTGRES_DB": "test db", "POSTGRES_HOST": "::1"}, clear=True):
            url = urlsplit(get_database_url())
        self.assertEqual((unquote(url.username), unquote(url.password), url.hostname,
                          unquote(url.path)), ("a:b", "a@/#%", "::1", "/test db"))

    def test_network_error_omits_api_key(self):
        with patch.dict(os.environ, {"ALPHA_VANTAGE_API_KEY": "fixture-secret"}), patch(
            "requests.get", side_effect=requests.Timeout("failed?apikey=fixture-secret")
        ) as request:
            with self.assertRaises(RuntimeError) as error:
                _make_api_request("OVERVIEW", {"symbol": "TEST"})
        self.assertNotIn("fixture-secret", str(error.exception))
        self.assertTrue(request.call_args.kwargs["timeout"])

    def test_history_window_includes_requested_date_and_reuses_cache(self):
        date = pd.Timestamp("2020-01-03")
        history = pd.DataFrame({key: [1] for key in ("Open", "High", "Low", "Close", "Volume")},
                               index=pd.DatetimeIndex([date], name="Date"))
        with TemporaryDirectory() as folder, patch("yfinance.download", return_value=history) as download:
            config = {"data_cache_dir": folder}
            for _ in range(2):
                df = load_price_window("ABC", date, 330, config)
                self.assertEqual(df["Date"].iloc[0], date)
            self.assertEqual(download.call_count, 1)
            self.assertEqual(download.call_args.kwargs["end"], "2020-01-04")
