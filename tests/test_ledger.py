"""Ledger regression tests. PG_TEST_BINDIR enables a new disposable PostgreSQL cluster."""
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tradingagents.scheduler.ticker_scheduler import TickerScheduler
from tradingagents.storage import Database, PositionRepository, ScheduleConfigRepository, ScheduleJobRepository
from tradingagents.virtual_trade.trade_manager import TradeManager


class TradeQuantityTests(unittest.TestCase):
    def test_reject_invalid_sell(self):
        manager = object.__new__(TradeManager)
        manager.load = Mock(return_value={"position": {"id": 1, "shares": 1, "avg_cost": 20}})
        for shares, price in ((-1, 20), (0, 20), (float("nan"), 20), (1, 0), (1, float("inf"))):
            with self.subTest(shares=shares, price=price), self.assertRaises(ValueError):
                manager.close_positions("TEST", shares, price, "2026-01-02")

    def test_microshares_are_preserved(self):
        self.assertEqual(TradeManager._round_shares(0.000123), 0.000123)


@unittest.skipUnless(os.environ.get("PG_TEST_BINDIR"), "Set PG_TEST_BINDIR to run private-cluster integration")
class LedgerDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        root = Path(temp.name)
        pg = Path(os.environ["PG_TEST_BINDIR"])
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        secret = secrets.token_hex(24)
        password = root / "password"
        password.write_text(secret, encoding="ascii")
        data = root / "cluster"
        subprocess.run([pg / "initdb", "-D", data, "-U", "test", "--auth=scram-sha-256",
                        "--pwfile", password, "--locale=C", "--encoding=UTF8"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([pg / "pg_ctl", "-D", data, "-l", root / "pg.log", "-o", f"-p {port} -h 127.0.0.1",
                        "start", "-w"], check=True, stdout=subprocess.DEVNULL)
        cls.addClassCleanup(subprocess.run, [pg / "pg_ctl", "-D", data, "stop", "-m", "fast", "-w"], check=True)
        with patch.dict(os.environ, SUPABASE_DIRECT_URL=""):
            cls.db = Database(f"postgresql://test:{secret}@127.0.0.1:{port}/postgres")
        cls.addClassCleanup(cls.db.close)
        cls.db.init_schema()

    def test_stop_loss_sell_and_failure_rollback(self):
        scheduler = object.__new__(TickerScheduler)
        scheduler.db = self.db
        scheduler.trade_manager = TradeManager(self.db)
        scheduler.graph = Mock()
        scheduler.graph.reflector.reflect_on_position.return_value = None
        scheduler._get_latest_close = Mock(return_value=(50, "2026-01-02"))
        config_repo = ScheduleConfigRepository(self.db)
        config = config_repo.create("TEST", 1)
        job = ScheduleJobRepository(self.db).create(config, 1, "running")
        manager = scheduler.trade_manager
        position = manager.open_position("TEST", 0.123456, 100, "2026-01-01")["position"]
        with patch("tradingagents.storage.TradeRepository.create", side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                scheduler._run_analysis_cycle_impl("TEST", job)
        self.assertEqual(PositionRepository(self.db).get_active("TEST")["shares"], 0.123456)
        conn = self.db.get_connection()
        self.assertEqual(conn.execute("select count(*) as n from reports").fetchone()["n"], 0)
        scheduler._run_analysis_cycle_impl("TEST", job)
        row = conn.execute(
            """select t.action,t.shares,t.price,t.position_id,j.status from trades t join reports r
               on t.report_id=r.id join schedule_jobs j on r.schedule_job_id=j.id where j.id=%s""", (job,)
        ).fetchone()
        self.assertEqual(row, dict(action="SELL", shares=0.123456, price=50, position_id=position["id"], status="done"))
        self.assertIsNone(PositionRepository(self.db).get_active("TEST"))
        self.assertEqual(str(config_repo.get_by_ticker("TEST")["last_data_date"]), "2026-01-02")

    def test_portfolio_failure_is_atomic_and_liquidation_keeps_cash_only(self):
        from datetime import timedelta
        from tradingagents.scheduler.portfolio_pipeline import PortfolioPipeline

        pipeline = PortfolioPipeline(self.db, {}, Mock())
        config = pipeline.config_repo.create(1000, base_currency="USD", fee_enabled=False)
        pipeline._load_today_reports = Mock(return_value=[{"ticker": "TEST"}])
        pipeline._load_today_skipped_tickers = Mock(return_value=[])
        pipeline._fetch_current_prices = Mock(return_value={"TEST": 20.0})
        pipeline.briefing_agent.generate_briefing = Mock(return_value={"items": [{"ticker": "TEST"}]})
        pipeline.exchange_rate_service.get_usd_krw = Mock(return_value=1400.0)
        pipeline.pm_agent.decide_allocation = Mock(return_value={
            "allocation_plan": [{"ticker": "TEST", "action": "BUY", "shares": 2}]
        })
        with patch.object(pipeline.config_repo, "update_fund", side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                pipeline.run_daily(config)
        conn = self.db.get_connection()
        for table in ("portfolio_decisions", "portfolio_trades", "portfolio_holdings"):
            self.assertEqual(conn.execute(f"select count(*) as n from {table}").fetchone()["n"], 0)
        self.assertEqual(pipeline.run_daily(config)["status"], "completed")
        self.assertEqual(pipeline.config_repo.get_by_id(config)["available_cash"], 960.0)
        self.assertEqual(pipeline.run_daily(config)["status"], "skipped")
        tomorrow = pipeline._today_kst() + timedelta(days=1)
        pipeline._today_kst = Mock(return_value=tomorrow)
        pipeline.pm_agent.decide_allocation = Mock(return_value={
            "allocation_plan": [{"ticker": "TEST", "action": "SELL", "shares": 2}]
        })
        self.assertEqual(pipeline.run_daily(config)["status"], "completed")
        self.assertEqual(pipeline.config_repo.get_by_id(config)["available_cash"], 1000.0)
        self.assertEqual(pipeline.holding_repo.list_latest(config), [])

    def test_rag_verdict_is_idempotent_and_preserves_score(self):
        from tradingagents.storage import RAGValidationRepository
        conn = self.db.get_connection()
        pos = PositionRepository(self.db).create("RAG")
        reflection = conn.execute(
            "insert into reflections(position_id,reflection,created_at) values (%s,'test',now()) returning id",
            (pos,),
        ).fetchone()["id"]
        retro = conn.execute(
            "insert into retrospective_analyses(position_id,ticker,position_sequence,position_status) "
            "values (%s,'RAG',1,'open') returning id", (pos,)
        ).fetchone()["id"]
        repo = RAGValidationRepository(self.db)
        self.assertGreater(repo.create(retro, reflection, "reflected", "test"), 0)
        self.assertEqual(repo.create(retro, reflection, "reflected", "test"), 0)
        self.assertEqual(conn.execute(
            "select usefulness_score from reflections where id=%s", (reflection,)
        ).fetchone()["usefulness_score"], 50)

    def test_verified_ticker_memory_requires_evidence_and_complete_fills(self):
        from tradingagents.memory.hybrid_memory import HybridMemory
        from tradingagents.storage import ReflectionRepository, TradeRepository
        conn = self.db.get_connection()
        position_repo = PositionRepository(self.db)
        pos = position_repo.create("RAGSAFE")
        config = ScheduleConfigRepository(self.db).create("RAGSAFE", 1)
        job = ScheduleJobRepository(self.db).create(config, 1, "done")
        report = conn.execute(
            "insert into reports(schedule_job_id,position_id,created_at) values (%s,%s,now()) returning id",
            (job, pos)
        ).fetchone()["id"]
        repo = ReflectionRepository(self.db)
        rid = repo.create(pos, "text", key_lessons="momentum dilution breakdown", outcome="win", return_pct=20)
        conn.execute("update positions set status='closed' where id=%s", (pos,))
        trades = TradeRepository(self.db)
        trades.create(pos, report, "BUY", 1, 100)
        self.assertIsNone(repo.get_verified_memory(rid))
        trades.create(pos, report, "SELL", 1, 120)
        memory = HybridMemory("regression", db=self.db)
        with patch.object(memory, "_lazy_init_vector"):
            query = "RAGSAFE analysis: unusual momentum dilution Decision: careful"
            self.assertEqual(memory.get_memories(query)[0]["metadata"]["reflection_id"], rid)
            self.assertFalse(memory.get_memories("OTHER analysis: unusual momentum dilution"))
            self.assertFalse(memory.get_memories("RAGSAFE analysis: momentum"))
        conn.execute("update reflections set return_pct=-20 where id=%s", (rid,))
        self.assertIsNone(repo.get_verified_memory(rid))

    def test_unfilled_forecast_is_persisted(self):
        from scripts.evaluate_saved_signals import forecast_probability
        from tradingagents.graph.signal_processing import SignalProcessor
        from tradingagents.storage import ReportRepository

        ticker = "NOFILL"
        config_id = ScheduleConfigRepository(self.db).create(ticker, 1)
        job = ScheduleJobRepository(self.db).create(config_id, 1, "running")
        scheduler = object.__new__(TickerScheduler)
        scheduler.db = self.db
        scheduler.config = {"deep_think_llm": "test-judge"}
        scheduler.trade_manager = TradeManager(self.db)
        scheduler._get_latest_close = Mock(return_value=(100, "2026-01-02"))
        scheduler.graph = Mock()
        signal = SignalProcessor(Mock()).process_signal(
            '```strategy_json\n{"action":"HOLD","forecast_5s":{"p_up":0.62}}\n```'
        )
        snapshot = {"version": 1, "ticker": ticker, "as_of": "2026-01-02T21:00:00+00:00",
                    "status": "available", "items": [{"ref": "N1"}, {"ref": "N2"}]}
        scheduler.graph.propagate.return_value = (
            {"news_analyst_cited": ["N1"], "final_trade_decision": "Material guidance [N1]. Unknown [N90]. [N2]"},
            signal,
        )
        scheduler.summary_agent = Mock()
        scheduler.summary_agent.summarize.return_value = {}
        scheduler.portfolio_agent = Mock()
        scheduler.portfolio_agent.decide.return_value = {"action": "HOLD"}
        scheduler._ticker_locks = {ticker: threading.Lock()}
        scheduler._requeued_job_ids = set()
        scheduler._on_all_tickers_complete = Mock()
        scheduler._get_latest_market_date = Mock(return_value=None)

        def before_report(symbol, market):
            self.assertEqual((symbol, market), (ticker, "us"))
            self.assertIsNone(ReportRepository(self.db).get_by_job(job))
            scheduler.graph.propagate.assert_not_called()

        with (
            patch("tradingagents.dataflows.macro_collector.collect_macro_context", return_value="") as macro,
            patch("tradingagents.scheduler.ticker_scheduler.trade_news_for_close", return_value=snapshot) as read_news,
            patch("tradingagents.scheduler.ticker_scheduler.collect_scheduled_issues", side_effect=before_report) as collect,
        ):
            self.assertFalse(scheduler._run_analysis_cycle(ticker))
            scheduler._get_latest_market_date.return_value = "2026-01-02"
            self.assertTrue(scheduler._run_analysis_cycle(ticker, job))
            self.assertFalse(scheduler._run_analysis_cycle(ticker, job))
            self.assertFalse(scheduler._run_analysis_cycle(ticker))
            collect.assert_called_once()
        macro.assert_called_once_with(ticker, "us", "2026-01-02")
        read_news.assert_called_once()
        self.assertEqual(scheduler.graph.propagate.call_args.kwargs["news_evidence"], snapshot)
        report = ReportRepository(self.db).get_by_job(job)
        evidence = self.db.get_connection().execute(
            "SELECT news_evidence FROM reports WHERE id=%s", (report["id"],)
        ).fetchone()["news_evidence"]
        self.assertEqual(evidence, {**snapshot, "analyst_cited": ["N1"], "decision_cited": ["N1"]})
        self.assertIsNone(report["position_id"])
        self.assertEqual(forecast_probability(report["pipeline_strategy"]), 0.62)
        self.assertEqual(json.loads(report["pipeline_strategy"])["forecast_5s"]["market_data_date"], "2026-01-02")
        self.assertEqual(self.db.get_connection().execute(
            "select count(*) as n from trades where report_id=%s", (report["id"],)
        ).fetchone()["n"], 0)

    def test_z_paired_outcome_is_atomic_and_cascades(self):
        from datetime import date
        from psycopg.types.json import Jsonb
        from tradingagents.rag_validator.outcome import evaluate_pending
        from tradingagents.storage import ReflectionRepository
        conn = self.db.get_connection()
        pos = PositionRepository(self.db).create("PAIR")
        config = ScheduleConfigRepository(self.db).create("PAIR", 1)
        job = ScheduleJobRepository(self.db).create(config, 1, "done")
        repo = ReflectionRepository(self.db)
        rid = repo.create(pos, "text", key_lessons="example", outcome="win", return_pct=5)
        pair = {"reflection_id":rid, "before":{"action":"HOLD","shares":0},
                "after":{"action":"BUY","shares":2}, "cash":1000, "holdings":0}
        payload = {"memories":[{"reflection_id":rid,"matched_situation":"lesson"}],"decision_pair_v1":pair,
                   "applied_reflection_ids":[rid]}
        report = conn.execute(
            "INSERT INTO reports(schedule_job_id,rag_used,rag_docs,created_at) "
            "VALUES(%s,true,%s,'2024-11-26T15:00:00Z') RETURNING id", (job, Jsonb(payload))
        ).fetchone()["id"]
        conn.commit()
        def bars(ticker, sessions, tz):
            return {day:(10, 9, 0) for day in sessions}, {}
        with patch("tradingagents.rag_validator.outcome._load_bars", side_effect=bars):
            self.assertEqual(evaluate_pending(self.db, date(2024, 12, 4)), 0)
            self.assertEqual(evaluate_pending(self.db, date(2024, 12, 5)), 1)
            self.assertEqual(evaluate_pending(self.db, date(2024, 12, 5)), 0)
        self.assertEqual(repo.outcome_scores([rid]), {rid:49})
        self.assertEqual(repo.get_by_id(rid)["usefulness_score"], 49)
        self.assertEqual(repo.get_by_position(pos)["usefulness_score"], 49)
        self.assertEqual(repo.get_usefulness_scores([rid]), {rid:49})
        self.assertEqual(repo.search_keyword("example")[0]["usefulness_score"], 49)
        self.assertEqual(repo.search_fts("example")[0]["usefulness_score"], 49)
        evidence = conn.execute("SELECT evidence FROM rag_outcome_evaluations WHERE report_id=%s",
                                (report,)).fetchone()["evidence"]
        self.assertEqual(evidence["gross_difference"], -2)
        conn.execute("DELETE FROM reports WHERE id=%s", (report,))
        self.assertEqual(repo.outcome_scores([rid]), {})
