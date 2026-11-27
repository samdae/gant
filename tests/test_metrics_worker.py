import asyncio
import unittest
from unittest.mock import Mock, patch

from tradingagents.api import app as api


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_accounting_and_status_after_failure_skip_success(self):
        queue = asyncio.PriorityQueue()
        graph, scheduler = Mock(), Mock()
        def run_cycle(ticker, job_id):
            if ticker == "BAD":
                raise RuntimeError("test failure")
            if ticker == "SKIP":
                callback = graph.set_status_callback.call_args.args[0]
                callback("system", "skipped", "No updated market data")
                return False
            return True

        scheduler._run_analysis_cycle.side_effect = run_cycle
        for i, ticker in enumerate(["BAD", "SKIP", "GOOD"]):
            await queue.put((0, i, {"ticker": ticker, "schedule_job_id": i}))
        with patch.object(api.ticker_scheduler_module, "analysis_queue", queue), patch.object(
            api, "graph", graph
        ), patch.object(api, "scheduler", scheduler), patch.object(api, "broadcast_status") as notify:
            worker = asyncio.create_task(api._queue_worker())
            try:
                await asyncio.wait_for(queue.join(), 3)
                statuses = [(c.args[0], c.args[2]) for c in notify.call_args_list]
                self.assertIn(("BAD", "error"), statuses)
                self.assertNotIn(("BAD", "completed"), statuses)
                self.assertNotIn(("SKIP", "completed"), statuses)
                notify.assert_any_call("SKIP", "system", "skipped", "No updated market data", schedule_job_id=1)
                self.assertIn(("GOOD", "completed"), statuses)
                self.assertIsNone(api.current_running_ticker)
                graph.set_status_callback.assert_called_with(None)
            finally:
                worker.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await worker
