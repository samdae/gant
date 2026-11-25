import json
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import Mock

import test_forecast_lab_store as store_fixture
from tradingagents.forecast_lab.scheduled_issues import collect_scheduled
from tradingagents.forecast_lab.issue_collector import (
    EXPORT,
    SOURCE,
    article_url,
    case_issues,
    collect_one,
    export_url,
    parse_export,
    parse_feed,
    public_issues,
)


def feed(at, title="Example article"):
    return f"""<rss><channel><item><pubDate>{format_datetime(at)}</pubDate><title>{title} - Reuters</title>
    <link>https://news.google.com/rss/articles/abc123?oc=5</link><source>Reuters</source>
    </item></channel></rss>""".encode()


def bundle(when):
    return {
        "schema_version": "1.4",
        "query": "Nvidia news",
        "generated_at": "2001-01-01T00:00:00Z",
        "window_days": 30,
        "results": [
            {
                "published_at": when,
                "url": "https://x.com/company/status/123",
                "title": "Earnings announcement",
                "source": "x",
                "summary": "private prompt",
            }
        ],
    }


class IssueProjectionTests(unittest.TestCase):
    def test_feed_bounds_and_host(self):
        now = datetime.now(UTC)
        self.assertEqual(len(parse_feed(feed(now), now)), 1)
        self.assertEqual(parse_feed(feed(now + timedelta(days=1)), now), [])
        self.assertEqual(parse_feed(feed(now - timedelta(days=31)), now), [])
        for url in (
            "file:///tmp/key",
            "https://news.google.com@elsewhere/rss/articles/abcdefgh",
            "https://news.google.com/redirect?to=internal",
        ):
            self.assertIsNone(article_url(url))
        self.assertIsNone(export_url("https://x.com/redirect?to=internal", "x"))
        with self.assertRaises(ValueError):
            parse_feed(b"<!DOCTYPE html>not an rss feed", now)

    def test_hackernews_submitted_article_without_discussion_id(self):
        raw = bundle("2026-11-15")
        raw["results"][0].update(
            source="hackernews",
            url="https://news.independentpublisher.org/earnings/example?utm_source=hn",
        )
        now = datetime(2026, 11, 24, tzinfo=UTC)
        ((url, title, publisher, at, day),) = parse_export(
            json.dumps(raw).encode(), now, "NVDA"
        )
        view = public_issues(
            {
                "as_of": now,
                "source": EXPORT,
                "status": "available",
                "collected_at": now - timedelta(seconds=1),
                "items": [
                    {
                        "source": EXPORT,
                        "url": url,
                        "title": title,
                        "publisher": publisher,
                        "published_at": at,
                        "published_day": day,
                        "first_seen_at": now - timedelta(seconds=1),
                    }
                ],
            }
        )
        self.assertEqual(
            view["items"][0]["publisher"], "news.independentpublisher.org · Hacker News"
        )
        self.assertEqual(
            view["items"][0]["url"],
            "https://news.independentpublisher.org/earnings/example",
        )
        self.assertIsNone(
            export_url(
                "https://nvidianews.nvidia.com/redirect?dst=https://x.com", "hackernews"
            )
        )
        self.assertIsNone(
            export_url("https://intranet.local/news/example", "hackernews")
        )

    def test_existing_export_publisher_label_is_displayed_from_validated_hostname(self):
        cutoff = datetime(2026, 11, 24, tzinfo=UTC)
        legacy = {
            "source": EXPORT,
            "publisher": "Earlier display name · Hacker News",
            "url": "https://independent-publisher.org/markets/example",
            "title": "Issuer update",
            "published_at": cutoff - timedelta(days=2),
            "first_seen_at": cutoff - timedelta(days=1),
        }
        case = {
            "source": EXPORT,
            "status": "available",
            "as_of": cutoff,
            "collected_at": legacy["first_seen_at"],
            "items": [legacy],
        }
        self.assertEqual(
            public_issues(case)["items"][0]["publisher"],
            "independent-publisher.org · Hacker News",
        )
        self.assertEqual(legacy["publisher"], "Earlier display name · Hacker News")
        legacy["source"] = SOURCE
        self.assertFalse(public_issues(case)["items"])

    def test_external_hn_original_urls_are_links_only_and_exclude_local_targets(self):
        for url in (
            "http://publisher.org/story",
            "https://localhost:443/story",
            "https://intranet/story",
            "https://192.168.10.1/story",
            "https://[::1]/news",
            "https://user:p@outside.org/a",
            "https://outside.org:8080/story",
            "https://localhost.localtest.me/story",
            "https://outside.org/stories/a?next=https://localhost",
            "https://outside.org/%5c%5cfoo",
        ):
            with self.subTest(url=url):
                self.assertIsNone(export_url(url, "hackernews"))
        self.assertEqual(
            export_url(
                "https://another-news.org:443/article?id=22&utm_source=hn", "hackernews"
            ),
            "https://another-news.org/article?id=22",
        )

    def test_day_only_export_has_no_invented_precise_timestamp(self):
        raw = bundle("2026-11-05")
        payload = json.dumps(raw).encode()
        now = datetime(2026, 11, 6, 11, 59, tzinfo=UTC)
        self.assertEqual(parse_export(payload, now, "NVDA"), [])
        (row,) = parse_export(payload, now + timedelta(minutes=2), "NVDA")
        self.assertEqual(row[3], datetime(2026, 11, 6, 12, tzinfo=UTC))
        self.assertEqual(str(row[4]), "2026-11-05")
        with self.assertRaises(ValueError):
            parse_export(payload, now, "KO")

    def test_public_cutoff_strict_and_fields_allowlisted(self):
        now = datetime.now(UTC)
        item = {
            "source": SOURCE,
            "title": "Article",
            "url": "https://news.google.com/rss/articles/abc123",
            "publisher": "wire",
            "published_at": now - timedelta(days=1),
            "first_seen_at": now,
            "debug": "private",
        }
        dto = {
            "as_of": now,
            "status": "empty",
            "source": SOURCE,
            "collected_at": now - timedelta(hours=1),
            "items": [item],
        }
        self.assertFalse(public_issues(dto)["items"])
        dto["as_of"] += timedelta(seconds=1)
        self.assertNotIn("debug", public_issues(dto)["items"][0])


@unittest.skipUnless(
    os.getenv("PG_TEST_BINDIR"), "requires isolated PostgreSQL test binaries"
)
class IssueStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store_fixture.ForecastStoreTests.setUpClass.__func__(cls)

    def test_scheduled_run_precedes_cutoff_and_coalesces_concurrent_schedules(self):
        connect = self.store._connect
        ticker = "ADD-ON"  # A valid scheduled ticker absent from the V3 watchlist.
        release = threading.Event()
        collecting = threading.Event()
        calls = []

        def engine(symbol, market):
            calls.append((symbol, market))
            collecting.set()
            if not release.wait(10):
                raise TimeoutError
            raw = bundle((datetime.now(UTC) - timedelta(days=2)).isoformat())
            raw["query"] = f"{symbol} market developments"
            raw["source_status"] = {"hackernews": "no-results", "youtube": "ok"}
            raw["results"][0].update(source="youtube", url="https://www.youtube.com/watch?v=abcdefghijk")
            return raw

        with connect() as conn:
            old_cutoff = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            leader = pool.submit(collect_scheduled, connect, ticker, "us", engine)
            self.assertTrue(collecting.wait(5))
            peer = pool.submit(collect_scheduled, connect, ticker, "us", engine)
            try:
                with connect() as conn:
                    conn.autocommit = True
                    deadline = time.monotonic() + 5
                    while not conn.execute(
                        "SELECT EXISTS (SELECT FROM pg_locks WHERE locktype='advisory' AND NOT granted) AS waiting"
                    ).fetchone()["waiting"]:
                        if time.monotonic() >= deadline:
                            self.fail("Concurrent schedule did not wait for the active collection")
                        time.sleep(.025)
            finally:
                release.set()
            first, reused = leader.result(), peer.result()
        self.assertEqual(calls, [(ticker, "us")])
        self.assertEqual((first["status"], first["disposition"]), ("available", "collected"))
        self.assertEqual((first["id"], "reused"), (reused["id"], reused["disposition"]))
        with connect() as conn:
            after = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
            self.assertEqual(case_issues(conn, ticker, old_cutoff, source=EXPORT)["status"], "uncollected")
            visible = case_issues(conn, ticker, after, source=EXPORT)
            self.assertEqual(len(visible["items"]), 1)
            self.assertEqual(visible["collected_at"], first["collected_at"].isoformat())

    def test_scheduled_failure_backoff_empty_and_future_retries(self):
        connect = self.store._connect
        ticker = "035420.KS"
        def collect(engine):
            return collect_scheduled(connect, ticker, "kr", engine)

        def age(run, interval):
            with connect() as conn:
                conn.execute("UPDATE v3_issue_runs SET collected_at=clock_timestamp()-%s WHERE id=%s",
                             (interval, run["id"]))

        wrong = bundle((datetime.now(UTC) - timedelta(days=2)).isoformat())  # NVDA query.
        failed = collect(Mock(return_value=wrong))
        self.assertEqual(failed["status"], "failed")
        engine = Mock(side_effect=RuntimeError("all providers unavailable"))
        self.assertEqual(collect(engine)["id"], failed["id"])
        engine.assert_not_called()
        age(failed, timedelta(minutes=16))
        failed = collect(engine)
        self.assertEqual((failed["status"], failed["disposition"]), ("failed", "collected"))
        engine.assert_called_once_with(ticker, "kr")
        age(failed, timedelta(minutes=16))
        empty = dict(wrong, query=ticker, results=[],
                     source_status={"hackernews": "no-results", "youtube": "no-results"})
        engine = Mock(return_value=empty)
        first = collect(engine)
        self.assertEqual(first["status"], "empty")
        self.assertEqual(collect(engine)["id"], first["id"])
        age(first, timedelta(hours=7))
        # Simulate the earlier failures ageing on the same timeline too.
        with connect() as conn:
            conn.execute("UPDATE v3_issue_runs SET collected_at=collected_at-interval '1 day' WHERE ticker=%s AND status='failed'", (ticker,))
        self.assertNotEqual(collect(engine)["id"], first["id"])
        self.assertEqual(engine.call_count, 2)

    def test_partial_source_failure_retains_in_time_items_and_retries(self):
        ticker = "PART"
        connect = self.store._connect
        export = bundle((datetime.now(UTC) - timedelta(days=3)).isoformat())
        export.update(query=ticker, source_status={"youtube": "timeout", "hackernews": "ok"})
        export["results"][0].update(source="hackernews", url="https://news.ycombinator.com/item?id=123")
        engine = Mock(return_value=export)
        run = collect_scheduled(connect, ticker, "us", engine)
        self.assertEqual((run["status"], run["item_count"]), ("failed", 1))
        with connect() as conn:
            cutoff = conn.execute("SELECT clock_timestamp() AS t").fetchone()["t"]
            group = case_issues(conn, ticker, cutoff, source=EXPORT)
            self.assertEqual(group["status"], "failed")
            self.assertEqual([r["url"] for r in group["items"]], [export["results"][0]["url"]])
            conn.execute("UPDATE v3_issue_runs SET collected_at=collected_at-interval '16 minutes' WHERE id=%s",
                         (run["id"],))
        export.update(results=[], source_status={"youtube": "timeout", "hackernews": "unreachable"})
        failed = collect_scheduled(connect, ticker, "us", engine)
        self.assertEqual((failed["status"], failed["item_count"]), ("failed", 0))
        self.assertEqual(engine.call_count, 2)

    def test_retries_import_and_failed_collection_as_of(self):
        store = self.store
        kr = {"ticker": "005930.KS", "market": "kr"}
        us = {"ticker": "NVDA", "market": "us"}

        def read(ticker, cutoff):
            with store._connect() as conn:
                return case_issues(conn, ticker, cutoff)

        original = datetime.now(UTC)
        pub = original - timedelta(days=4)
        self.assertEqual(collect_one(store, kr, lambda *_: feed(pub)), "available")
        one = read(kr["ticker"], datetime.now(UTC))
        self.assertEqual(one["items"][0]["publisher"], "Reuters")
        first_seen = datetime.fromisoformat(one["items"][0]["first_seen_at"])
        self.assertEqual(read(kr["ticker"], first_seen)["status"], "uncollected")
        self.assertEqual(
            collect_one(store, kr, lambda *_: feed(pub, "Updated title")), "available"
        )
        self.assertEqual(
            collect_one(store, kr, Mock(side_effect=OSError("unavailable"))), "failed"
        )
        later = read(kr["ticker"], datetime.now(UTC))
        self.assertEqual(later["status"], "failed")
        self.assertEqual(later["items"], one["items"])
        self.assertEqual(read(kr["ticker"], original)["items"], [])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "export.json"
            path.write_text(json.dumps(bundle(pub.date().isoformat())), encoding="utf8")
            self.assertEqual(collect_one(store, us, export_path=path), "available")
        imported = read("NVDA", datetime.now(UTC))
        after = datetime.now(UTC)
        separated = store.report_sources("NVDA", after)
        self.assertEqual(separated["last30days"]["items"], imported["items"])
        self.assertEqual(separated["issues"]["status"], "uncollected")
        self.assertEqual(
            store.report_sources("NVDA", original)["last30days"]["items"], []
        )
        self.assertEqual(
            store.report_sources(kr["ticker"], after)["last30days"]["items"], []
        )
        self.assertEqual(
            store.report_sources("NVDA", after + timedelta(days=31))["last30days"][
                "items"
            ],
            [],
        )
        self.assertEqual(imported["source"], EXPORT)
        self.assertEqual(imported["items"][0]["published_precision"], "day")
        self.assertGreater(
            datetime.fromisoformat(imported["items"][0]["first_seen_at"]), original
        )
