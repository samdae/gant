"""Verify report semantics and untrusted response envelopes in a real browser DOM."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "packages/tradingagents/forecast_lab/web"


def browser():
    candidates = [
        os.environ.get("CHROME_BIN"),
        shutil.which("chromium"),
        shutil.which("google-chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


def browser_check(cases, refresh_checks=None):
    """Run with supplied API-shaped cases without contacting a scheduler, DB, or model."""
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        src = (WEB / "lab.js").read_text(encoding="utf-8")
        html = (WEB / "index.html").read_text(encoding="utf-8")
        fixture_data = json.dumps(cases, ensure_ascii=False).replace("<", r"\u003c")
        checks = r"""
        const fixture = CASE_DATA;
        const result = [];
        for (const c of fixture) {
            renderCase($("detail"), c);
            const d = $("detail");
            const text = d.textContent;
            const leaks = text.match(/\*\*|```|snapshot_sha256|input_sha256|strategy_json|forecast_5s|secret_key|create_bull_researcher|\[object Object\]/g) || [];
            if (leaks.length) result.push(c.id + " leaked " + leaks.join(","));
            if (d.querySelector("script,img,iframe,[onerror]") || window.pwned) result.push("executable markup");
            if (document.body.scrollWidth > window.innerWidth) result.push("mobile overflow");
            if (c.id === 8890) {
                const h = d.querySelector("h2 [data-instrument]");
                if (h?.textContent !== "TEST") result.push("unknown symbol fallback missing or duplicated");
                applyNameMap({TEST:"시장 기본 이름",MARKET:"기준 종목",OLD:"이전 종목"},false);
                const open = d.querySelector("details");
                open.open = true;
                applyNameMap({TEST:"등록한 긴 이름 <img src=x onerror=window.pwned=1>"},true);
                applyNameMap({TEST:"늦게 도착한 기본 이름",MARKET:"기준 종목",OLD:"이전 종목"},false);
                if (!h.querySelector("strong")?.textContent.startsWith("등록한 긴 이름") ||
                    h.querySelector("small")?.textContent !== "TEST" || h.querySelector("img") || !open.open)
                    result.push("registered name precedence, safety, or preserved disclosure failed");
                if (!d.querySelector('[data-instrument="MARKET"]')?.textContent.includes("기준 종목") ||
                    !d.querySelector('[data-instrument="OLD"]')?.textContent.includes("이전 종목"))
                    result.push("benchmark or memory missing label");
                if (!d.textContent.includes("TEST 원문은 그대로")) result.push("frozen narrative rewritten");
            }
            if (c.id === 8889) {
                const svg = d.querySelector(".price-plot svg");
                const axis = [...(svg?.querySelectorAll(".axis") || [])];
                const middle = axis.find(t => t.textContent === "01.06");
                if (!middle || Number(middle.getAttribute("x")) < 400) result.push("calendar gaps lost");
                if (!svg?.querySelector("title")?.textContent.includes("2026-01-02 – 2026-01-07 · 종가 3개"))
                    result.push("chart coverage wrong");
                const readouts = [...d.querySelectorAll(".prob-label strong")].map(n => n.textContent);
                if (readouts.join() !== "미발행,0.0%,미발행,건너뜀") result.push("probability missing/zero ambiguity");
            }
            if (c.id === 8888) {
                if (d.querySelector(".price-plot svg")) result.push("fabricated chart");
                for (const sel of ["strong","ul li","ol li","h5","blockquote","table","details > summary"]) {
                    if (!d.querySelector(".report " + sel) && !d.querySelector(sel)) result.push("missing " + sel);
                }
                if (!text.includes("제안 비중") || !text.includes("동결된 시장 근거") || !text.includes("상승 확률 70.0%"))
                    result.push("incomplete structured report");
                if (text.includes("SHOULD_NEVER_RENDER")) result.push("tool trace leaked");
            }
        }
        const resultNode = document.createElement("output");
        resultNode.id = "dom-result";
        resultNode.textContent = result.length ? result.join(" / ") : "passed";
        document.body.replaceChildren(resultNode);
        """.replace("CASE_DATA", fixture_data)
        if refresh_checks:
            checks = refresh_checks
        # Mock HTTP before running the normal script. A never-resolving fetch keeps the
        # periodic refresh out of this synchronous DOM renderer check.
        for name in ("workspace-tokens.css", "lab.css"):
            pattern = (
                r'<link rel="stylesheet" href="/(?:research/)?'
                + re.escape(name)
                + r'\?v=[^"]+" />'
            )
            css = (WEB / name).read_text(encoding="utf-8")
            html, count = re.subn(
                pattern, lambda _, css=css: "<style>" + css + "</style>", html
            )
            if count != 1:
                raise AssertionError(
                    f"Expected exactly one versioned {name} stylesheet"
                )
        html, count = re.subn(
            r'<script defer src="/lab\.js\?v=[^"]+"></script>', "", html
        )
        if count != 1:
            raise AssertionError("Expected exactly one versioned lab.js script")
        html = html.replace(
            "</body>",
            "<script>window.fetch=()=>new Promise(()=>{});</script><script>"
            + src
            + "</script><script>"
            + checks
            + "</script></body>",
        )
        file = folder / "report.html"
        file.write_text(html, encoding="utf-8")
        r = subprocess.run(
            [
                browser(),
                "--headless=new",
                "--disable-gpu",
                "--virtual-time-budget=1500",
                "--no-first-run",
                "--window-size=420,800",
                "--user-data-dir=" + str(folder / "profile"),
                "--dump-dom",
                file.as_uri(),
            ],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            check=True,
        )
        marker = '<output id="dom-result">'
        return (
            r.stdout.rsplit(marker, 1)[-1].split("</output>", 1)[0]
            if marker in r.stdout
            else "browser failed to execute checks"
        )


@unittest.skipUnless(browser(), "A Chromium browser is required")
class LabWebTest(unittest.TestCase):
    def test_independent_refresh_revalidation_and_selection_race(self):
        checks = r"""
        (async () => {
          const issues = [];
          const check = (ok, why) => { if (!ok) issues.push(why); };
          const result = document.createElement("output");
          result.id = "dom-result";
          try {
            let bad = "stats", rev = 1, pending, slow = false, downloaded = 0;
            const row = id => ({id, ticker:"SYM" + id, status:"pending", arms:[], snapshot:{}});
            window.fetch = async (url, opts) => {
              const kind = url.includes("stats?") ? "stats" : url.includes("cases?") ? "list" :
                  url.includes("cases/") ? "detail" : "status";
              if (bad === kind) return new Response(null, {status:503});
              if (kind === "detail") {
                const id = Number(url.split("/").at(-1));
                const tag = 'W/"' + id + '-' + rev + '"';
                if (opts.headers["If-None-Match"] === tag)
                  return new Response(null, {status:304, headers:{ETag:tag}});
                if (slow && id === 1) await new Promise(resolve => pending = resolve);
                downloaded++;
                return Response.json(row(id), {headers:{ETag:tag}});
              }
              return Response.json(kind === "status" ? {tickers:[]} : kind === "stats" ?
                {counts:{}} : [row(1),row(2)]);
            };
            await refresh();
            check($("detail").dataset.caseId === "1" && !$("stats-error").hidden && $("list-error").hidden, "stats blocked cases");
            bad = "detail"; await refresh();
            check(!$("detail-error").hidden && $("stats-error").hidden, "detail error leaked");
            bad = "list"; await refresh();
            check($("detail-error").hidden && !$("list-error").hidden && downloaded === 1, "304 recovery/redownload");
            rev++; bad = "status"; await refresh();
            check(downloaded === 2 && !$("status-error").hidden && $("list-error").hidden, "new revision not fetched");
            slow = true; rev++;
            const obsolete = showCase(1);
            await showCase(2);
            pending(); await obsolete;
            check($("detail").dataset.caseId === "2", "late response replaced selected case");
          } catch (e) { issues.push(String(e)); }
          result.textContent = issues.length ? issues.join(" / ") : "passed";
          document.body.replaceChildren(result);
        })();
        """
        self.assertEqual(browser_check([], checks), "passed")

    def test_nested_reports_and_no_executable_markup(self):
        narrative = (
            "### 투자 근거\n\n**강조된 문장**\n\n- 이유 하나\n- 이유 둘\n\n1. 첫 항목\n2. 다음 항목\n\n"
            "> 가격 근거\n\n|지표|값|\n|---|---|\n|거래량|100|\n\n<img src=x onerror=window.pwned=1>\n\n"
            "```strategy_json\n"
            + json.dumps(
                {
                    "action": "BUY",
                    "conviction": "HIGH",
                    "allocation_pct": 35,
                    "forecast_5s": {"p_up": 0.7},
                    "secret_key": "SHOULD_NEVER_RENDER",
                }
            )
            + "\n```"
        )
        envelope = json.dumps(
            {
                "content": [{"type": "text", "text": narrative}],
                "calls": [{"arguments": {"secret_key": "SHOULD_NEVER_RENDER"}}],
            }
        )
        c = {
            "id": 8888,
            "ticker": "TEST",
            "market": "us",
            "status": "awaiting",
            "snapshot": {"features": {}, "currency": "USD", "bars": []},
            "arms": [
                {
                    "method": "debate",
                    "status": "published",
                    "probability": 0.7,
                    "rationale": envelope,
                    "audit": {
                        "snapshot_sha256": "SHOULD_NEVER_RENDER",
                        "debate": [
                            {"role": "create_bull_researcher", "output": envelope}
                        ],
                    },
                }
            ],
        }
        self.assertEqual(browser_check([c]), "passed")

    def test_truthful_price_axis_and_missing_probability(self):
        case = {
            "id": 8889,
            "ticker": "TEST",
            "market": "us",
            "status": "awaiting",
            "snapshot": {
                "currency": "USD",
                "bars": [
                    {"date": "2026-01-02", "close": 100},
                    {"date": "2026-01-06", "close": 120},
                    {"date": "2026-01-07", "close": 110},
                ],
            },
            "arms": [
                {"method": "single", "status": "published", "probability": 0},
                {"method": "memory", "status": "skipped"},
            ],
        }
        self.assertEqual(browser_check([case]), "passed")

    def test_names_arrive_without_blocking_frozen_case_and_preserve_disclosures(self):
        case = {
            "id": 8890,
            "ticker": "TEST",
            "status": "awaiting",
            "market": "us",
            "snapshot": {
                "currency": "USD",
                "benchmark": {"ticker": "MARKET", "status": "unavailable"},
            },
            "selected_memory": {"ticker": "OLD", "rationale": "이전 사례"},
            "arms": [
                {
                    "method": "memory",
                    "status": "published",
                    "probability": 0.5,
                    "rationale": "TEST 원문은 그대로",
                }
            ],
        }
        self.assertEqual(browser_check([case]), "passed")
