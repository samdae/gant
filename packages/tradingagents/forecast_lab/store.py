"""PostgreSQL persistence for the independent prospective forecast laboratory."""

import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import exchange_calendars
import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .engine import DELAY, _valid_bar

METHODS = ("baseline", "single", "debate", "memory")
STATUSES = ("pending", "awaiting", "matured", "excluded", "unpublished")
ZONES = {"us": "America/New_York", "kr": "Asia/Seoul"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS lab_watchlist(
 ticker text PRIMARY KEY, market text NOT NULL CHECK(market IN ('us','kr')));
CREATE TABLE IF NOT EXISTS lab_cases(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, ticker text NOT NULL, market text NOT NULL,
 data_session date NOT NULL, experiment_version text NOT NULL, snapshot jsonb NOT NULL,
 observed_at timestamptz NOT NULL, entry_at timestamptz NOT NULL, exit_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(ticker, data_session, experiment_version),
 CHECK(observed_at <= created_at AND created_at < entry_at AND entry_at < exit_at));
CREATE TABLE IF NOT EXISTS lab_references(
 case_id bigint PRIMARY KEY REFERENCES lab_cases,
 experiment_version text NOT NULL, source text NOT NULL, source_report_id bigint NOT NULL,
 ticker text NOT NULL, data_session date NOT NULL, probability double precision NOT NULL CHECK(probability BETWEEN 0 AND 1),
 model text NOT NULL, source_published_at timestamptz NOT NULL, captured_at timestamptz NOT NULL,
 UNIQUE(experiment_version,source,source_report_id), CHECK(source_published_at<=captured_at));
CREATE TABLE IF NOT EXISTS lab_outcomes(
 case_id bigint PRIMARY KEY REFERENCES lab_cases, status text NOT NULL CHECK(status IN ('scored','excluded')),
 entry_open double precision, exit_close double precision, actual integer CHECK(actual IN (0,1)),
 evidence jsonb NOT NULL, reason text, observed_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE IF NOT EXISTS lab_memories(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, case_id bigint UNIQUE NOT NULL REFERENCES lab_outcomes,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp());
CREATE TABLE IF NOT EXISTS lab_arms(
 case_id bigint NOT NULL REFERENCES lab_cases, method text NOT NULL CHECK(method IN ('baseline','single','debate','memory')),
 status text NOT NULL CHECK(status IN ('published','failed','skipped')), probability double precision,
 rationale text NOT NULL, model text NOT NULL, version text NOT NULL, memory_id bigint REFERENCES lab_memories,
 error text, audit jsonb NOT NULL, published_at timestamptz, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(case_id,method), CHECK ((status='published')=(published_at IS NOT NULL)),
 CHECK((status='published' AND probability BETWEEN 0 AND 1) OR (status<>'published' AND probability IS NULL)),
 CHECK(memory_id IS NULL OR method='memory'));
CREATE INDEX IF NOT EXISTS lab_memory_uses ON lab_arms(memory_id,case_id)
 WHERE method='memory' AND status='published';
CREATE INDEX IF NOT EXISTS lab_cases_recent ON lab_cases(created_at DESC,id DESC);
CREATE INDEX IF NOT EXISTS lab_cases_market_version ON lab_cases(market,experiment_version);
"""

STATE = """CASE WHEN o.status='scored' THEN 'matured' WHEN o.status='excluded' THEN 'excluded'
WHEN c.entry_at > statement_timestamp() AND
 (SELECT count(*) FROM lab_arms a WHERE a.case_id=c.id AND a.status<>'failed') < 4 THEN 'pending'
WHEN EXISTS(SELECT FROM lab_arms a WHERE a.case_id=c.id AND a.status='published') THEN 'awaiting'
ELSE 'unpublished' END"""
SUMMARY = f"""SELECT c.id,c.ticker,c.market,c.data_session,c.experiment_version,c.created_at,
 c.entry_at AS entry_open_at,c.exit_at AS exit_close_at,{STATE} AS status
 FROM lab_cases c LEFT JOIN lab_outcomes o ON o.case_id=c.id"""
MEMORY = """SELECT m.id,m.case_id,m.created_at,c.ticker,c.market,c.data_session,c.experiment_version,
 c.snapshot->'features' AS features,a.probability,a.rationale,a.model,a.version,o.actual,o.entry_open,o.exit_close,
 o.observed_at, power(a.probability-o.actual,2) AS brier
 FROM lab_memories m JOIN lab_cases c ON c.id=m.case_id JOIN lab_outcomes o ON o.case_id=m.case_id
 JOIN lab_arms a ON a.case_id=m.case_id AND a.method='single' AND a.status='published'"""


def stamp(value):
    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return parsed


def number(value):
    return type(value) in (float, int) and abs(value) <= 1.7976931348623157e308


def ticker_key(ticker, market):
    ticker, market = ticker.strip().upper(), market.strip().lower()
    if market not in ZONES or not re.fullmatch(r"[A-Z0-9][A-Z0-9.^=-]{0,23}", ticker):
        raise ValueError("invalid ticker or market")
    return ticker, market


def cohort_filters(market, from_date, to_date):
    lower = date.fromisoformat(str(from_date)) if from_date is not None else None
    upper = date.fromisoformat(str(to_date)) if to_date is not None else None
    if market is not None and market not in ZONES:
        raise ValueError("unknown market")
    if lower and upper and lower > upper:
        raise ValueError("from_date exceeds to_date")
    predicates = []
    params = []
    for condition, value in (
        ("c.market = %s", market),
        ("c.data_session >= %s", lower),
        ("c.data_session <= %s", upper),
    ):
        if value is not None:
            predicates.append(condition)
            params.append(value)
    return predicates, params


class Store:
    def __init__(self, dsn):
        params = conninfo_to_dict(dsn or "")
        if (
            not re.fullmatch(r"forecast_lab[a-z0-9_]*", params.get("dbname", ""))
            or params.get("host") not in ("localhost", "127.0.0.1", "::1")
            or not params.get("user")
            or not params.get("port")
            or any(k in params for k in ("service", "hostaddr", "options"))
        ):
            raise ValueError(
                "explicit dedicated local forecast_lab PostgreSQL DSN required"
            )
        self._dsn = dsn

    def _connect(self):
        return psycopg.connect(
            self._dsn,
            row_factory=dict_row,
            connect_timeout=5,
            options="-c timezone=UTC",
        )

    def init(self):
        with self._connect() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(892417601)")
            conn.execute(SCHEMA)

    @contextmanager
    def worker_lock(self):
        with self._connect() as conn:
            conn.autocommit = True
            acquired = conn.execute(
                "SELECT pg_try_advisory_lock(892417602) AS ok"
            ).fetchone()["ok"]
            yield acquired

    def set_ticker(self, ticker, market):
        ticker, market = ticker_key(ticker, market)
        with self._connect() as conn:
            return conn.execute(
                """INSERT INTO lab_watchlist VALUES(%s,%s)
                ON CONFLICT(ticker) DO UPDATE SET market=excluded.market RETURNING ticker,market""",
                (ticker, market),
            ).fetchone()

    def list_tickers(self):
        with self._connect() as conn:
            return conn.execute(
                "SELECT ticker,market FROM lab_watchlist ORDER BY ticker"
            ).fetchall()

    def create_case(self, snapshot, experiment_version=None):
        ticker, market = ticker_key(snapshot["ticker"], snapshot["market"])
        version = experiment_version or snapshot["experiment_version"]
        day = date.fromisoformat(
            str(snapshot.get("data_session") or snapshot["session_date"])
        )
        seen = stamp(snapshot["observed_at"])
        entry = stamp(snapshot.get("entry_open_at") or snapshot["entry_at"])
        end = stamp(snapshot.get("exit_close_at") or snapshot["exit_at"])
        zone = ZoneInfo(ZONES[market])
        if (
            not version
            or not day <= seen.astimezone(zone).date()
            or not day < entry.astimezone(zone).date()
            or not seen < entry < end
        ):
            raise ValueError("invalid snapshot horizon")
        cal = exchange_calendars.get_calendar("XNYS" if market == "us" else "XKRX")
        sessions = cal.sessions_in_range(
            day + timedelta(days=1), day + timedelta(days=30)
        )[:5]
        expected = [s.date().isoformat() for s in sessions]
        if (
            len(sessions) != 5
            or not cal.is_session(day)
            or cal.session_close(day) + DELAY > seen
            or snapshot.get("sessions") != expected
            or cal.session_open(sessions[0]) != entry
            or cal.session_close(sessions[-1]) != end
        ):
            raise ValueError("snapshot conflicts with exchange calendar")
        bars = snapshot.get("bars") or []
        bench = (snapshot.get("benchmark") or {}).get("bars") or []
        if (
            not bars
            or bars[-1].get("date") != day.isoformat()
            or not snapshot.get("source")
        ):
            raise ValueError("latest observation and price provenance required")
        if any(
            not _valid_bar(bar) or date.fromisoformat(str(bar["date"])) > day
            for bar in [*bars, *bench]
        ):
            raise ValueError("snapshot contains invalid or future bars")
        key = (ticker, day, version)
        with self._connect() as conn:
            prior = conn.execute(
                "SELECT id FROM lab_cases WHERE (ticker,data_session,experiment_version)=(%s,%s,%s)",
                key,
            ).fetchone()
            if prior:
                return prior["id"]
            row = conn.execute(
                """INSERT INTO lab_cases
                (ticker,market,data_session,experiment_version,snapshot,observed_at,entry_at,exit_at,created_at)
                SELECT %s,%s,%s,%s,%s,%s,%s,%s,t FROM (SELECT clock_timestamp() t) tm
                WHERE %s <= t AND t < %s ON CONFLICT DO NOTHING RETURNING id""",
                (
                    ticker,
                    market,
                    day,
                    version,
                    Jsonb(snapshot),
                    seen,
                    entry,
                    end,
                    seen,
                    entry,
                ),
            ).fetchone()
            if row:
                return row["id"]
            prior = conn.execute(
                "SELECT id FROM lab_cases WHERE (ticker,data_session,experiment_version)=(%s,%s,%s)",
                key,
            ).fetchone()
            if prior:
                return prior["id"]
            raise ValueError(
                "case publication window closed or snapshot not yet observable"
            )

    def record_arm(
        self,
        case_id,
        method,
        *,
        probability=None,
        rationale="",
        model="",
        version="",
        prompt_version=None,
        memory_id=None,
        status="published",
        error=None,
        audit=None,
        published_at=None,
    ):
        version = version or prompt_version or ""
        if method not in METHODS or status not in ("published", "skipped", "failed"):
            raise ValueError("unknown arm or status")
        if status == "published" and (
            not number(probability)
            or not 0 <= probability <= 1
            or not rationale
            or not model
            or not version
        ):
            raise ValueError(
                "published arm requires valid probability, rationale, model and version"
            )
        if status == "published" and ((method == "memory") != (memory_id is not None)):
            raise ValueError("memory arm must cite exactly one eligible memory")
        if status != "published" and (
            probability is not None or not (error or rationale)
        ):
            raise ValueError("unpublished arm requires a reason and no probability")
        with self._connect() as conn:
            c = conn.execute(
                "SELECT * FROM lab_cases WHERE id=%s FOR UPDATE", (case_id,)
            ).fetchone()
            if not c:
                raise KeyError(case_id)
            if memory_id is not None:
                selected = self._select_memory(conn, c)
                if not selected or selected["id"] != memory_id:
                    raise ValueError("ineligible memory")
                audit = {
                    **(audit or {}),
                    "memory_selection_v1": {
                        key: selected[key]
                        for key in (
                            "feature_distance",
                            "uplift_support",
                            "shrunk_uplift",
                        )
                    },
                }
            row = conn.execute(
                """INSERT INTO lab_arms(case_id,method,status,probability,rationale,model,version,
                    memory_id,error,audit,published_at)
                SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s='published' THEN t END
                FROM (SELECT clock_timestamp() t) tm WHERE t < %s
                ON CONFLICT(case_id,method) DO UPDATE SET (status,probability,rationale,model,version,memory_id,
                    error,audit,published_at,recorded_at)=(excluded.status,excluded.probability,excluded.rationale,
                    excluded.model,excluded.version,excluded.memory_id,excluded.error,excluded.audit,
                    excluded.published_at,excluded.recorded_at) WHERE lab_arms.status='failed'
                RETURNING case_id""",
                (
                    case_id,
                    method,
                    status,
                    probability,
                    rationale,
                    model,
                    version,
                    memory_id,
                    error,
                    Jsonb(audit or {}),
                    status,
                    c["entry_at"],
                ),
            ).fetchone()
            return bool(row)

    def select_memory(self, case_id):
        with self._connect() as conn:
            c = conn.execute(
                "SELECT * FROM lab_cases WHERE id=%s", (case_id,)
            ).fetchone()
            if not c:
                raise KeyError(case_id)
            return self._select_memory(conn, c)

    @staticmethod
    def _select_memory(conn, c):
        rows = conn.execute(
            MEMORY
            + """ WHERE c.market=%s AND c.experiment_version=%s AND c.id<>%s
            AND m.created_at < %s AND o.observed_at < %s""",
            (
                c["market"],
                c["experiment_version"],
                c["id"],
                c["observed_at"],
                c["observed_at"],
            ),
        ).fetchall()
        if not rows:
            return None
        features = c["snapshot"].get("features") or {}
        for row in rows:
            historical = row["features"] or {}
            comparable = [
                k
                for k, v in features.items()
                if number(v) and number(historical.get(k))
            ]
            row["feature_distance"] = (
                sum(
                    abs(features[k] - historical[k])
                    / (1 + abs(features[k]) + abs(historical[k]))
                    for k in comparable
                )
                / len(comparable)
                if comparable
                else 1.0
            )
        same_ticker = [row for row in rows if row["ticker"] == c["ticker"]]
        pool = same_ticker or rows
        nearest = min(row["feature_distance"] for row in pool)
        pool = [row for row in pool if row["feature_distance"] <= nearest + 0.05]
        by_id = {row["id"]: row for row in pool}
        for row in pool:
            row.update(uplift_support=0, shrunk_uplift=0.0)
        # Restrict evidence to the same independent single-model protocol as this target.
        # An unavailable current control keeps the retrieval prior neutral.
        pairs = conn.execute(
            """
            SELECT m.memory_id,p.ticker,p.entry_at,p.exit_at,
              power(b.probability-o.actual,2)-power(m.probability-o.actual,2) AS uplift
            FROM lab_arms active
            JOIN lab_arms b ON b.method='single' AND b.status='published'
                 AND b.model=active.model AND b.version=active.version
            JOIN lab_arms m ON m.case_id=b.case_id AND m.method='memory' AND m.status='published'
                 AND m.version=b.version AND m.model=b.model
            JOIN lab_cases p ON p.id=m.case_id
            JOIN lab_cases current_case ON current_case.id=active.case_id
            JOIN lab_outcomes o ON o.case_id=p.id AND o.status='scored'
            WHERE active.case_id=%s AND active.method='single' AND active.status='published'
              AND m.memory_id=ANY(%s) AND p.experiment_version=current_case.experiment_version
              AND p.created_at<current_case.observed_at AND p.exit_at<current_case.observed_at
              AND b.published_at<current_case.observed_at AND m.published_at<current_case.observed_at
              AND o.observed_at<current_case.observed_at
            ORDER BY m.memory_id,p.ticker,p.exit_at,p.id
            """,
            (c["id"], list(by_id)),
        ).fetchall()
        last_exit = {}
        totals = {}
        for pair in pairs:
            mid = pair["memory_id"]
            group = (mid, pair["ticker"])
            if group in last_exit and pair["entry_at"] <= last_exit[group]:
                continue
            last_exit[group] = pair["exit_at"]
            totals[mid] = totals.get(mid, 0.0) + pair["uplift"]
            by_id[mid]["uplift_support"] += 1
        for mid, total in totals.items():
            row = by_id[mid]
            row["shrunk_uplift"] = max(
                -1.0, min(1.0, total / (5 + row["uplift_support"]))
            )
        return min(
            pool,
            key=lambda row: (
                -row["shrunk_uplift"],
                row["feature_distance"],
                -row["id"],
            ),
        )

    def record_outcome(self, case_id, *, entry_open, exit_close, evidence):
        if (
            not number(entry_open)
            or not number(exit_close)
            or min(entry_open, exit_close) <= 0
            or not evidence
        ):
            raise ValueError("positive observed prices and provenance required")
        return self._finish(
            case_id,
            "scored",
            entry_open,
            exit_close,
            int(exit_close > entry_open),
            None,
            evidence,
        )

    def exclude_case(self, case_id, reason, evidence=None):
        if not reason:
            raise ValueError("exclusion reason required")
        return self._finish(
            case_id, "excluded", None, None, None, reason, evidence or {}
        )

    def _finish(self, case_id, status, entry, close, actual, reason, evidence):
        with self._connect() as conn:
            c = conn.execute(
                "SELECT * FROM lab_cases WHERE id=%s FOR UPDATE", (case_id,)
            ).fetchone()
            if not c:
                raise KeyError(case_id)
            if conn.execute(
                "SELECT clock_timestamp() < %s AS early", (c["exit_at"],)
            ).fetchone()["early"]:
                return False
            evaluated_at = (
                stamp(evidence["observed_at"]) if "observed_at" in evidence else None
            )
            if evaluated_at is not None and evaluated_at < c["exit_at"] + DELAY:
                raise ValueError("outcome evidence predates the horizon")
            if status == "scored":
                window = evidence.get("evidence") or {}
                bars = window.get("bars") or []
                days = c["snapshot"]["sessions"]
                if (
                    evaluated_at is None
                    or evidence.get("source") != c["snapshot"].get("source")
                    or window.get("sessions") != days
                    or [b.get("date") for b in bars] != days
                    or any(
                        not _valid_bar(b)
                        or b.get("split") != 0
                        or b.get("adjustment_uncertain")
                        for b in bars
                    )
                    or bars[0].get("open") != entry
                    or bars[-1].get("close") != close
                ):
                    raise ValueError(
                        "outcome provenance inconsistent with frozen sessions or prices"
                    )
            row = conn.execute(
                """INSERT INTO lab_outcomes(case_id,status,entry_open,exit_close,actual,
                reason,evidence,observed_at) SELECT %s,%s,%s,%s,%s,%s,%s,t FROM (SELECT clock_timestamp() t) tm
                WHERE %s <= t AND COALESCE(%s::timestamptz,t) <= t AND EXISTS(SELECT FROM lab_arms WHERE case_id=%s AND status='published')
                ON CONFLICT DO NOTHING RETURNING case_id""",
                (
                    case_id,
                    status,
                    entry,
                    close,
                    actual,
                    reason,
                    Jsonb(evidence),
                    c["exit_at"],
                    evaluated_at,
                    case_id,
                ),
            ).fetchone()
            if row and status == "scored":
                conn.execute(
                    """INSERT INTO lab_memories(case_id) SELECT case_id FROM lab_arms
                        WHERE case_id=%s AND method='single' AND status='published'""",
                    (case_id,),
                )
            return bool(row)

    def recent_cases(
        self,
        limit=50,
        before_id=None,
        market=None,
        ticker=None,
        from_date=None,
        to_date=None,
    ):
        conditions, params = cohort_filters(market, from_date, to_date)
        if before_id is not None:
            conditions.append("c.id < %s")
            params.append(int(before_id))
        if ticker is not None:
            conditions.append("c.ticker = %s")
            params.append(ticker.strip().upper())
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._connect() as conn:
            return conn.execute(
                SUMMARY + where + " ORDER BY c.id DESC LIMIT %s",
                [*params, max(1, min(int(limit), 500))],
            ).fetchall()

    def detail(self, case_id):
        return self.detail_if_changed(case_id)[1]

    def detail_if_changed(self, case_id, validators=()):
        """Read validation metadata and any requested body in the same database snapshot."""
        with self._connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            c = conn.execute(
                f"""WITH summary AS ({SUMMARY} WHERE c.id=%s)
                SELECT s.*, md5(jsonb_build_array(s.id, s.status,
                    (SELECT jsonb_agg(jsonb_build_array(a.method,a.status,a.recorded_at,a.xmin::text)
                        ORDER BY a.method) FROM lab_arms a WHERE a.case_id=s.id),
                    (SELECT captured_at FROM lab_references WHERE case_id=s.id),
                    (SELECT observed_at FROM lab_outcomes WHERE case_id=s.id),
                    (SELECT id FROM lab_memories WHERE case_id=s.id)
                )::text) AS revision FROM summary s""",
                (case_id,),
            ).fetchone()
            if not c:
                return None, None
            tag = '"' + c.pop("revision") + '"'
            if tag in validators or "*" in validators:
                return tag, None
            c["snapshot"] = conn.execute(
                "SELECT snapshot FROM lab_cases WHERE id=%s", (case_id,)
            ).fetchone()["snapshot"]
            c["arms"] = conn.execute(
                """SELECT a.*,CASE WHEN a.status='published' AND o.status='scored'
                THEN power(a.probability-o.actual,2) END AS brier FROM lab_arms a
                LEFT JOIN lab_outcomes o ON o.case_id=a.case_id WHERE a.case_id=%s ORDER BY a.method""",
                (case_id,),
            ).fetchall()
            c["outcome"] = conn.execute(
                "SELECT * FROM lab_outcomes WHERE case_id=%s", (case_id,)
            ).fetchone()
            c["memory"] = conn.execute(
                MEMORY + " WHERE m.case_id=%s", (case_id,)
            ).fetchone()
            cited = next((arm for arm in c["arms"] if arm["memory_id"]), None)
            c["selected_memory"] = None
            if cited:
                memory = conn.execute(
                    MEMORY + " WHERE m.id=%s", (cited["memory_id"],)
                ).fetchone()
                c["selected_memory"] = {
                    **memory,
                    **cited["audit"].get("memory_selection_v1", {}),
                }
            c["reference"] = conn.execute(
                "SELECT * FROM lab_references WHERE case_id=%s", (case_id,)
            ).fetchone()
            return tag, c

    def open_reference_cases(self):
        with self._connect() as conn:
            return conn.execute("""
                SELECT c.id,c.ticker,c.market,c.data_session,c.experiment_version,c.snapshot,
                       c.entry_at AS entry_open_at,c.exit_at AS exit_close_at
                FROM lab_cases c WHERE c.entry_at > statement_timestamp()
                AND NOT EXISTS(SELECT FROM lab_references r WHERE r.case_id=c.id)
                ORDER BY c.entry_at,c.id
            """).fetchall()

    def record_reference(
        self,
        case_id,
        *,
        source_report_id,
        ticker,
        probability,
        model,
        source_published_at,
        data_session,
        source="public_report",
    ):
        if (
            not isinstance(ticker, str)
            or not number(probability)
            or not 0 <= probability <= 1
            or type(source_report_id) is not int
            or not 0 < source_report_id < 2**63
            or not isinstance(model, str)
            or not model.strip()
            or not isinstance(source, str)
            or not source.strip()
        ):
            return False
        try:
            published = stamp(source_published_at)
            data_day = date.fromisoformat(str(data_session))
        except (ValueError, TypeError):
            return False
        with self._connect() as conn:
            c = conn.execute(
                "SELECT * FROM lab_cases WHERE id=%s FOR UPDATE", (case_id,)
            ).fetchone()
            if (
                not c
                or c["ticker"] != ticker.strip().upper()
                or c["data_session"] != data_day
            ):
                return False
            zone = ZoneInfo(ZONES[c["market"]])
            calendar = exchange_calendars.get_calendar(
                "XNYS" if c["market"] == "us" else "XKRX"
            )
            if not calendar.session_close(data_day) <= published < c["entry_at"]:
                return False
            next_session = calendar.date_to_session(
                published.astimezone(zone).date() + timedelta(days=1), direction="next"
            )
            if calendar.session_open(next_session) != c["entry_at"]:
                return False
            return bool(
                conn.execute(
                    """
                INSERT INTO lab_references(case_id,experiment_version,source,source_report_id,ticker,data_session,
                    probability,model,source_published_at,captured_at)
                SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,t FROM (SELECT clock_timestamp() t) tm
                WHERE %s<=t AND t<%s ON CONFLICT DO NOTHING RETURNING case_id
                """,
                    (
                        case_id,
                        c["experiment_version"],
                        source,
                        source_report_id,
                        c["ticker"],
                        data_day,
                        probability,
                        model,
                        published,
                        published,
                        c["entry_at"],
                    ),
                ).fetchone()
            )

    def pending_cases(self):
        with self._connect() as conn:
            rows = conn.execute("""SELECT c.id FROM lab_cases c WHERE NOT EXISTS(
              SELECT FROM lab_outcomes o WHERE o.case_id=c.id) AND (
              (c.entry_at > clock_timestamp() AND (SELECT count(*) FROM lab_arms a
                 WHERE a.case_id=c.id AND a.status<>'failed')<4)
              OR (c.exit_at <= clock_timestamp() AND EXISTS(SELECT FROM lab_arms a WHERE a.case_id=c.id
                 AND a.status='published'))) ORDER BY c.entry_at""").fetchall()
        return [self.detail(r["id"]) for r in rows]

    def stats(self, market=None, from_date=None, to_date=None):
        conditions, params = cohort_filters(market, from_date, to_date)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        cohort = "WITH target_cases AS (SELECT c.* FROM lab_cases c" + where + ") "

        with self._connect() as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            counts = dict.fromkeys(STATUSES, 0)
            for row in conn.execute(
                "SELECT status,count(*) AS n FROM ("
                + SUMMARY
                + where
                + ") cases GROUP BY status",
                params,
            ):
                counts[row["status"]] = row["n"]
            comparisons = conn.execute(
                cohort
                + """SELECT c.experiment_version,a.method AS control,b.method AS treated,
              a.model AS control_model,b.model AS treated_model,a.version AS control_version,b.version AS treated_version,
              count(*) AS n,count(DISTINCT (c.snapshot->'sessions'->>0)) AS distinct_entry_dates,
              count(DISTINCT c.ticker) AS distinct_tickers,avg(power(a.probability-o.actual,2)) AS control_brier,
              avg(power(b.probability-o.actual,2)) AS treated_brier,
              avg(power(a.probability-o.actual,2)-power(b.probability-o.actual,2)) AS improvement,
              avg(CASE WHEN a.probability>0.5 THEN o.exit_close/o.entry_open-1 ELSE 0 END) AS control_paper_return,
              avg(CASE WHEN b.probability>0.5 THEN o.exit_close/o.entry_open-1 ELSE 0 END) AS treated_paper_return,
              avg(((b.probability>0.5)::int-(a.probability>0.5)::int)*(o.exit_close/o.entry_open-1)) AS paper_improvement
              FROM lab_arms a JOIN lab_arms b ON a.case_id=b.case_id JOIN target_cases c ON c.id=a.case_id
              JOIN lab_outcomes o ON o.case_id=c.id AND o.status='scored'
              WHERE a.status='published' AND b.status='published'
                AND ((a.method='baseline' AND b.method IN ('single','debate','memory'))
                  OR (a.method='single' AND b.method IN ('debate','memory')))
                AND (b.method<>'memory' OR a.method<>'single' OR (a.model=b.model AND a.version=b.version))
              GROUP BY 1,2,3,4,5,6,7 ORDER BY 1,2,3,4,5,6,7""",
                params,
            ).fetchall()
            memory_effects = conn.execute(
                cohort
                + """SELECT m.memory_id,c.experiment_version,b.model,b.version,
              count(*) AS n,avg(power(b.probability-o.actual,2)-power(m.probability-o.actual,2)) AS improvement
              FROM lab_arms m JOIN lab_arms b ON m.case_id=b.case_id AND b.method='single'
                AND b.status='published' AND b.model=m.model AND b.version=m.version
              JOIN target_cases c ON c.id=m.case_id JOIN lab_outcomes o ON o.case_id=c.id AND o.status='scored'
              WHERE m.method='memory' AND m.status='published'
              GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""",
                params,
            ).fetchall()
            calibration = conn.execute(
                cohort
                + """
                ,bins AS (
                    SELECT a.method,a.model,a.version,c.experiment_version,a.probability,o.actual,
                      least(4,floor(a.probability*5)::int) AS bin_index
                    FROM lab_arms a JOIN target_cases c ON c.id=a.case_id
                    JOIN lab_outcomes o ON o.case_id=c.id AND o.status='scored'
                    WHERE a.status='published')
                SELECT method,model,version,experiment_version,bin_index,bin_index/5.0 AS lower,
                  (bin_index+1)/5.0 AS upper,count(*) AS n,avg(probability) AS mean_probability,
                  avg(actual)::float8 AS observed_rate FROM bins GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5
                """,
                params,
            ).fetchall()
            references = conn.execute(
                cohort
                + """
                SELECT c.experiment_version,r.source,r.model AS source_model,a.method,a.model,a.version,
                       count(*) AS n,count(DISTINCT (c.snapshot->'sessions'->>0)) AS distinct_entry_dates,
                       avg(power(r.probability-o.actual,2)) AS source_brier,
                       avg(power(a.probability-o.actual,2)) AS method_brier,
                       avg(power(r.probability-o.actual,2)-power(a.probability-o.actual,2)) AS improvement
                FROM lab_references r JOIN target_cases c ON c.id=r.case_id
                JOIN lab_outcomes o ON o.case_id=r.case_id AND o.status='scored'
                JOIN lab_arms a ON a.case_id=r.case_id AND a.status='published'
                GROUP BY 1,2,3,4,5,6 ORDER BY 1,2,3,4,5,6
                """,
                params,
            ).fetchall()
            return {
                "counts": counts,
                "reference_comparisons": references,
                "comparisons": comparisons,
                "memory_effects": memory_effects,
                "calibration": calibration,
            }
