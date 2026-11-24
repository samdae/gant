"""Sequential forecast issuance and maturity checks, independent of the trading worker."""

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from .classification import POLICY

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
METHODS = ("baseline", "single", "debate", "memory")


def now():
    return datetime.now(UTC).isoformat()


def reason(exc):
    # Only engine-authored constant messages may leave the worker; transport errors can contain URLs.
    from .engine import ForecastUnavailable

    if isinstance(exc, ForecastUnavailable):
        text = str(exc)
        if text in {
            "Entry session has already opened",
            "Latest 21-session prices incomplete or crossed an uncertain corporate action",
            "Fewer than 20 complete historical five-session windows",
            "Snapshot has not been observed yet",
            "NAVER chart identity mismatch",
            "Instrument classification or listing exchange changed",
            "Outcome price source differs from frozen issuance source",
            "Exchange calendar revised the frozen five-session horizon",
            "No eligible matured memory",
            "Memory was not already available at snapshot observation",
            "Memory market or experiment version mismatch",
        }:
            return text
    return type(exc).__name__


class Progress:
    """Atomic checkpoint shared by the scheduler, CLI worker and read-only API."""

    def __init__(self, folder):
        self.path = Path(folder) / "scan-progress.json"

    def read(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def save(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.path.parent, delete=False, encoding="utf-8"
        ) as out:
            json.dump(value, out, ensure_ascii=False)
            tmp = out.name
        try:
            os.replace(tmp, self.path)
        finally:
            Path(tmp).unlink(missing_ok=True)


class Worker:
    def __init__(
        self,
        store,
        engine,
        progress,
        clock=None,
        reference=None,
        experiment_version=None,
    ):
        self.experiment_version = experiment_version
        self.reference = reference
        self.store = store
        self.engine = engine
        self.progress = progress
        self.clock = clock or (lambda: datetime.now(UTC))

    def current_version(self, case):
        return (
            self.experiment_version is None
            or self.experiment_version == case["experiment_version"]
        )

    def mature(self, pending):
        count = 0
        for case in pending:
            try:
                result = self.engine.outcome(case["snapshot"])
                if not result:
                    continue
                if result["status"] == "excluded":
                    saved = self.store.exclude_case(
                        case["id"], result["reason"], evidence=result
                    )
                else:
                    saved = self.store.record_outcome(
                        case["id"],
                        entry_open=result["entry_open"],
                        exit_close=result["exit_close"],
                        evidence=result,
                    )
                count += int(bool(saved))
            except Exception:
                logger.exception("Outcome deferred for case %s", case["id"])
        return count

    def capture(self, cases=None):
        if not self.reference:
            return 0
        try:
            return self.reference.capture(
                self.store.open_reference_cases() if cases is None else cases
            )
        except Exception as exc:  # noqa: BLE001 - optional read source must never interrupt issuance
            logger.warning("Reference capture deferred: %s", type(exc).__name__)
            return 0

    def issue(self, row, state):
        snapshot = self.engine.snapshot(row["ticker"], row["market"])
        case_id = self.store.create_case(snapshot)
        case = self.store.detail(case_id)
        # A restart must reuse the original evidence even if the vendor revised its latest bars.
        if self.reference and not case.get("reference"):
            self.capture([case])
        self.issue_frozen(case, state)
        return case_id

    def issue_frozen(self, case, state):
        case_id = case["id"]
        snapshot = case["snapshot"]
        recorded = {arm["method"]: arm for arm in case["arms"]}
        methods = METHODS
        if snapshot.get("retrieval_policy") == POLICY:
            methods += ("memory_sector",)
        control = recorded.get("memory") or {}
        control_id = (
            control.get("memory_id") if control.get("status") == "published" else None
        )
        for method in methods:
            arm = recorded.get(method)
            attempts = (arm.get("audit") or {}).get("attempts", 1) if arm else 0
            if arm and (arm["status"] != "failed" or attempts >= MAX_ATTEMPTS):
                continue
            state.update(case_id=case_id, method=method)
            self.progress.save(state)
            deadline = datetime.fromisoformat(str(snapshot["entry_open_at"]))
            if self.clock() >= deadline:
                break
            try:
                memory = None
                if method in {"memory", "memory_sector"}:
                    memory = (
                        self.store.select_memory(case_id) if method == "memory"
                        else self.store.select_memory(case_id, method)
                    )
                    if not memory:
                        error = (
                            "no eligible matured memory" if method == "memory"
                            else "no_eligible_sector_memory"
                        )
                        self.store.record_arm(case_id, method, status="skipped", error=error)
                        continue
                    if method == "memory_sector":
                        # On restart or a failed control attempt, compare against a durable
                        # published control. A missing forecast is never evidence of a pair.
                        if control_id is None:
                            continue
                        if memory["id"] == control_id:
                            self.store.record_arm(
                                case_id, method, status="skipped", error="same_memory"
                            )
                            continue
                arm = self.engine.forecast(snapshot, method, memory=memory)
            except Exception as exc:  # noqa: BLE001 - isolate provider/model failures per arm
                logger.warning(
                    "Forecast failed for case %s method %s: %s",
                    case_id,
                    method,
                    reason(exc),
                )
                self.store.record_arm(
                    case_id,
                    method,
                    status="failed",
                    error=reason(exc),
                    audit={"attempts": attempts + 1},
                )
                continue
            if self.store.record_arm(case_id, **arm) and method == "memory":
                control_id = arm["memory_id"]

    def scan(self, limit=None, stopping=lambda: False):
        with self.store.worker_lock() as acquired:
            if not acquired:
                return {"phase": "busy"}
            previous = self.progress.read()
            rows = sorted(self.store.list_tickers(), key=lambda r: r["ticker"])
            cursor = previous.get("cursor", "")
            rows = [r for r in rows if r["ticker"] > cursor] + [
                r for r in rows if r["ticker"] <= cursor
            ]
            state = {
                "phase": "maturing",
                "started_at": now(),
                "cursor": cursor,
                "attempted": 0,
                "total": len(rows),
                "failures": {},
                "matured": 0,
                "ticker": None,
                "case_id": None,
                "method": None,
                "latest": previous.get("latest", {}),
            }
            self.progress.save(state)
            try:
                self.capture()
                pending = self.store.pending_cases()
                state["matured"] = self.mature(pending)
                open_cases = {}
                for case in pending:
                    deadline = datetime.fromisoformat(
                        str(case["snapshot"]["entry_open_at"])
                    )
                    if self.clock() < deadline and self.current_version(case):
                        open_cases[case["ticker"]] = case
                for row in rows[:limit]:
                    if stopping():
                        break
                    # Commit cursor before inference so a killed noisy ticker cannot monopolize restart.
                    state.update(
                        phase="issuing",
                        cursor=row["ticker"],
                        ticker=row["ticker"],
                        case_id=None,
                        method=None,
                    )
                    self.progress.save(state)
                    try:
                        if row["ticker"] in open_cases:
                            self.issue_frozen(open_cases[row["ticker"]], state)
                        else:
                            latest_id = state["latest"].get(row["ticker"])
                            last = self.store.detail(latest_id) if latest_id else None
                            if (
                                last
                                and self.current_version(last)
                                and last["ticker"] == row["ticker"]
                                and self.clock()
                                < datetime.fromisoformat(
                                    last["snapshot"]["entry_open_at"]
                                )
                            ):
                                continue
                            state["latest"][row["ticker"]] = self.issue(row, state)
                    except Exception as exc:  # noqa: BLE001 - allow other tickers to issue
                        state["failures"][row["ticker"]] = reason(exc)
                        logger.warning("Skipped %s: %s", row["ticker"], reason(exc))
                    finally:
                        state["attempted"] += 1
                state.update(phase="idle", finished_at=now())
            except Exception:
                state.update(phase="failed", finished_at=now())
                raise
            finally:
                state.update(ticker=None, case_id=None, method=None)
                self.progress.save(state)
            return state
